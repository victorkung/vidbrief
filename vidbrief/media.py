"""yt-dlp probe + audio-only download, and the MLX Whisper subprocess.

Download hardening is carried over from clipgenerator's scripts/download.sh.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

from .config import ROOT
from .naming import canonicalize_media_url

ProgressFn = Callable[[dict[str, Any]], None]
TRANSCRIBE_PY = ROOT / "scripts" / "transcribe.py"

# android_vr (yt-dlp 2026.07 default) 403s mid-file on YouTube.
_YT_EXTRACTOR_ARGS = "youtube:player_client=web_embedded,default,-android_vr"


def _is_youtube(url: str) -> bool:
    return bool(re.search(r"youtube\.com|youtu\.be|youtube-nocookie\.com", url))


def _ytdlp_base(url: str) -> list[str]:
    cmd = ["yt-dlp", "--no-playlist", "--no-warnings", "--retries", "10", "--fragment-retries", "10"]
    cookies = (os.environ.get("YTDLP_COOKIES_FROM_BROWSER") or "").strip()
    if cookies:
        cmd += ["--cookies-from-browser", cookies]
    if _is_youtube(url):
        cmd += ["--extractor-args", _YT_EXTRACTOR_ARGS]
    return cmd


def ffprobe_duration(path: Path) -> float | None:
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(path)],
            text=True,
            timeout=20,
        ).strip()
        return float(out) if out else None
    except (subprocess.CalledProcessError, ValueError, FileNotFoundError, subprocess.TimeoutExpired):
        return None


def probe_url(url: str) -> dict[str, Any]:
    url = canonicalize_media_url(url)
    cmd = _ytdlp_base(url) + ["--dump-json", url]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    except FileNotFoundError as exc:
        raise RuntimeError("yt-dlp not found. Install with: brew install yt-dlp") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Timed out resolving URL") from exc
    if proc.returncode != 0 or not proc.stdout.strip():
        raise RuntimeError(f"Could not resolve URL: {(proc.stderr or proc.stdout)[-500:]}")
    meta = json.loads(proc.stdout.strip().splitlines()[-1])
    return {
        "id": meta.get("id"),
        "title": meta.get("title") or "Untitled",
        "uploader": meta.get("uploader") or meta.get("channel") or meta.get("creator"),
        "duration": meta.get("duration"),
        "webpage_url": meta.get("webpage_url") or url,
    }


def download_audio(
    url: str,
    dest: Path,
    *,
    expected_duration: float | None = None,
    on_progress: ProgressFn | None = None,
    on_proc: Callable[[subprocess.Popen], None] | None = None,
) -> Path:
    """Audio-only m4a at `dest`. Rejects partial files (< 90% of the probed duration)."""
    url = canonicalize_media_url(url)
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = _ytdlp_base(url) + [
        "--newline",
        "-N", "4",
        "-x", "--audio-format", "m4a", "--audio-quality", "0",
        "-o", str(dest.with_suffix(".%(ext)s")),
        url,
    ]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=str(dest.parent))
    except FileNotFoundError as exc:
        raise RuntimeError("yt-dlp not found. Install with: brew install yt-dlp") from exc
    if on_proc:
        on_proc(proc)
    assert proc.stdout is not None
    pct_re = re.compile(r"(\d{1,3}(?:\.\d+)?)%")
    lines: list[str] = []
    last = 0.0
    for raw in proc.stdout:
        line = raw.strip()
        if not line:
            continue
        lines = (lines + [line])[-40:]
        m = pct_re.search(line) if "[download]" in line else None
        if m and on_progress and (time.monotonic() - last > 0.5):
            last = time.monotonic()
            on_progress({"stage": "downloading", "percent": float(m.group(1)), "detail": line[10:].strip()[:120]})
    code = proc.wait()
    if code < 0:
        raise RuntimeError("Download was cancelled")
    if code != 0 or not dest.is_file() or dest.stat().st_size == 0:
        tail = "\n".join(lines[-12:])
        if "403" in tail or "blocked" in tail.lower():
            raise RuntimeError(
                "Download blocked (HTTP 403). Set YTDLP_COOKIES_FROM_BROWSER=chrome in .env, "
                "run `brew upgrade yt-dlp`, and retry.\n" + tail[-600:]
            )
        raise RuntimeError(f"Audio download failed:\n{tail[-800:]}")
    got = ffprobe_duration(dest)
    if expected_duration and got and got < 0.9 * float(expected_duration):
        dest.unlink(missing_ok=True)
        raise RuntimeError(
            f"Download was cut short ({got:.0f}s of {float(expected_duration):.0f}s). Retry; "
            "if it keeps happening set YTDLP_COOKIES_FROM_BROWSER=chrome."
        )
    return dest


_CAPTION_NOISE = re.compile(r"\[(?:music|applause|laughter|inaudible)\]", re.I)


def _parse_json3(path: Path) -> list[dict[str, Any]]:
    """YouTube json3 captions → [{'start', 'end', 'text'}]. Keeps '>>' speaker-change marks."""
    events = json.loads(path.read_text(encoding="utf-8")).get("events") or []
    segments = []
    for ev in events:
        if ev.get("aAppend") or not ev.get("segs"):
            continue
        text = _CAPTION_NOISE.sub("", "".join(s.get("utf8", "") for s in ev["segs"]))
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            continue
        start = ev.get("tStartMs", 0) / 1000
        segments.append({"start": round(start, 3), "end": round(start + ev.get("dDurationMs", 0) / 1000, 3), "text": text})
    return segments


def fetch_youtube_captions(url: str, dest_json: Path) -> str | None:
    """Write YouTube's English captions as a transcript JSON (same shape as Whisper's).

    Prefers captions uploaded by the creator, then YouTube's own speech recognition.
    Returns the source label, or None when the video has no usable English captions.
    """
    url = canonicalize_media_url(url)
    if not _is_youtube(url):
        return None
    folder = dest_json.parent
    folder.mkdir(parents=True, exist_ok=True)
    attempts = (
        ("youtube-captions", ["--write-subs", "--sub-langs", "en,en-US,en-GB"]),
        ("youtube-auto-captions", ["--write-auto-subs", "--sub-langs", "en-orig,en"]),
    )
    for label, flags in attempts:
        for old in folder.glob(".captions.*.json3"):
            old.unlink()
        cmd = _ytdlp_base(url) + ["--skip-download", *flags, "--sub-format", "json3",
                                  "-o", str(folder / ".captions.%(ext)s"), url]
        try:
            subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None
        files = sorted(folder.glob(".captions.*.json3"), key=lambda p: ("orig" not in p.name, p.name))
        segments = _parse_json3(files[0]) if files else []
        for f in files:
            f.unlink()
        if len(segments) >= 3:
            payload = {"source": label, "text": " ".join(s["text"] for s in segments), "words": [],
                       "segments": segments, "language": "en"}
            dest_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            return label
    return None


def transcribe(
    audio: Path,
    *,
    model: str,
    on_progress: ProgressFn | None = None,
    on_proc: Callable[[subprocess.Popen], None] | None = None,
) -> Path:
    """Run scripts/transcribe.py (chunked MLX Whisper). Returns the transcript JSON path."""
    cmd = [sys.executable, str(TRANSCRIBE_PY), "--model", model, "--language", "en", str(audio)]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if on_proc:
        on_proc(proc)
    assert proc.stdout is not None
    tail: list[str] = []
    for raw in proc.stdout:
        line = raw.rstrip("\n")
        if line.startswith("PROGRESS_JSON:"):
            if on_progress:
                try:
                    p = json.loads(line[len("PROGRESS_JSON:"):])
                except json.JSONDecodeError:
                    continue
                on_progress({"stage": "transcribing", "percent": p.get("percent"), "detail": _stt_detail(p)})
        elif line.strip() and not line.startswith("TIMING_JSON:"):
            tail = (tail + [line])[-15:]
    code = proc.wait()
    json_path = audio.parent / f"{audio.stem}.transcript.json"
    if code < 0:
        raise RuntimeError("Transcription was cancelled")
    if code != 0 or not json_path.is_file():
        raise RuntimeError("Whisper transcription failed:\n" + "\n".join(tail)[-800:])
    # transcribe.py (built for video) extracts an audio sidecar; our input is already audio.
    (audio.parent / f"{audio.stem}.audio.m4a").unlink(missing_ok=True)
    return json_path


def _stt_detail(p: dict[str, Any]) -> str | None:
    pos, total = p.get("audio_pos_s"), p.get("audio_total_s")
    if pos is None or not total:
        return None
    fmt = lambda s: time.strftime("%H:%M:%S", time.gmtime(max(0, float(s))))  # noqa: E731
    out = f"{fmt(min(float(pos), float(total)))} / {fmt(total)}"
    if p.get("chunk") and p.get("chunks"):
        out += f" · chunk {p['chunk']}/{p['chunks']}"
    return out

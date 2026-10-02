"""Read briefs aloud: brief.md → a clean narration script → brief.mp3 (Kokoro via mlx-audio)."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from .config import ROOT, Settings
from .modellock import model_slot

TTS_RUN = ROOT / "scripts" / "tts_run.py"

_TS = re.compile(r"\*{0,2}\[?\b\d{1,2}:\d{2}(?::\d{2})?\b\]?\*{0,2}")
_LINK = re.compile(r"\[([^\]]+)\]\((?:[^)]+)\)")
_URL = re.compile(r"https?://\S+")
_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
_LABEL = re.compile(r"^\*\*(.+?)\*\*\s*:?\s*")
_SCALE = {"K": "thousand", "M": "million", "B": "billion", "T": "trillion"}
_REPLACEMENTS = [
    (re.compile(r"(\d)\s*[—–]\s*(?=[$\d])"), r"\1 to "),  # ranges: 5–10 → 5 to 10
    (re.compile(r"\s*[—–]\s*"), ", "),
    (re.compile(r"\s&\s"), " and "),
    (re.compile(r"\bvs\.?(?=\s)"), "versus"),
    (re.compile(r"\be\.g\.,?"), "for example,"),
    (re.compile(r"\bi\.e\.,?"), "that is,"),
    (re.compile(r"(?:(?<=\s)|^)~\s?(?=[$\d])"), "about "),
    # $200M → $200 million, 55K → 55 thousand (so they aren't read as letters)
    (re.compile(r"(\$?\d+(?:\.\d+)?)\s?([KMBT])\b"), lambda m: f"{m.group(1)} {_SCALE[m.group(2)]}"),
]


def _sentence(text: str) -> str:
    text = text.strip()
    return text if not text or text[-1] in ".!?:" else text + "."


def _clean_inline(text: str) -> str:
    text = _LINK.sub(r"\1", text)
    text = _URL.sub("", text)
    text = _TS.sub("", text)
    text = text.replace("★", "")
    text = re.sub(r"[*_`#]", "", text)
    for pattern, repl in _REPLACEMENTS:
        text = pattern.sub(repl, text)
    return re.sub(r"\s{2,}", " ", text).strip(" ,")


def brief_to_speech(brief_md: str, *, title: str | None = None, uploader: str | None = None) -> str:
    """Narration script: headings become spoken signposts, bullets become sentences, and
    timestamps, markdown, stars and links are removed. One line per spoken unit (pauses)."""
    out: list[str] = []
    if title:
        name = _clean_inline(title).rstrip("…. ")
        out.append(_sentence(f"VidBrief summary of {name}" + (f", from {uploader}" if uploader else "")))
    for i, raw in enumerate((brief_md or "").splitlines()):
        line = raw.strip()
        if not line:
            continue
        if i == 0 and line.startswith("*") and line.endswith("*") and "·" in line:
            continue  # the metadata line (title · channel · date · length)
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
            heading = re.sub(r"^(Chapter \d+):\s*", r"\1. ", heading)
            out.append(_sentence(_clean_inline(heading)))
            continue
        if _BULLET.match(line):
            body = _TS.sub("", _BULLET.sub("", line), count=1).strip()
            m = _LABEL.match(body)
            if m:
                body = f"{_sentence(_clean_inline(m.group(1)))} {body[m.end():]}"
            out.append(_sentence(_clean_inline(body)))
            continue
        out.append(_sentence(_clean_inline(line)))
    return "\n".join(s for s in out if s.strip(" ."))


def synthesize(
    text: str,
    out_path: Path,
    *,
    settings: Settings,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
    on_proc: Callable[[subprocess.Popen], None] | None = None,
) -> dict[str, Any]:
    """Run scripts/tts_run.py under the machine-wide model slot. Returns {'seconds', 'gen_seconds', ...}."""
    waiting = (lambda: on_progress({"stage": "voicing", "percent": None,
                                    "detail": "Waiting for another VidBrief job to finish…"})) if on_progress else None
    with model_slot(on_wait=waiting):
        proc = subprocess.Popen([sys.executable, str(TTS_RUN)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True)
        if on_proc:
            on_proc(proc)
        assert proc.stdin and proc.stdout
        proc.stdin.write(json.dumps({"text": text, "out": str(out_path), "model": settings.tts_model,
                                     "voice": settings.tts_voice, "speed": settings.tts_speed}))
        proc.stdin.close()
        result: dict[str, Any] = {}
        tail: list[str] = []
        for raw in proc.stdout:
            tag, _, body = raw.rstrip("\n").partition(":")
            if tag == "PROGRESS_JSON" and on_progress:
                p = json.loads(body)
                on_progress({"stage": "voicing", "percent": 100 * p["done"] / max(1, p["total"]),
                             "detail": f"part {p['done']}/{p['total']}"})
            elif tag == "RESULT_JSON":
                result = json.loads(body)
            elif raw.strip():
                tail = (tail + [raw.rstrip()])[-12:]
        code = proc.wait()
    if code < 0:
        raise RuntimeError("Audio was cancelled")
    if code != 0 or not result or not out_path.is_file():
        raise RuntimeError("Audio generation failed:\n" + "\n".join(tail)[-800:])
    return result

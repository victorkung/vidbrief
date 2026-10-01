"""URL → download → transcribe → summarize, resumable from files on disk.

Shared by the CLI and the API. Each stage writes an artifact into the brief folder;
a rerun skips stages whose artifact already exists.
"""

from __future__ import annotations

import json
import time
from datetime import date
from pathlib import Path
from typing import Any, Callable

from . import media, summarize
from .config import Settings
from .naming import canonicalize_media_url, clean_title, is_supported_url, make_project_dir
from .store import Library, make_brief

UpdateFn = Callable[[dict[str, Any]], None]

# Overall progress band per stage (start, end).
BANDS = {
    "resolving": (0, 3),
    "downloading": (3, 15),
    "transcribing": (15, 55),
    "condensing": (55, 78),
    "chapters": (78, 81),
    "writing": (81, 93),
    "synthesizing": (93, 99),
}
MESSAGES = {
    "resolving": "Resolving URL…",
    "downloading": "Downloading audio…",
    "transcribing": "Transcribing with Whisper…",
    "condensing": "Condensing transcript…",
    "chapters": "Planning chapters…",
    "writing": "Writing chapters…",
    "synthesizing": "Writing summary…",
}


def meta_line(brief: dict[str, Any]) -> str:
    """Italic line atop brief.md so copied briefs carry their source: title · channel · date · length."""
    bits = [brief.get("title"), brief.get("uploader")]
    if brief.get("published"):
        bits.append("Published " + date.fromisoformat(brief["published"]).strftime("%b %-d, %Y"))
    if brief.get("duration"):
        secs = float(brief["duration"])
        bits.append(f"{round(secs)} sec" if secs < 60 else f"{round(secs / 60)} min")
    return "*" + " · ".join(str(b) for b in bits if b) + "*"


def artifacts(folder: Path) -> dict[str, Path]:
    return {
        "audio": folder / "source.m4a",
        "transcript_json": folder / "source.transcript.json",
        "transcript_md": folder / "transcript.md",
        "condensed": folder / "condensed.md",
        "key_points": folder / "key_points.md",
        "brief": folder / "brief.md",
    }


def library(settings: Settings) -> Library:
    return Library(settings.data_dir / "library.json")


def create(url: str, settings: Settings, lib: Library) -> dict[str, Any]:
    if not is_supported_url(url):
        raise ValueError("Paste a YouTube watch URL or an X status URL.")
    brief = make_brief(title="Resolving…", url=canonicalize_media_url(url), whisper_model=settings.whisper_model)
    brief["llm_model"] = settings.llm_model
    brief["mode"] = settings.mode
    return lib.upsert_brief(brief)


def process(
    brief_id: str,
    settings: Settings,
    lib: Library,
    *,
    on_update: UpdateFn | None = None,
    on_proc: Callable | None = None,
    resummarize: bool = False,
) -> dict[str, Any]:
    brief = lib.get_brief(brief_id)
    if not brief:
        raise KeyError(brief_id)
    started = time.monotonic()

    def update(**fields: Any) -> None:
        nonlocal brief
        brief = lib.upsert_brief({**brief, **fields})
        if on_update:
            on_update(brief)

    def progress(p: dict[str, Any]) -> None:
        stage = p.get("stage") or brief.get("stage")
        lo, hi = BANDS.get(stage, (0, 100))
        pct = p.get("percent")
        overall = brief.get("percent") if pct is None else lo + (hi - lo) * min(100.0, float(pct)) / 100
        update(stage=stage, percent=round(overall or 0, 1), message=MESSAGES.get(stage, ""), detail=p.get("detail"))

    try:
        update(status="running", error=None)
        if not brief.get("folder"):
            update(stage="resolving", percent=1, message=MESSAGES["resolving"], detail=None)
            meta = media.probe_url(brief["url"])
            folder = make_project_dir(settings.briefs_dir, title=meta["title"], media_id=meta["id"],
                                      show_name=meta["uploader"])
            update(title=clean_title(meta["title"]), uploader=meta["uploader"], duration=meta["duration"],
                   url=meta["webpage_url"], folder=str(folder), published=meta["published"],
                   description=meta["description"])
        folder = Path(brief["folder"])
        a = artifacts(folder)

        # YouTube captions first (seconds, no audio needed); Whisper when there are none.
        if not a["transcript_json"].is_file() and settings.transcript_source != "whisper":
            update(stage="captions", percent=4, message="Fetching YouTube captions…", detail=None)
            label = media.fetch_youtube_captions(brief["url"], a["transcript_json"])
            if label:
                update(transcript_source=label)
            elif settings.transcript_source == "captions":
                raise RuntimeError("No English captions on this video (TRANSCRIPT_SOURCE=captions).")

        if not a["transcript_json"].is_file():
            if not a["audio"].is_file():
                progress({"stage": "downloading", "percent": 0})
                media.download_audio(brief["url"], a["audio"], expected_duration=brief.get("duration"),
                                     on_progress=progress, on_proc=on_proc)
            progress({"stage": "transcribing", "percent": 0})
            t0 = time.monotonic()
            media.transcribe(a["audio"], model=brief.get("whisper_model") or settings.whisper_model,
                             on_progress=progress, on_proc=on_proc)
            update(stt_seconds=round(time.monotonic() - t0, 1), transcript_source="whisper")

        if resummarize or not a["brief"].is_file():
            if resummarize:
                a["brief"].unlink(missing_ok=True)
            progress({"stage": "condensing" if settings.mode == "chaptered" else "synthesizing", "percent": 0})
            stats = summarize.run(
                transcript_json=a["transcript_json"], folder=folder, settings=settings,
                title=brief.get("title"), uploader=brief.get("uploader"), duration_s=brief.get("duration"),
                description=brief.get("description"), meta_line=meta_line(brief),
                on_progress=progress, on_proc=on_proc, reuse_condensed=not resummarize,
            )
            update(llm_model=settings.llm_model, mode=settings.mode, llm_stats=stats)
            (folder / "meta.json").write_text(json.dumps(brief, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        update(status="ready", stage="done", percent=100, message="Ready", detail=None,
               brief_path=str(a["brief"]), total_seconds=round(time.monotonic() - started, 1))
    except Exception as exc:  # noqa: BLE001 — surface any stage failure to the UI/CLI
        update(status="error", stage="error", error=str(exc), message=str(exc)[:300])
        raise
    return brief

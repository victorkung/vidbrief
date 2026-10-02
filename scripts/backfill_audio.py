#!/usr/bin/env python3
"""Record audio (brief.mp3) for finished briefs that don't have it yet.

Safe while the app is running: each recording waits for the machine-wide model slot.

  .venv/bin/python scripts/backfill_audio.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vidbrief import pipeline  # noqa: E402
from vidbrief.config import load_settings  # noqa: E402


def main() -> None:
    settings = load_settings()
    lib = pipeline.library(settings)
    for row in lib.list_briefs():
        if row.get("status") != "ready" or not row.get("folder"):
            continue
        folder = Path(row["folder"])
        a = pipeline.artifacts(folder)
        if not a["brief"].is_file() or a["brief_audio"].is_file():
            continue
        t0 = time.monotonic()
        ok = pipeline.voice(row, folder, settings, update=lambda **f: lib.update(row["id"], **f))
        fresh = lib.get_brief(row["id"]) or {}
        if ok:
            size = a["brief_audio"].stat().st_size / 1e6
            print(f"{fresh.get('audio_seconds', 0) / 60:4.1f} min audio · {time.monotonic() - t0:4.0f}s · "
                  f"{size:.1f} MB · {row['title'][:60]}")
        else:
            print(f"failed · {row['title'][:60]} · {fresh.get('audio_error')}")


if __name__ == "__main__":
    main()

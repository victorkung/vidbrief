#!/usr/bin/env python3
"""Fill in publish date and description for briefs created before VidBrief stored them.

  .venv/bin/python scripts/backfill_meta.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vidbrief import media, pipeline  # noqa: E402
from vidbrief.config import load_settings  # noqa: E402


def main() -> None:
    settings = load_settings()
    lib = pipeline.library(settings)
    for row in lib.list_briefs():
        if row.get("published") and row.get("description"):
            continue
        try:
            meta = media.probe_url(row["url"])
        except RuntimeError as exc:
            print(f"skip {row['title'][:50]}: {exc}"[:160])
            continue
        lib.upsert_brief({**row, "published": meta["published"], "description": meta["description"]})
        print(f"{meta['published']}  {row['title'][:60]}")


if __name__ == "__main__":
    main()

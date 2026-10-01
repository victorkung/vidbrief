#!/usr/bin/env python3
"""Compare summarizer models on videos you have already transcribed.

Runs the full summarize stage (condense → chapters → chapter → overview, or single pass) per model and
writes each result to briefs/<video>/eval/<model>/brief.md, then prints a table.

  .venv/bin/python scripts/eval.py --models mlx-community/Qwen3.5-9B-MLX-4bit mlx-community/gemma-4-e4b-it-4bit
  .venv/bin/python scripts/eval.py --models <id> --videos "2026-10-01 Y Combinator"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vidbrief import pipeline, summarize  # noqa: E402
from vidbrief.config import MODES, load_settings  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--videos", nargs="*", help="Folder names under briefs/ (default: all transcribed)")
    parser.add_argument("--mode", choices=MODES)
    parser.add_argument("--reuse-condensed", action="store_true",
                        help="Reuse each model's condensed.md from a previous run (re-runs chapters onward)")
    args = parser.parse_args()

    settings = load_settings()
    if args.mode:
        settings.mode = args.mode
    folders = [settings.briefs_dir / v for v in args.videos] if args.videos else sorted(
        p for p in settings.briefs_dir.iterdir() if (p / "source.transcript.json").is_file()
    )
    by_folder = {Path(b["folder"]).resolve(): b for b in pipeline.library(settings).list_briefs() if b.get("folder")}
    rows = []
    for folder in folders:
        meta = by_folder.get(folder.resolve())
        if meta is None:
            meta_path = folder / "meta.json"
            meta = json.loads(meta_path.read_text()) if meta_path.is_file() else {}
        for model in args.models:
            out = folder / "eval" / model.split("/")[-1] / settings.mode
            out.mkdir(parents=True, exist_ok=True)
            settings.llm_model = model
            print(f"→ {folder.name} · {model} · {settings.mode}", file=sys.stderr, flush=True)
            try:
                s = summarize.run(
                    transcript_json=folder / "source.transcript.json", folder=out, settings=settings,
                    title=meta.get("title"), uploader=meta.get("uploader"), duration_s=meta.get("duration"),
                    description=meta.get("description"), meta_line=pipeline.meta_line(meta), reuse_condensed=args.reuse_condensed,
                )
            except Exception as exc:  # noqa: BLE001
                rows.append((folder.name, model, "ERROR", str(exc)[:80]))
                continue
            secs = s["seconds"]
            peak = max((v.get("peak_memory_gb") or 0) for v in s.values() if isinstance(v, dict))
            words = len((out / "brief.md").read_text().split())
            rows.append((folder.name, model.split("/")[-1], "ok" if s["valid"] else "INVALID",
                         f"{secs:.0f}s · {peak} GB · {words}/{s['target_words']} words · coverage {s.get('coverage')} · "
                         f"chapters {(s.get('chapters') or {}).get('chapters', '-')} {' '.join(s['missing'])}"))
    print()
    for r in rows:
        print(" | ".join(r))


if __name__ == "__main__":
    main()

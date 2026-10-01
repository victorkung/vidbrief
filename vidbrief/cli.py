"""vidbrief <url> — download, transcribe, and summarize a video locally."""

from __future__ import annotations

import argparse
import os
import sys

from . import pipeline
from .config import MODES, load_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vidbrief", description=__doc__)
    parser.add_argument("url", help="YouTube watch URL or X status URL")
    parser.add_argument("--model", help="LLM (HF repo id or local path); overrides LLM_MODEL")
    parser.add_argument("--whisper", help="Whisper model: small | medium | turbo | …")
    parser.add_argument("--mode", choices=MODES, help="two_pass (default) or single_pass")
    args = parser.parse_args(argv)

    for flag, env in ((args.model, "LLM_MODEL"), (args.whisper, "WHISPER_MODEL"), (args.mode, "SUMMARY_MODE")):
        if flag:
            os.environ[env] = flag
    settings = load_settings()
    lib = pipeline.library(settings)
    try:
        brief = pipeline.create(args.url, settings, lib)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    last = {"line": ""}

    def show(b: dict) -> None:
        line = f"[{b.get('percent', 0):5.1f}%] {b.get('message') or ''} {b.get('detail') or ''}".rstrip()
        if line != last["line"]:
            last["line"] = line
            print("\r\033[K" + line[:160], end="", file=sys.stderr, flush=True)

    try:
        brief = pipeline.process(brief["id"], settings, lib, on_update=show)
    except Exception as exc:  # noqa: BLE001
        print(f"\nerror: {exc}", file=sys.stderr)
        return 1
    print(file=sys.stderr)
    stats = brief.get("llm_stats") or {}
    if not stats.get("valid", True):
        print(f"warning: brief is missing {', '.join(stats.get('missing') or [])}", file=sys.stderr)
    print(brief["brief_path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

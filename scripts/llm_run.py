#!/usr/bin/env python3
"""Run one or more chat completions on a local MLX model, then exit.

Runs as a subprocess so the model's memory is released when the stage ends
(Whisper and the LLM never hold RAM at the same time).

Input (stdin JSON):
  {"model": "<hf id or path>", "jobs": [{"system": str, "user": str,
   "max_tokens": int, "temperature": float}]}

Output lines (stdout):
  PROGRESS_JSON:{"job": i, "jobs": n, "tokens": k, "max_tokens": m}
  RESULT_JSON:{"job": i, "content": str, "prompt_tokens": ..., ...}
  TIMING_JSON:{"load_s": ..., "peak_memory_gb": ...}

Smoke test:
  .venv/bin/python scripts/llm_run.py --prompt "Say hello in five words."
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vidbrief.config import load_settings  # noqa: E402

_THINK = re.compile(r"<think>.*?</think>\s*", re.S)


def emit(tag: str, payload: dict) -> None:
    print(f"{tag}:{json.dumps(payload, ensure_ascii=False)}", flush=True)


def build_prompt(tokenizer, system: str, user: str) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})
    try:
        return tokenizer.apply_chat_template(
            messages, add_generation_prompt=True, tokenize=False, enable_thinking=False
        )
    except TypeError:
        return tokenizer.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)


def run(model_id: str, jobs: list[dict]) -> None:
    import mlx.core as mx
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler

    t0 = time.monotonic()
    model, tokenizer = load(model_id)
    load_s = time.monotonic() - t0

    for i, job in enumerate(jobs):
        max_tokens = int(job.get("max_tokens") or 2048)
        sampler = make_sampler(temp=float(job.get("temperature") or 0.0))
        prompt = build_prompt(tokenizer, job.get("system") or "", job["user"])
        started = time.monotonic()
        text = ""
        last = None
        last_emit = 0.0
        for resp in stream_generate(model, tokenizer, prompt, max_tokens=max_tokens, sampler=sampler):
            text += resp.text
            last = resp
            now = time.monotonic()
            if now - last_emit > 1.0:
                last_emit = now
                emit(
                    "PROGRESS_JSON",
                    {"job": i, "jobs": len(jobs), "tokens": resp.generation_tokens, "max_tokens": max_tokens},
                )
        content = _THINK.sub("", text).strip()
        emit(
            "RESULT_JSON",
            {
                "job": i,
                "content": content,
                "prompt_tokens": last.prompt_tokens if last else 0,
                "generation_tokens": last.generation_tokens if last else 0,
                "prompt_tps": round(last.prompt_tps, 1) if last else 0,
                "generation_tps": round(last.generation_tps, 1) if last else 0,
                "finish_reason": (last.finish_reason if last else None) or "",
                "seconds": round(time.monotonic() - started, 2),
            },
        )
        mx.clear_cache()

    emit(
        "TIMING_JSON",
        {"model": model_id, "load_s": round(load_s, 2), "peak_memory_gb": round(mx.get_peak_memory() / 1e9, 2)},
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", help="HF repo id or local path (default: LLM_MODEL)")
    parser.add_argument("--prompt", help="One-off user prompt (otherwise read jobs JSON from stdin)")
    parser.add_argument("--max-tokens", type=int, default=256)
    args = parser.parse_args()

    settings = load_settings()
    if args.prompt:
        payload = {"jobs": [{"system": "", "user": args.prompt, "max_tokens": args.max_tokens}]}
    else:
        payload = json.load(sys.stdin)
    model_id = args.model or payload.get("model") or settings.llm_model
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    run(model_id, payload["jobs"])


if __name__ == "__main__":
    main()

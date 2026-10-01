"""Local LLM via scripts/llm_run.py (mlx-lm in a subprocess)."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Any, Callable

from .config import ROOT

LLM_RUN = ROOT / "scripts" / "llm_run.py"


@dataclass
class LlmResult:
    content: str
    prompt_tokens: int
    generation_tokens: int
    generation_tps: float
    finish_reason: str
    seconds: float


def run_jobs(
    jobs: list[dict[str, Any]],
    *,
    model: str,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
    on_proc: Callable[[subprocess.Popen], None] | None = None,
) -> tuple[list[LlmResult], dict[str, Any]]:
    """Run jobs in one model load. Returns (results in job order, timing)."""
    proc = subprocess.Popen(
        [sys.executable, str(LLM_RUN)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if on_proc:
        on_proc(proc)
    assert proc.stdin and proc.stdout
    proc.stdin.write(json.dumps({"model": model, "jobs": jobs}))
    proc.stdin.close()

    results: dict[int, LlmResult] = {}
    timing: dict[str, Any] = {}
    tail: list[str] = []
    for raw in proc.stdout:
        line = raw.rstrip("\n")
        tag, _, body = line.partition(":")
        if tag == "PROGRESS_JSON" and on_progress:
            on_progress(json.loads(body))
        elif tag == "RESULT_JSON":
            r = json.loads(body)
            results[r["job"]] = LlmResult(
                content=r["content"],
                prompt_tokens=r["prompt_tokens"],
                generation_tokens=r["generation_tokens"],
                generation_tps=r["generation_tps"],
                finish_reason=r["finish_reason"],
                seconds=r["seconds"],
            )
        elif tag == "TIMING_JSON":
            timing = json.loads(body)
        elif line.strip():
            tail = (tail + [line])[-15:]
    code = proc.wait()
    if code != 0 or len(results) != len(jobs):
        if code < 0:
            raise RuntimeError("Summarizer was cancelled")
        raise RuntimeError("Local LLM failed:\n" + "\n".join(tail)[-1200:])
    return [results[i] for i in range(len(jobs))], timing

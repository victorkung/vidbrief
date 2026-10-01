"""Transcript → brief. two_pass: chunked extract → synthesize. single_pass: one call."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import chunking, llm, prompts
from .config import Settings

ProgressFn = Callable[[dict[str, Any]], None]


def _ledger(settings: Settings, row: dict[str, Any]) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    row = {"at": datetime.now(timezone.utc).isoformat(), **row}
    with (settings.data_dir / "ledger.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _stats(results: list[llm.LlmResult], timing: dict[str, Any]) -> dict[str, Any]:
    gen = sum(r.generation_tokens for r in results)
    secs = sum(r.seconds for r in results)
    return {
        "calls": len(results),
        "prompt_tokens": sum(r.prompt_tokens for r in results),
        "generation_tokens": gen,
        "seconds": round(secs + float(timing.get("load_s") or 0), 1),
        "generation_tps": round(gen / secs, 1) if secs else 0,
        "peak_memory_gb": timing.get("peak_memory_gb"),
        "model": timing.get("model"),
    }


def _write_brief(
    *,
    system: str,
    user: str,
    settings: Settings,
    on_progress: ProgressFn | None,
    on_proc: Callable | None,
    stage: str,
) -> tuple[str, dict[str, Any]]:
    """One synthesis call, validated; one structured retry if sections are missing."""
    job = {"system": system, "user": user, "max_tokens": settings.synth_max_tokens, "temperature": settings.synth_temperature}

    def prog(p: dict[str, Any]) -> None:
        if on_progress:
            on_progress({"stage": stage, "percent": min(99, 100 * p["tokens"] / max(1, p["max_tokens"]) * 1.4),
                         "detail": f"{p['tokens']} tokens written"})

    [res], timing = llm.run_jobs([job], model=settings.llm_model, on_progress=prog, on_proc=on_proc)
    results = [res]
    brief = res.content
    ok, missing = prompts.validate_summary_structure(brief)
    if not ok or res.finish_reason == "length":
        if on_progress:
            on_progress({"stage": stage, "percent": None, "detail": "Retrying structure: " + ", ".join(missing[:3])})
        retry_job = dict(job, system=prompts.quality_retry_system(system, missing or ["truncated output"]))
        [retry], timing2 = llm.run_jobs([retry_job], model=settings.llm_model, on_progress=prog, on_proc=on_proc)
        results.append(retry)
        timing = {**timing, "load_s": float(timing.get("load_s") or 0) + float(timing2.get("load_s") or 0)}
        retry_ok, retry_missing = prompts.validate_summary_structure(retry.content)
        better = len(retry_missing) < len(missing) or (len(retry_missing) == len(missing) and res.finish_reason == "length"
                                                       and retry.finish_reason != "length")
        if retry_ok or better:
            brief = retry.content
    return brief, _stats(results, timing)


def run(
    *,
    transcript_json: Path,
    folder: Path,
    settings: Settings,
    title: str | None,
    uploader: str | None,
    duration_s: float | None = None,
    on_progress: ProgressFn | None = None,
    on_proc: Callable | None = None,
    reuse_condensed: bool = True,
) -> dict[str, Any]:
    """Writes transcript.md, condensed.md (two_pass) and brief.md into `folder`."""
    paras = chunking.paragraphs(chunking.load_segments(transcript_json))
    if not paras:
        raise RuntimeError("Transcript is empty (no speech found).")
    transcript_md = chunking.render(paras)
    (folder / "transcript.md").write_text(transcript_md + "\n", encoding="utf-8")
    stats: dict[str, Any] = {"mode": settings.mode, "model": settings.llm_model}
    span_s = duration_s or paras[-1][0]
    sections = prompts.section_count(span_s)

    if settings.mode == "single_pass":
        brief, s = _write_brief(
            system=prompts.load_prompt("single_pass"),
            user=prompts.single_pass_user_prompt(title=title, uploader=uploader, transcript=transcript_md,
                                                 sections=sections, duration_s=span_s),
            settings=settings, on_progress=on_progress, on_proc=on_proc, stage="synthesizing",
        )
        stats["synthesize"] = s
        _ledger(settings, {"folder": folder.name, "stage": "single_pass", **s})
    else:
        condensed_path = folder / "condensed.md"
        if reuse_condensed and condensed_path.is_file() and condensed_path.stat().st_size > 0:
            condensed = condensed_path.read_text(encoding="utf-8")
        else:
            wins = chunking.windows(paras, max_tokens=settings.chunk_tokens)
            system = prompts.load_prompt("extract")
            jobs = [
                {
                    "system": system,
                    "user": prompts.extract_user_prompt(transcript=chunking.render(w), part=i + 1, parts=len(wins)),
                    "max_tokens": settings.extract_max_tokens,
                    "temperature": settings.extract_temperature,
                }
                for i, w in enumerate(wins)
            ]

            def prog(p: dict[str, Any]) -> None:
                if on_progress:
                    frac = (p["job"] + min(1.0, p["tokens"] / max(1, p["max_tokens"]) * 1.6)) / p["jobs"]
                    on_progress({"stage": "extracting", "percent": min(99, 100 * frac),
                                 "detail": f"part {p['job'] + 1}/{p['jobs']} · {p['tokens']} tokens"})

            results, timing = llm.run_jobs(jobs, model=settings.llm_model, on_progress=prog, on_proc=on_proc)
            condensed = "\n\n".join(r.content for r in results).strip()
            condensed_path.write_text(condensed + "\n", encoding="utf-8")
            s = _stats(results, timing)
            s["windows"] = len(wins)
            s["truncated_windows"] = sum(1 for r in results if r.finish_reason == "length")
            stats["extract"] = s
            _ledger(settings, {"folder": folder.name, "stage": "extract", **s})

        brief, s = _write_brief(
            system=prompts.load_prompt("synthesize"),
            user=prompts.synthesize_user_prompt(title=title, uploader=uploader, condensed=condensed,
                                                sections=sections, duration_s=span_s),
            settings=settings, on_progress=on_progress, on_proc=on_proc, stage="synthesizing",
        )
        stats["synthesize"] = s
        _ledger(settings, {"folder": folder.name, "stage": "synthesize", **s})

    ok, missing = prompts.validate_summary_structure(brief)
    stats["coverage"] = prompts.coverage(brief, span_s)
    stats["valid"] = ok
    stats["missing"] = missing
    (folder / "brief.md").write_text(brief.strip() + "\n", encoding="utf-8")
    return stats

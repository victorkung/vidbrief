"""Transcript → brief.

chaptered (default), four short steps so a small local model never has to juggle much:
  1. condense  — each ~7k-token transcript window → one [HH:MM:SS] line per key point
                 (windows run independently, so the whole video is always covered).
  2. chapters  — one call groups the condensed points into 3–6 topic-based chapters
                 ("[HH:MM:SS] Title" starts). Code checks order, count and balance.
  3. chapter   — one call per chapter writes its theme + 3–4 timestamped bullets from only
                 the condensed points inside that chapter's time range.
  4. overview  — one call writes Executive Summary, Speaker & Guests, Key Takeaways from
                 the finished chapters plus the opening minutes.
  Code assembles the brief in PodBrief's order.

single_pass: the whole transcript in one call (prompts/single_pass.md). Fine for short videos.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import chunking, llm, prompts
from .config import Settings

ProgressFn = Callable[[dict[str, Any]], None]
OPENING_S = 180  # transcript the overview sees for "who is speaking and why"


def _ledger(settings: Settings, row: dict[str, Any]) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    row = {"at": datetime.now(timezone.utc).isoformat(), **row}
    with (settings.data_dir / "ledger.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _rel(folder: Path, settings: Settings) -> str:
    try:
        return str(folder.resolve().relative_to(settings.briefs_dir.resolve()))
    except ValueError:
        return folder.name


def _stats(results: list[llm.LlmResult], timings: list[dict[str, Any]]) -> dict[str, Any]:
    gen = sum(r.generation_tokens for r in results)
    secs = sum(r.seconds for r in results)
    return {
        "calls": len(results),
        "prompt_tokens": sum(r.prompt_tokens for r in results),
        "generation_tokens": gen,
        "seconds": round(secs + sum(float(t.get("load_s") or 0) for t in timings), 1),
        "generation_tps": round(gen / secs, 1) if secs else 0,
        "peak_memory_gb": max((t.get("peak_memory_gb") or 0) for t in timings) if timings else None,
        "model": timings[0].get("model") if timings else None,
    }


def _progress(on_progress: ProgressFn | None, stage: str, label: str) -> Callable[[dict[str, Any]], None]:
    def prog(p: dict[str, Any]) -> None:
        if on_progress:
            frac = (p["job"] + min(1.0, p["tokens"] / max(1, p["max_tokens"]) * 1.5)) / p["jobs"]
            detail = f"{label} {p['job'] + 1}/{p['jobs']}" if p["jobs"] > 1 else label
            on_progress({"stage": stage, "percent": min(99, 100 * frac), "detail": f"{detail} · {p['tokens']} tokens"})
    return prog


def condense(
    paras: list[tuple[float, str]],
    *,
    settings: Settings,
    on_progress: ProgressFn | None,
    on_proc: Callable | None,
) -> tuple[list[tuple[int, str]], dict[str, Any]]:
    wins = chunking.windows(paras, max_tokens=settings.chunk_tokens)
    system = prompts.load_prompt("condense")
    jobs = [
        {
            "system": system,
            "user": prompts.condense_user_prompt(transcript=chunking.render(w), part=i + 1, parts=len(wins)),
            "max_tokens": settings.condense_max_tokens,
            "temperature": settings.condense_temperature,
        }
        for i, w in enumerate(wins)
    ]
    results, timing = llm.run_jobs(jobs, model=settings.llm_model, on_proc=on_proc,
                                   on_progress=_progress(on_progress, "condensing", "part"))
    points: dict[int, str] = {}
    for r in results:
        for t, text in prompts.parse_points(r.content):
            points.setdefault(t, text)  # window overlap repeats a paragraph; keep the first
    if not points:
        raise RuntimeError("Condense step produced no timestamped points.")
    stats = _stats(results, [timing])
    stats.update(windows=len(wins), points=len(points), truncated=sum(r.finish_reason == "length" for r in results))
    return sorted(points.items()), stats


def plan_chapters(
    points: list[tuple[int, str]],
    *,
    span_s: float,
    title: str | None,
    settings: Settings,
    on_progress: ProgressFn | None,
    on_proc: Callable | None,
) -> tuple[list[tuple[int, str]], dict[str, Any]]:
    target = prompts.section_count(span_s)
    system = prompts.load_prompt("chapters")
    job = {
        "system": system,
        "user": prompts.chapters_user_prompt(title=title, condensed=prompts.render_points(points),
                                             duration_s=span_s, target=target),
        "max_tokens": settings.chapters_max_tokens,
        "temperature": settings.chapters_temperature,
    }
    prog = _progress(on_progress, "chapters", "planning chapters")
    [res], timing = llm.run_jobs([job], model=settings.llm_model, on_proc=on_proc, on_progress=prog)
    results, timings = [res], [timing]
    starts = prompts.parse_outline(res.content, span_s)
    problems = prompts.outline_problems(starts, span_s, target)
    if problems:
        retry_job = dict(job, system=prompts.quality_retry_system(system, problems),
                         temperature=settings.chapters_temperature + 0.2)
        [retry], t2 = llm.run_jobs([retry_job], model=settings.llm_model, on_proc=on_proc, on_progress=prog)
        results.append(retry)
        timings.append(t2)
        again = prompts.parse_outline(retry.content, span_s)
        if len(prompts.outline_problems(again, span_s, target)) < len(problems) or len(starts) < 3:
            starts = again
    if len(starts) < 3:
        raise RuntimeError("Could not plan chapters (model returned fewer than 3).")
    stats = _stats(results, timings)
    stats["chapters"] = len(starts)
    return starts, stats


def write_chapters(
    points: list[tuple[int, str]],
    starts: list[tuple[int, str]],
    *,
    span_s: float,
    title: str | None,
    settings: Settings,
    on_progress: ProgressFn | None,
    on_proc: Callable | None,
) -> tuple[list[str], dict[str, Any]]:
    bounds = [t for t, _ in starts] + [span_s]
    ranges = list(zip(bounds, bounds[1:]))
    system = prompts.load_prompt("chapter")

    def job(i: int, sys_prompt: str, temperature: float) -> dict[str, Any]:
        lo, hi = ranges[i]
        inside = [p for p in points if lo <= p[0] < hi] or [min(points, key=lambda p: abs(p[0] - lo))]
        return {
            "system": sys_prompt,
            "user": prompts.chapter_user_prompt(
                title=starts[i][1], number=i + 1, start=chunking.format_hms(lo), end=chunking.format_hms(hi),
                points=prompts.render_points(inside), video_title=title,
            ),
            "max_tokens": settings.chapter_max_tokens,
            "temperature": temperature,
        }

    jobs = [job(i, system, settings.chapter_temperature) for i in range(len(starts))]
    results, timing = llm.run_jobs(jobs, model=settings.llm_model, on_proc=on_proc,
                                   on_progress=_progress(on_progress, "writing", "chapter"))
    all_results, timings = list(results), [timing]
    parsed = [prompts.parse_chapter(r.content) for r in results]
    failed = [i for i, p in enumerate(parsed) if p is None]
    if failed:
        retry_sys = prompts.quality_retry_system(system, ["THEME line and 3-4 timestamped bullets"])
        retries, t2 = llm.run_jobs([job(i, retry_sys, settings.chapter_temperature + 0.2) for i in failed],
                                   model=settings.llm_model, on_proc=on_proc,
                                   on_progress=_progress(on_progress, "writing", "retrying chapter"))
        all_results += retries
        timings.append(t2)
        for i, r in zip(failed, retries):
            parsed[i] = prompts.parse_chapter(r.content) or {
                "theme": "", "bullets": [prompts.normalize_bullet(ln) for ln in results[i].content.splitlines()
                                         if ln.strip()][:4] or ["(no summary produced)"]}

    sections_md = [prompts.render_section(i + 1, {"title": starts[i][1], **sec}) for i, sec in enumerate(parsed)]
    stats = _stats(all_results, timings)
    stats["retried"] = len(failed)
    return sections_md, stats


def write_overview(
    paras: list[tuple[float, str]],
    sections_md: list[str],
    *,
    title: str | None,
    uploader: str | None,
    settings: Settings,
    on_progress: ProgressFn | None,
    on_proc: Callable | None,
) -> tuple[dict[str, str], dict[str, Any]]:
    opening = chunking.render([p for p in paras if p[0] < OPENING_S] or paras[:1])
    system = prompts.load_prompt("overview")
    job = {
        "system": system,
        "user": prompts.overview_user_prompt(title=title, uploader=uploader, opening=opening,
                                             chapters="\n\n".join(sections_md)),
        "max_tokens": settings.overview_max_tokens,
        "temperature": settings.overview_temperature,
    }
    prog = _progress(on_progress, "synthesizing", "summary & takeaways")
    [res], timing = llm.run_jobs([job], model=settings.llm_model, on_proc=on_proc, on_progress=prog)
    results, timings = [res], [timing]
    overview = prompts.split_overview(res.content)
    if len(overview) < len(prompts.OVERVIEW_KEYS):
        missing = [h for k, h in prompts.OVERVIEW_KEYS.items() if k not in overview]
        retry_job = dict(job, system=prompts.quality_retry_system(system, missing))
        [retry], t2 = llm.run_jobs([retry_job], model=settings.llm_model, on_proc=on_proc, on_progress=prog)
        results.append(retry)
        timings.append(t2)
        again = prompts.split_overview(retry.content)
        overview = {**again, **overview} if len(overview) >= len(again) else {**overview, **again}
    return overview, _stats(results, timings)


def write_single_pass(
    paras: list[tuple[float, str]],
    *,
    span_s: float,
    title: str | None,
    uploader: str | None,
    settings: Settings,
    on_progress: ProgressFn | None,
    on_proc: Callable | None,
) -> tuple[str, dict[str, Any]]:
    system = prompts.load_prompt("single_pass")
    job = {
        "system": system,
        "user": prompts.single_pass_user_prompt(title=title, uploader=uploader, transcript=chunking.render(paras),
                                                sections=prompts.section_count(span_s)),
        "max_tokens": settings.single_pass_max_tokens,
        "temperature": settings.overview_temperature,
    }
    prog = _progress(on_progress, "synthesizing", "brief")
    [res], timing = llm.run_jobs([job], model=settings.llm_model, on_proc=on_proc, on_progress=prog)
    results, timings = [res], [timing]
    brief = res.content
    ok, missing = prompts.validate_summary_structure(brief)
    if not ok:
        retry_job = dict(job, system=prompts.quality_retry_system(system, missing))
        [retry], t2 = llm.run_jobs([retry_job], model=settings.llm_model, on_proc=on_proc, on_progress=prog)
        results.append(retry)
        timings.append(t2)
        if len(prompts.validate_summary_structure(retry.content)[1]) < len(missing):
            brief = retry.content
    # Normalize bullet timestamps (**00:01:00** → [00:01:00]) the same way chaptered mode does.
    lines = [("- " + prompts.normalize_bullet(ln)) if prompts._BULLET.match(ln) else ln for ln in brief.splitlines()]
    return "\n".join(lines).strip() + "\n", _stats(results, timings)


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
    reuse_condensed: bool = False,
) -> dict[str, Any]:
    """Writes transcript.md, condensed.md + sections.md (chaptered) and brief.md into `folder`."""
    paras = chunking.paragraphs(chunking.load_segments(transcript_json))
    if not paras:
        raise RuntimeError("Transcript is empty (no speech found).")
    (folder / "transcript.md").write_text(chunking.render(paras) + "\n", encoding="utf-8")
    span_s = float(duration_s or paras[-1][0] + 60)
    stats: dict[str, Any] = {"mode": settings.mode, "model": settings.llm_model}
    common = {"settings": settings, "on_progress": on_progress, "on_proc": on_proc}

    if settings.mode == "single_pass":
        brief, s = write_single_pass(paras, span_s=span_s, title=title, uploader=uploader, **common)
        stats["single_pass"] = s
        _ledger(settings, {"folder": _rel(folder, settings), "stage": "single_pass", **s})
    else:
        condensed_path = folder / "condensed.md"
        if reuse_condensed and condensed_path.is_file():
            points = prompts.parse_points(condensed_path.read_text(encoding="utf-8"))
        else:
            points, s = condense(paras, **common)
            condensed_path.write_text(prompts.render_points(points) + "\n", encoding="utf-8")
            stats["condense"] = s
            _ledger(settings, {"folder": _rel(folder, settings), "stage": "condense", **s})

        starts, s = plan_chapters(points, span_s=span_s, title=title, **common)
        stats["chapters"] = s
        _ledger(settings, {"folder": _rel(folder, settings), "stage": "chapters", **s})

        sections_md, s = write_chapters(points, starts, span_s=span_s, title=title, **common)
        (folder / "sections.md").write_text("\n\n".join(sections_md) + "\n", encoding="utf-8")
        stats["write"] = s
        _ledger(settings, {"folder": _rel(folder, settings), "stage": "write", **s})

        overview, s = write_overview(paras, sections_md, title=title, uploader=uploader, **common)
        stats["overview"] = s
        _ledger(settings, {"folder": _rel(folder, settings), "stage": "overview", **s})
        brief = prompts.assemble_brief(overview, sections_md)

    ok, missing = prompts.validate_summary_structure(brief)
    stats.update(valid=ok, missing=missing, coverage=prompts.coverage(brief, span_s),
                 words=len(brief.split()),
                 seconds=round(sum((stats.get(k) or {}).get("seconds", 0)
                                   for k in ("condense", "chapters", "write", "overview", "single_pass")), 1))
    (folder / "brief.md").write_text(brief.strip() + "\n", encoding="utf-8")
    return stats

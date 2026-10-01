"""Prompt files (prompts/*.md, overridable in prompts/private/), builders, parsers, validator.

chaptered flow (see summarize.py): condense.md per transcript window → chapters.md plans
topic-based chapters → chapter.md writes each chapter from its condensed points →
overview.md writes the overview, context and takeaways. Code assembles the brief.
"""

from __future__ import annotations

import re
from pathlib import Path

from .config import ROOT

PROMPTS = ROOT / "prompts"
NAMES = ("condense", "chapters", "chapter", "overview", "single_pass")


def prompt_path(name: str, *, prompts_dir: Path = PROMPTS) -> Path:
    private = prompts_dir / "private" / f"{name}.md"
    if private.is_file():
        return private
    public = prompts_dir / f"{name}.md"
    if public.is_file():
        return public
    raise FileNotFoundError(f"no prompt file for '{name}' in {prompts_dir}")


def load_prompt(name: str, *, prompts_dir: Path = PROMPTS) -> str:
    return prompt_path(name, prompts_dir=prompts_dir).read_text(encoding="utf-8").strip()


def section_count(duration_s: float | None) -> int:
    """Target chapter count, matching PodBrief: 18 min → 3, 37 → 4, 65 → 5, 88+ → 6."""
    minutes = (duration_s or 0) / 60
    return max(3, min(6, round(2.6 + minutes / 30)))


def _source_line(title: str | None, uploader: str | None) -> str:
    bits = [b for b in (title, uploader) if b]
    return ("VIDEO: " + " — ".join(bits) + "\n\n") if bits else ""


def condense_user_prompt(*, transcript: str, part: int, parts: int) -> str:
    scope = f"Part {part} of {parts} of the transcript" if parts > 1 else "Transcript"
    return f"{scope}:\n\n{transcript}\n\n---\nWrite the key points now, one [HH:MM:SS] line each."


def chapters_user_prompt(*, title: str | None, condensed: str, duration_s: float, target: int) -> str:
    return (
        f"{_source_line(title, None)}Video length: {_hms(duration_s)}\n\nCONDENSED TRANSCRIPT:\n{condensed}\n\n"
        f"---\nList the chapters now: about {target} (between {max(3, target - 1)} and {target + 1}), "
        "one '[HH:MM:SS] Title' line each, starting at [00:00:00]."
    )


def chapter_user_prompt(*, title: str, number: int, start: str, end: str, points: str,
                        video_title: str | None = None) -> str:
    return (
        f"{_source_line(video_title, None)}CHAPTER {number}: {title} ({start}–{end})\n\nKEY POINTS:\n{points}\n\n"
        "---\nWrite INTRO and 3-4 timestamped bullets for this chapter now."
    )


def overview_user_prompt(*, title: str | None, uploader: str | None, opening: str, chapters: str) -> str:
    return (
        f"{_source_line(title, uploader)}OPENING MINUTES (for who is speaking and why):\n{opening}\n\n"
        f"CHAPTERS:\n{chapters}\n\n"
        "---\nWrite ## High-Level Overview, ## Context, and ## Key Takeaways now."
    )


def single_pass_user_prompt(*, title: str | None, uploader: str | None, transcript: str, sections: int) -> str:
    return (
        f"{_source_line(title, uploader)}Transcript:\n{transcript}\n\n"
        f"---\nWrite the brief now, with exactly {sections} chapters spread evenly across the video."
    )


# ── Parsing ────────────────────────────────────────────────────────────────

# [00:01:00], **00:01:00**, **[00:01:00]**, 00:01:00 — at the start of a bullet.
_LEAD_TS = re.compile(r"^\s*(?:\*\*)?\[?(\d{1,2}:\d{2}(?::\d{2})?)\]?(?:\*\*)?[\s:\-–—]*")
_TS = re.compile(r"\[\d{1,2}:\d{2}(?::\d{2})?\]")
_BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")


def _hms(seconds: float) -> str:
    total = int(max(0, seconds))
    return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"


def _to_seconds(ts: str) -> int:
    return sum(int(x) * 60 ** i for i, x in enumerate(reversed(ts.split(":"))))


def normalize_bullet(text: str) -> str:
    """Strip the list marker and put any leading timestamp in [HH:MM:SS] form."""
    body = _BULLET.sub("", text).strip()
    m = _LEAD_TS.match(body)
    if m:
        body = f"[{_hms(_to_seconds(m.group(1)))}] {body[m.end():].strip()}"
    return body


def parse_points(text: str) -> list[tuple[int, str]]:
    """Lines that start with a timestamp → [(seconds, text)]. Used for condense and chapters replies."""
    out: list[tuple[int, str]] = []
    for raw in (text or "").splitlines():
        line = _BULLET.sub("", raw.strip())
        m = _LEAD_TS.match(line)
        if m and line[m.end():].strip():
            out.append((_to_seconds(m.group(1)), line[m.end():].strip().strip("*").strip()))
    return out


def render_points(points: list[tuple[int, str]]) -> str:
    return "\n".join(f"[{_hms(t)}] {text}" for t, text in points)


def parse_outline(text: str, duration_s: float) -> list[tuple[int, str]]:
    """chapters.md reply → sorted, de-duplicated chapter starts; first forced to 0."""
    seen: dict[int, str] = {}
    for t, title in parse_points(text):
        if t < duration_s and t not in seen:
            seen[t] = title.strip(" .\"'")
    starts = sorted(seen.items())
    if starts:
        starts[0] = (0, starts[0][1])
    return starts


def outline_problems(starts: list[tuple[int, str]], duration_s: float, target: int) -> list[str]:
    problems = []
    if not (3 <= len(starts) <= max(4, target + 2)):
        problems.append(f"{target} chapters (got {len(starts)})")
    bounds = [t for t, _ in starts] + [duration_s]
    longest = max((b - a for a, b in zip(bounds, bounds[1:])), default=0)
    if duration_s > 20 * 60 and longest > 0.5 * duration_s:
        problems.append("balanced chapters (one chapter covers over half the video)")
    return problems


def parse_chapter(text: str) -> dict | None:
    """chapter.md reply → {'intro', 'bullets'}. None when unusable (caller retries)."""
    intro: list[str] = []
    bullets: list[str] = []
    for raw in (text or "").splitlines():
        line = re.sub(r"^\**\s*(INTRO|THEME)\s*:\s*\**", "INTRO:", raw.strip(), flags=re.I)
        if line.startswith("INTRO:"):
            intro.append(line[6:].strip())
        elif _BULLET.match(line):
            bullets.append(normalize_bullet(line))
        elif line and not bullets and intro:
            intro.append(line)  # intro wrapped onto a second line
    bullets = [b for b in bullets if b]
    if len(bullets) < 2:
        return None
    return {"intro": " ".join(intro).strip("*_ "), "bullets": bullets[:4]}


def render_section(i: int, sec: dict) -> str:
    lines = [f"### Chapter {i}: {sec['title']}"]
    if sec.get("intro"):
        lines.append(sec["intro"])
    lines.append("")
    lines += [f"- {b}" for b in sec["bullets"]]
    return "\n".join(lines)


OVERVIEW_KEYS = {"overview": "High-Level Overview", "context": "Context", "key takeaway": "Key Takeaways"}


def split_overview(text: str) -> dict[str, str]:
    """Overview reply → {'overview': body, 'context': body, 'key takeaway': body}."""
    out: dict[str, str] = {}
    key = None
    buf: list[str] = []
    for line in (text or "").splitlines():
        if line.startswith("#"):
            if key:
                out[key] = "\n".join(buf).strip()
            name = line.lstrip("#").strip().lower()
            key = next((k for k in OVERVIEW_KEYS if k in name), name)
            buf = []
        elif key:
            buf.append(line)
    if key:
        out[key] = "\n".join(buf).strip()
    return {k: v for k, v in out.items() if k in OVERVIEW_KEYS and v}


def assemble_brief(overview: dict[str, str], sections_md: list[str]) -> str:
    """High-Level Overview, Context, chapters, Key Takeaways (PodBrief's layout)."""
    parts = [f"## {OVERVIEW_KEYS[k]}\n{overview[k]}" for k in ("overview", "context") if overview.get(k)]
    parts += sections_md
    if overview.get("key takeaway"):
        parts.append(f"## Key Takeaways\n{overview['key takeaway']}")
    return "\n\n".join(parts).strip() + "\n"


# ── Validation ─────────────────────────────────────────────────────────────

REQUIRED_H2 = {"overview": "High-Level Overview", "key takeaways": "Key Takeaways"}
MAX_SECTIONS = 7


def validate_summary_structure(summary: str) -> tuple[bool, list[str]]:
    """Same idea as PodBrief's validateSummaryStructure, plus timestamps and chapter count."""
    lines = (summary or "").splitlines()
    h2 = [ln.lower() for ln in lines if ln.startswith("## ")]
    h3 = [ln for ln in lines if ln.startswith("### ")]
    missing: list[str] = []
    for name, label in REQUIRED_H2.items():
        if not any(name in h for h in h2):
            missing.append(label)
    if len(h3) < 3:
        missing.append(f"3+ '### Chapter' sections (found {len(h3)})")
    elif len(h3) > MAX_SECTIONS:
        missing.append(f"at most {MAX_SECTIONS} chapters (found {len(h3)})")
    stamps = sum(1 for ln in lines if _BULLET.match(ln) and _LEAD_TS.match(_BULLET.sub("", ln)))
    if h3 and stamps < 2 * len(h3):
        missing.append(f"[HH:MM:SS] timestamps on chapter bullets (found {stamps})")
    return (not missing, missing)


def coverage(summary: str, duration_s: float | None) -> float | None:
    """Last timestamp in the brief as a fraction of the video length (tapering check)."""
    stamps = [_to_seconds(m.strip("[]")) for m in _TS.findall(summary or "")]
    if not stamps or not duration_s:
        return None
    return round(min(1.0, max(stamps) / duration_s), 2)


def quality_retry_system(system: str, missing: list[str]) -> str:
    return (
        f"Your previous reply was incomplete (missing: {', '.join(missing)}). "
        "Follow the format exactly this time.\n\n" + system
    )

"""Prompt files (prompts/*.md, overridable in prompts/private/), user-prompt builders, validator."""

from __future__ import annotations

import re
from pathlib import Path

from .config import ROOT

PROMPTS = ROOT / "prompts"
NAMES = ("extract", "synthesize", "single_pass")


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


def _source_line(title: str | None, uploader: str | None) -> str:
    bits = [b for b in (title, uploader) if b]
    return ("SOURCE: " + " — ".join(bits) + "\n\n") if bits else ""


def extract_user_prompt(*, transcript: str, part: int = 1, parts: int = 1) -> str:
    scope = f" (part {part} of {parts} of a longer video)" if parts > 1 else ""
    return (
        f"Transform this video transcript{scope} into a comprehensive AI Condensed Transcript:\n\n"
        f"{transcript}"
    )


def section_count(duration_s: float | None) -> int:
    """About one chapter per 15 minutes, 3–6 total."""
    minutes = (duration_s or 0) / 60
    return max(3, min(6, round(minutes / 15)))


def _hms(seconds: float) -> str:
    total = int(max(0, seconds))
    return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"


def section_spans(duration_s: float | None, sections: int) -> list[tuple[str, str]]:
    if not duration_s or duration_s <= 0:
        return []
    step = duration_s / sections
    return [(_hms(i * step), _hms((i + 1) * step)) for i in range(sections)]


def format_reminder(sections: int, duration_s: float | None = None) -> str:
    # Small local models drift on long inputs and front-load coverage; restating the format after
    # the content, with a fixed time range per chapter, keeps them on spec through the ending.
    lines = [
        "\n\n---\nNow write the brief. Follow the output format exactly:",
        "## Executive Summary, ## Speaker & Guests, ## Thematic Breakdown, ## Key Takeaways.",
        f"- Thematic Breakdown has exactly {sections} chapters, each `### Section X: Title`, in time order.",
    ]
    spans = section_spans(duration_s, sections)
    if spans:
        lines.append("- Each chapter covers this time range (you write the title):")
        lines += [f"  - Section {i + 1}: {a}–{b}" for i, (a, b) in enumerate(spans)]
    lines += [
        "- Every chapter bullet starts with a [HH:MM:SS] timestamp copied from the source, inside that "
        "chapter's range. 3-4 bullets per chapter.",
        "- 900-1,100 words total. Do not exceed 1,250 words.",
    ]
    return "\n".join(lines)


def synthesize_user_prompt(
    *, title: str | None, uploader: str | None, condensed: str, sections: int = 4, duration_s: float | None = None
) -> str:
    return (
        "Synthesize this AI Condensed Transcript into an Executive Brief (under 1,100 words).\n\n"
        f"{_source_line(title, uploader)}Condensed Transcript:\n{condensed}{format_reminder(sections, duration_s)}"
    )


def single_pass_user_prompt(
    *, title: str | None, uploader: str | None, transcript: str, sections: int = 4, duration_s: float | None = None
) -> str:
    return (
        "Write an Executive Brief (under 1,100 words) of this video transcript.\n\n"
        f"{_source_line(title, uploader)}Transcript:\n{transcript}{format_reminder(sections, duration_s)}"
    )


REQUIRED_H2 = ("executive summary", "key takeaways")
MAX_SECTIONS = 7
_TS = re.compile(r"\[\d{1,2}:\d{2}(?::\d{2})?\]")


def validate_summary_structure(summary: str) -> tuple[bool, list[str]]:
    """Same idea as PodBrief's validateSummaryStructure."""
    lines = (summary or "").splitlines()
    h2 = [ln.lower() for ln in lines if ln.startswith("## ")]
    h3 = [ln for ln in lines if ln.startswith("### ")]
    missing: list[str] = []
    for name in REQUIRED_H2:
        if not any(name in h for h in h2):
            missing.append(name.title())
    if len(h3) < 3:
        missing.append(f"3+ '### Section' chapters (found {len(h3)})")
    elif len(h3) > MAX_SECTIONS:
        missing.append(f"at most {MAX_SECTIONS} chapters (found {len(h3)})")
    stamps = len(_TS.findall(summary or ""))
    if h3 and stamps < 2 * len(h3):
        missing.append(f"[HH:MM:SS] timestamps on chapter bullets (found {stamps})")
    return (not missing, missing)


def coverage(summary: str, duration_s: float | None) -> float | None:
    """Last timestamp in the brief as a fraction of the video length (tapering check)."""
    stamps = [sum(int(x) * 60 ** i for i, x in enumerate(reversed(m.strip("[]").split(":"))))
              for m in _TS.findall(summary or "")]
    if not stamps or not duration_s:
        return None
    return round(min(1.0, max(stamps) / duration_s), 2)


def quality_retry_system(system: str, missing: list[str]) -> str:
    return (
        f"CRITICAL: Your previous output was incomplete (missing: {', '.join(missing)}). "
        "You MUST produce ALL required sections: Executive Summary, Speaker & Guests, "
        "Thematic Breakdown with 3-6 '### Section X:' chapters whose bullets start with [HH:MM:SS], "
        "and Key Takeaways. Stay within 1,250 words.\n\n" + system
    )

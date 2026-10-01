"""Prompt files (prompts/*.md, overridable in prompts/private/), user-prompt builders, validator."""

from __future__ import annotations

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


def synthesize_user_prompt(*, title: str | None, uploader: str | None, condensed: str) -> str:
    return (
        "Synthesize this AI Condensed Transcript into an Executive Brief (under 1,100 words).\n\n"
        f"{_source_line(title, uploader)}Condensed Transcript:\n{condensed}"
    )


def single_pass_user_prompt(*, title: str | None, uploader: str | None, transcript: str) -> str:
    return (
        "Write an Executive Brief (under 1,100 words) of this video transcript.\n\n"
        f"{_source_line(title, uploader)}Transcript:\n{transcript}"
    )


REQUIRED_H2 = ("executive summary", "key takeaways")


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
    return (not missing, missing)


def quality_retry_system(system: str, missing: list[str]) -> str:
    return (
        f"CRITICAL: Your previous output was incomplete (missing: {', '.join(missing)}). "
        "You MUST produce ALL required sections: Executive Summary, Speaker & Guests, "
        "Thematic Breakdown with at least 3 '### Section X:' chapters, and Key Takeaways. "
        "Do not abbreviate or truncate.\n\n" + system
    )

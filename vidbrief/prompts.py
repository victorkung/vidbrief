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
NAMES = ("priorities", "condense", "chapters", "chapter", "overview", "single_pass")
Point = tuple[int, str, bool]  # (seconds, text, key) — key marks ★ points (advice, news, predictions)


def prompt_path(name: str, *, prompts_dir: Path = PROMPTS) -> Path:
    private = prompts_dir / "private" / f"{name}.md"
    if private.is_file():
        return private
    public = prompts_dir / f"{name}.md"
    if public.is_file():
        return public
    raise FileNotFoundError(f"no prompt file for '{name}' in {prompts_dir}")


def load_prompt(name: str, *, prompts_dir: Path = PROMPTS) -> str:
    """Prompt text with `{priorities}` replaced by priorities.md (the reader's idea of 'important')."""
    text = prompt_path(name, prompts_dir=prompts_dir).read_text(encoding="utf-8").strip()
    if "{priorities}" in text:
        priorities = prompt_path("priorities", prompts_dir=prompts_dir).read_text(encoding="utf-8").strip()
        text = text.replace("{priorities}", priorities)
    return text


def section_count(duration_s: float | None) -> int:
    """Target chapter count: 18 min → 3, 1 h → 4, 1.5 h → 5, 2 h → 6, 2.5 h → 7 (max 8)."""
    minutes = (duration_s or 0) / 60
    return max(3, min(8, round(2 + minutes / 30)))


MAX_WORDS = 1250


def target_words(duration_s: float | None) -> int:
    """Brief length grows sublinearly: ~650 words for 1 h, ~1,150 for 2.5 h, never above 1,250."""
    hours = (duration_s or 0) / 3600
    return int(max(450, min(MAX_WORDS, 650 + 330 * (hours - 1))))


def _source_line(title: str | None, uploader: str | None) -> str:
    bits = [b for b in (title, uploader) if b]
    return ("VIDEO: " + " — ".join(bits) + "\n\n") if bits else ""


def reference_block(*, title: str | None, uploader: str | None, description: str | None) -> str:
    """Publisher metadata, used only to spell names correctly (YouTube auto-captions mangle them)."""
    lines = [f"Title: {title}" if title else "", f"Channel: {uploader}" if uploader else "",
             f"Description: {description.strip()[:1500]}" if description else ""]
    body = "\n".join(ln for ln in lines if ln)
    return f"REFERENCE (for spelling names and terms only; do not add facts from it):\n{body}\n\n" if body else ""


def condense_user_prompt(*, transcript: str, part: int, parts: int, reference: str = "") -> str:
    scope = f"Part {part} of {parts} of the transcript" if parts > 1 else "Transcript"
    return (f"{reference}{scope}:\n\n{transcript}\n\n---\n"
            "Write the key points now, one [HH:MM:SS] line each, ★ before the most important ones.")


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
        "---\nWrite INTRO and 3 timestamped bullets (4 only if there are 4+ ★ points worth keeping) now."
    )


def overview_user_prompt(*, title: str | None, uploader: str | None, opening: str, chapters: str,
                         reference: str = "") -> str:
    return (
        f"{reference or _source_line(title, uploader)}OPENING MINUTES (for who is speaking and why):\n{opening}\n\n"
        f"CHAPTERS:\n{chapters}\n\n"
        "---\nWrite ## High-Level Overview, ## Context, and ## Key Takeaways now."
    )


def single_pass_user_prompt(*, title: str | None, uploader: str | None, transcript: str, sections: int,
                            reference: str = "") -> str:
    return (
        f"{reference or _source_line(title, uploader)}Transcript:\n{transcript}\n\n"
        f"---\nWrite the brief now, with {sections} chapters in time order."
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


def parse_points(text: str) -> list[Point]:
    """Lines that start with a timestamp → [(seconds, text, key)]. ★ (before or after the stamp) sets key."""
    out: list[Point] = []
    for raw in (text or "").splitlines():
        line = _BULLET.sub("", raw.strip())
        key = line.startswith("★")
        line = line.lstrip("★").strip()
        m = _LEAD_TS.match(line)
        if not m:
            continue
        rest = line[m.end():].strip()
        if rest.startswith("★"):
            key, rest = True, rest.lstrip("★").strip()
        rest = rest.strip("*").strip()
        if rest:
            out.append((_to_seconds(m.group(1)), rest, key))
    return out


def render_points(points: list[Point], *, bullets: bool = False) -> str:
    return "\n".join(f"{'- ' if bullets else ''}{'★ ' if key else ''}[{_hms(t)}] {text}" for t, text, key in points)


def key_points_md(points: list[Point], starts: list[tuple[int, str]], duration_s: float) -> str:
    """Condensed points grouped under their chapters, as bullets (the UI's Key points tab)."""
    bounds = [t for t, _ in starts] + [duration_s + 1]
    blocks = []
    for i, (lo, title) in enumerate(starts):
        inside = [p for p in points if lo <= p[0] < bounds[i + 1]]
        if inside:
            blocks.append(f"### Chapter {i + 1}: {title}\n\n{render_points(inside, bullets=True)}")
    return "\n\n".join(blocks) + "\n"


def parse_outline(text: str, duration_s: float) -> list[tuple[int, str]]:
    """chapters.md reply → sorted, de-duplicated chapter starts; first forced to 0."""
    seen: dict[int, str] = {}
    for t, title, _ in parse_points(text):
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


def merge_short_chapters(starts: list[tuple[int, str]], duration_s: float, target: int) -> list[tuple[int, str]]:
    """Fold chapters much shorter than average (cold-open teasers, brief asides) into a neighbour.

    A short first chapter merges forward and takes the next chapter's title; any other short
    chapter merges into the one before it. Never goes below 3 chapters.
    """
    min_s = max(180.0, 0.35 * duration_s / max(1, target))
    starts = list(starts)
    while len(starts) > 3:
        bounds = [t for t, _ in starts] + [duration_s]
        lengths = [b - a for a, b in zip(bounds, bounds[1:])]
        i = min(range(len(starts)), key=lambda k: lengths[k])
        if lengths[i] >= min_s:
            break
        if i == 0:
            starts[1] = (0, starts[1][1])
        del starts[i]
    return starts


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


def _words_of(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", re.sub(r"\*\*[^*]+\*\*:?|\[[\d:]+\]", "", text.lower())))


def copied_takeaways(takeaways: str, sections_md: list[str], threshold: float = 0.7) -> int:
    """How many takeaway bullets are near-copies (word overlap ≥ threshold) of a chapter bullet."""
    bullets = [_words_of(ln) for sec in sections_md for ln in sec.splitlines() if _BULLET.match(ln)]
    count = 0
    for ln in takeaways.splitlines():
        if not _BULLET.match(ln):
            continue
        t = _words_of(ln)
        if t and any(len(t & b) / len(t | b) >= threshold for b in bullets if b):
            count += 1
    return count


def assemble_brief(overview: dict[str, str], sections_md: list[str], meta_line: str | None = None) -> str:
    """Metadata line, High-Level Overview, Context, chapters, Key Takeaways (PodBrief's layout)."""
    parts = [meta_line] if meta_line else []
    parts += [f"## {OVERVIEW_KEYS[k]}\n{overview[k]}" for k in ("overview", "context") if overview.get(k)]
    parts += sections_md
    if overview.get("key takeaway"):
        parts.append(f"## Key Takeaways\n{overview['key takeaway']}")
    return "\n\n".join(parts).strip() + "\n"


def trim_sections(sections: list[dict], *, budget: int, fixed_words: int, key_ts: set[int]) -> list[dict]:
    """Drop bullets until the brief fits `budget` words: 4th bullets first, then the least important
    (non-★, longest) bullet of the wordiest chapter. Never below 2 bullets per chapter."""
    secs = [dict(s, bullets=list(s["bullets"])) for s in sections]

    def words() -> int:
        return fixed_words + sum(len(render_section(i + 1, s).split()) for i, s in enumerate(secs))

    def ts_of(bullet: str) -> int | None:
        m = _LEAD_TS.match(bullet)
        return _to_seconds(m.group(1)) if m else None

    while words() > budget:
        pool = [s for s in secs if len(s["bullets"]) > 3] or [s for s in secs if len(s["bullets"]) > 2]
        if not pool:
            break
        sec = max(pool, key=lambda s: len(render_section(0, s).split()))
        order = sorted(range(len(sec["bullets"])),
                       key=lambda j: (ts_of(sec["bullets"][j]) in key_ts, -len(sec["bullets"][j].split())))
        del sec["bullets"][order[0]]
    return secs


# ── Validation ─────────────────────────────────────────────────────────────

REQUIRED_H2 = {"overview": "High-Level Overview", "key takeaways": "Key Takeaways"}
MAX_SECTIONS = 9


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

"""Transcript → timestamped paragraphs → token-bounded windows for pass 1.

Paragraphs follow PodBrief production: one `HH:MM:SS` label per ~60s of speech,
so the model copies literal timestamps instead of inventing them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def format_hms(seconds: float | None) -> str:
    total = int(max(0, seconds or 0))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def est_tokens(text: str) -> int:
    # ~4 chars per token for English; good enough to size windows.
    return len(text) // 4 + 1


def load_segments(json_path: Path) -> list[dict[str, Any]]:
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    segs = [s for s in (data.get("segments") or []) if (s.get("text") or "").strip()]
    if segs:
        return segs
    text = (data.get("text") or "").strip()
    return [{"start": 0.0, "text": text}] if text else []


def paragraphs(segments: list[dict[str, Any]], *, every_s: float = 60.0) -> list[tuple[float, str]]:
    out: list[tuple[float, str]] = []
    start: float | None = None
    buf: list[str] = []
    for seg in segments:
        t = float(seg.get("start") or 0)
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        if start is None:
            start = t
        elif t - start >= every_s:
            out.append((start, " ".join(buf)))
            start, buf = t, []
        buf.append(text)
    if buf and start is not None:
        out.append((start, " ".join(buf)))
    return out


def render(paras: list[tuple[float, str]]) -> str:
    return "\n\n".join(f"{format_hms(t)}\n{text}" for t, text in paras)


def windows(
    paras: list[tuple[float, str]],
    *,
    max_tokens: int = 7000,
    overlap: int = 1,
) -> list[list[tuple[float, str]]]:
    """Greedy split on paragraph boundaries; `overlap` paragraphs carry over for context."""
    if not paras:
        return []
    out: list[list[tuple[float, str]]] = []
    cur: list[tuple[float, str]] = []
    cur_tok = 0
    for p in paras:
        tok = est_tokens(p[1]) + 4
        if cur and cur_tok + tok > max_tokens:
            out.append(cur)
            carry = cur[-overlap:] if overlap > 0 and len(cur) > overlap else []
            cur = list(carry)
            cur_tok = sum(est_tokens(c[1]) + 4 for c in cur)
        cur.append(p)
        cur_tok += tok
    if cur:
        out.append(cur)
    return out

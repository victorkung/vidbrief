"""Transcript → timestamped paragraphs → token-bounded windows for the condense step.

Paragraphs follow PodBrief production: one `HH:MM:SS` label per ~60s of speech,
so the model copies literal timestamps instead of inventing them.
"""

from __future__ import annotations

import json
import math
import re
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



_STOP = frozenset(
    "the a an and or but of to in on at for with from by as is are was were be been it its this that these those "
    "he she they we you i his her their our your him them us me my not no so if then than there here what which who "
    "about into over also just like very really more most some any all can will would should could has have had do "
    "does did says said argues notes speaker host guest explains believes thinks".split()
)


def _terms(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9$%.]+", text.lower()) if len(w) > 2 and w not in _STOP}


def ground_timestamps(lines: list[tuple[int, str]], paras: list[tuple[float, str]]) -> list[tuple[int, str]]:
    """Re-time condensed lines to the paragraph they came from.

    Small models sometimes repeat one timestamp for a whole list, or list points slightly out of
    order. Each line is matched independently to the paragraph sharing the most distinctive words
    (IDF-weighted); the model's own timestamp only breaks near-ties. Lines that share no
    distinctive words with any paragraph keep the model's timestamp.
    """
    if not lines or not paras:
        return lines
    para_terms = [_terms(t) for _, t in paras]
    df: dict[str, int] = {}
    for terms in para_terms:
        for w in terms:
            df[w] = df.get(w, 0) + 1
    m = len(paras)
    idf = {w: math.log((m + 1) / (c + 0.5)) for w, c in df.items()}
    out: list[tuple[int, str]] = []
    for ts, text in lines:
        q = _terms(text)
        best, best_score = None, 1.0  # need at least ~one distinctive shared word
        for i in range(m):
            score = sum(idf.get(w, 0) for w in q & para_terms[i]) - 0.01 * abs(paras[i][0] - ts) / 60
            if score > best_score:
                best, best_score = i, score
        out.append((int(paras[best][0]) if best is not None else ts, text))
    return out

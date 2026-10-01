"""Human-friendly titles, URL canonicalize, and per-brief folder layout."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse


def clean_title(raw: str, *, max_len: int = 80) -> str:
    if not raw:
        return "Untitled"
    s = raw.replace("\n", " ").strip()
    s = s.replace("_", " ")
    s = re.sub(r"\s*[|–—/]+\s*", " — ", s)
    s = re.sub(r"\s+", " ", s).strip(" -—.")
    s = re.sub(r"\s*\.\.\.\s*$", "", s)
    s = re.sub(r"\s*\[[^\]]{6,}\]\s*$", "", s)
    parts = re.split(r"\s+—\s+|\s+-\s+", s, maxsplit=2)
    if len(parts) >= 2 and parts[0].lower() == parts[1].lower():
        s = " — ".join(parts[1:])
    if len(s) > max_len:
        s = s[: max_len - 1].rstrip() + "…"
    return s or "Untitled"


_YT_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
    "www.youtu.be",
}
_YT_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_X_STATUS = re.compile(
    r"^https?://(?:www\.)?(?:x\.com|twitter\.com)/[^/]+/status/\d+",
    re.I,
)


def canonicalize_media_url(url: str) -> str:
    """One video. Strip YouTube playlist / share junk. Normalize X → https."""
    raw = (url or "").strip()
    if not raw:
        return raw
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    if host in {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}:
        path = parsed.path or ""
        return urlunparse(("https", "x.com", path, "", "", ""))
    if host not in _YT_HOSTS:
        return raw
    vid = ""
    path = parsed.path or ""
    if host.endswith("youtu.be"):
        vid = path.strip("/").split("/")[0] if path.strip("/") else ""
    else:
        qs = parse_qs(parsed.query)
        if qs.get("v"):
            vid = qs["v"][0]
        else:
            parts = [p for p in path.split("/") if p]
            if len(parts) >= 2 and parts[0] in {"shorts", "live", "embed", "v"}:
                vid = parts[1]
    if not _YT_ID.match(vid or ""):
        return raw
    return urlunparse(("https", "www.youtube.com", "/watch", "", urlencode({"v": vid}), ""))


def is_supported_url(url: str) -> bool:
    raw = canonicalize_media_url(url)
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    if host in _YT_HOSTS:
        return bool(_YT_ID.match((parse_qs(parsed.query).get("v") or [""])[0]))
    return bool(_X_STATUS.match(raw))


def ingest_day(*, day: str | None = None) -> str:
    if day and re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        return day
    return date.today().isoformat()


def safe_folder_name(name: str, *, max_len: int = 60) -> str:
    s = clean_title(name, max_len=max_len + 20)
    s = re.sub(r'[/\\:*?"<>|]', "-", s)
    s = re.sub(r"\s+", " ", s).strip(" .")
    if len(s) > max_len:
        s = s[:max_len].rstrip(" .")
    return s or "Untitled"


def make_project_dir(
    briefs_root: Path,
    *,
    title: str,
    media_id: str | None,
    show_name: str | None = None,
    day: str | None = None,
) -> Path:
    folder_day = ingest_day(day=day)
    show = safe_folder_name(show_name or title, max_len=55)
    base = briefs_root / f"{folder_day} {show}"
    if not base.exists():
        base.mkdir(parents=True, exist_ok=True)
        return base
    tail = (media_id or "x")[-8:]
    base = briefs_root / f"{folder_day} {show} ({tail})"
    base.mkdir(parents=True, exist_ok=True)
    return base

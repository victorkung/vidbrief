"""Kokoro's English voices and the chosen default (stored in DATA_DIR/settings.json)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# (id, accent, gender). Kokoro's own quality grades put af_heart and af_bella first.
_CATALOG = [
    ("af_heart", "American", "female"), ("af_bella", "American", "female"), ("af_nicole", "American", "female"),
    ("af_sarah", "American", "female"), ("af_kore", "American", "female"), ("af_aoede", "American", "female"),
    ("af_nova", "American", "female"), ("af_sky", "American", "female"), ("af_alloy", "American", "female"),
    ("af_jessica", "American", "female"), ("af_river", "American", "female"),
    ("am_michael", "American", "male"), ("am_fenrir", "American", "male"), ("am_puck", "American", "male"),
    ("am_echo", "American", "male"), ("am_eric", "American", "male"), ("am_liam", "American", "male"),
    ("am_onyx", "American", "male"), ("am_adam", "American", "male"), ("am_santa", "American", "male"),
    ("bf_emma", "British", "female"), ("bf_isabella", "British", "female"), ("bf_alice", "British", "female"),
    ("bf_lily", "British", "female"),
    ("bm_george", "British", "male"), ("bm_fable", "British", "male"), ("bm_lewis", "British", "male"),
    ("bm_daniel", "British", "male"),
]
RECOMMENDED = ("af_heart", "af_bella", "am_michael", "am_fenrir", "bf_emma", "bm_george")
DEFAULT_VOICE = "af_heart"
VOICE_IDS = frozenset(v for v, _, _ in _CATALOG)
PREVIEW_TEXT = (
    "Here's your VidBrief. Bitcoin dominance sits at 58 percent, and the 30-year yield just hit 5.17 percent. "
    "The takeaway: stay patient and keep some cash ready."
)


def catalog() -> list[dict[str, Any]]:
    return [
        {"id": v, "name": v.split("_", 1)[1].title(), "accent": accent, "gender": gender,
         "recommended": v in RECOMMENDED}
        for v, accent, gender in _CATALOG
    ]


def lang_code(voice: str) -> str:
    """Kokoro's language code is the voice's first letter: 'a' American, 'b' British English."""
    return voice[:1] if voice[:1] in {"a", "b"} else "a"


def _settings_file(data_dir: Path) -> Path:
    return Path(data_dir) / "settings.json"


def saved_voice(data_dir: Path) -> str | None:
    try:
        voice = json.loads(_settings_file(data_dir).read_text(encoding="utf-8")).get("tts_voice")
    except (OSError, ValueError):
        return None
    return voice if voice in VOICE_IDS else None


def save_voice(data_dir: Path, voice: str) -> None:
    if voice not in VOICE_IDS:
        raise ValueError(f"Unknown voice: {voice}")
    path = _settings_file(data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data["tts_voice"] = voice
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)

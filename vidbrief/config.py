"""Settings from .env / environment. One place for defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .envload import load_dotenv

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_LLM_MODEL = "mlx-community/Qwen3.5-9B-MLX-4bit"
DEFAULT_WHISPER = "small"
MODES = ("chaptered", "single_pass")
MODE_ALIASES = {"two_pass": "chaptered", "three_pass": "chaptered"}


TRANSCRIPT_SOURCES = ("auto", "whisper", "captions")  # auto: YouTube captions, else Whisper


def _choice(name: str, options: tuple[str, ...]) -> str:
    value = (os.environ.get(name) or options[0]).strip().lower()
    return value if value in options else options[0]


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name) or default)
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name) or default)
    except ValueError:
        return default


@dataclass
class Settings:
    llm_model: str
    whisper_model: str
    transcript_source: str
    mode: str
    chunk_tokens: int
    condense_max_tokens: int
    chapters_max_tokens: int
    chapter_max_tokens: int
    overview_max_tokens: int
    single_pass_max_tokens: int
    condense_temperature: float
    chapters_temperature: float
    chapter_temperature: float
    overview_temperature: float
    briefs_dir: Path
    data_dir: Path


def load_settings() -> Settings:
    load_dotenv(ROOT)
    mode = (os.environ.get("SUMMARY_MODE") or "chaptered").strip().lower()
    mode = MODE_ALIASES.get(mode, mode)
    return Settings(
        llm_model=(os.environ.get("LLM_MODEL") or DEFAULT_LLM_MODEL).strip(),
        whisper_model=(os.environ.get("WHISPER_MODEL") or DEFAULT_WHISPER).strip(),
        transcript_source=_choice("TRANSCRIPT_SOURCE", TRANSCRIPT_SOURCES),
        mode=mode if mode in MODES else "chaptered",
        chunk_tokens=_int("CHUNK_TOKENS", 7000),
        condense_max_tokens=_int("CONDENSE_MAX_TOKENS", 2000),
        chapters_max_tokens=_int("CHAPTERS_MAX_TOKENS", 400),
        chapter_max_tokens=_int("CHAPTER_MAX_TOKENS", 700),
        overview_max_tokens=_int("OVERVIEW_MAX_TOKENS", 1200),
        single_pass_max_tokens=_int("SINGLE_PASS_MAX_TOKENS", 4000),
        condense_temperature=_float("CONDENSE_TEMPERATURE", 0.1),
        chapters_temperature=_float("CHAPTERS_TEMPERATURE", 0.2),
        chapter_temperature=_float("CHAPTER_TEMPERATURE", 0.2),
        overview_temperature=_float("OVERVIEW_TEMPERATURE", 0.3),
        briefs_dir=Path(os.environ.get("BRIEFS_DIR") or ROOT / "briefs").expanduser(),
        data_dir=ROOT / "data",
    )

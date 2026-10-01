"""Settings from .env / environment. One place for defaults."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .envload import load_dotenv

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_LLM_MODEL = "mlx-community/Qwen3.5-9B-MLX-4bit"
DEFAULT_WHISPER = "small"
MODES = ("two_pass", "single_pass")


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
    mode: str
    chunk_tokens: int
    extract_max_tokens: int
    synth_max_tokens: int
    extract_temperature: float
    synth_temperature: float
    briefs_dir: Path
    data_dir: Path


def load_settings() -> Settings:
    load_dotenv(ROOT)
    mode = (os.environ.get("SUMMARY_MODE") or "two_pass").strip().lower()
    return Settings(
        llm_model=(os.environ.get("LLM_MODEL") or DEFAULT_LLM_MODEL).strip(),
        whisper_model=(os.environ.get("WHISPER_MODEL") or DEFAULT_WHISPER).strip(),
        mode=mode if mode in MODES else "two_pass",
        chunk_tokens=_int("CHUNK_TOKENS", 7000),
        extract_max_tokens=_int("EXTRACT_MAX_TOKENS", 2500),
        synth_max_tokens=_int("SYNTH_MAX_TOKENS", 3000),
        extract_temperature=_float("EXTRACT_TEMPERATURE", 0.1),
        synth_temperature=_float("SYNTH_TEMPERATURE", 0.2),
        briefs_dir=Path(os.environ.get("BRIEFS_DIR") or ROOT / "briefs").expanduser(),
        data_dir=ROOT / "data",
    )

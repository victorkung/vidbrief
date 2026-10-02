#!/usr/bin/env python3
"""Turn a narration script into an MP3 with Kokoro (mlx-audio), then exit (frees memory).

Input (stdin JSON): {"text": str, "out": "brief.mp3", "model": hf id, "voice": "af_heart", "speed": 1.0}
Output lines: PROGRESS_JSON:{"done": i, "total": n}  RESULT_JSON:{"seconds": ..., "gen_seconds": ...}

Each line of the script is one spoken unit; a short pause is added between units.
Needs espeak-ng (brew install espeak-ng) so unfamiliar names are pronounced, not skipped.

Smoke test:
  echo '{"text": "Hello from VidBrief.", "out": "/tmp/t.mp3"}' | .venv/bin/python scripts/tts_run.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from vidbrief.config import load_settings  # noqa: E402

SAMPLE_RATE = 24000
PAUSE_S = 0.25


def emit(tag: str, payload: dict) -> None:
    print(f"{tag}:{json.dumps(payload)}", flush=True)


def main() -> None:
    job = json.load(sys.stdin)
    settings = load_settings()  # loads .env (HF_HOME) before the model libraries read it
    import mlx.core as mx
    import numpy as np
    from mlx_audio.tts.utils import load_model

    lines = [ln.strip() for ln in job["text"].splitlines() if ln.strip()]
    if not lines:
        raise SystemExit("empty script")
    started = time.monotonic()
    model = load_model(job.get("model") or settings.tts_model)
    voice = job.get("voice") or settings.tts_voice
    speed = float(job.get("speed") or settings.tts_speed)
    pause = np.zeros(int(PAUSE_S * SAMPLE_RATE), dtype=np.float32)
    pieces = []
    for i, line in enumerate(lines):
        for seg in model.generate(text=line, voice=voice, speed=speed, lang_code="a"):
            pieces.append(np.array(seg.audio, dtype=np.float32).reshape(-1))
        pieces.append(pause)
        emit("PROGRESS_JSON", {"done": i + 1, "total": len(lines)})
        mx.clear_cache()
    audio = np.concatenate(pieces)
    out = Path(job["out"])
    tmp = out.with_suffix(".partial.mp3")
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "f32le", "-ar", str(SAMPLE_RATE), "-ac", "1", "-i", "-",
         "-b:a", "64k", str(tmp)],
        input=audio.tobytes(), check=True,
    )
    tmp.replace(out)  # never leave a half-written brief.mp3
    emit("RESULT_JSON", {"seconds": round(len(audio) / SAMPLE_RATE, 1),
                         "gen_seconds": round(time.monotonic() - started, 1),
                         "peak_memory_gb": round(mx.get_peak_memory() / 1e9, 2)})


if __name__ == "__main__":
    main()

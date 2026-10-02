#!/usr/bin/env bash
# One-time setup: check tools, create .venv, install UI deps, prefetch models.
# Safe to re-run.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "error: VidBrief needs an Apple Silicon Mac (MLX)." >&2
  exit 1
fi

missing=()
for tool in python3 yt-dlp ffmpeg node espeak-ng; do
  command -v "$tool" >/dev/null 2>&1 || missing+=("$tool")
done
if (( ${#missing[@]} )); then
  echo "error: missing ${missing[*]}. Install with: brew install ${missing[*]/python3/python}" >&2
  exit 1
fi

if [[ ! -x .venv/bin/python ]]; then
  echo "→ creating .venv"
  python3 -m venv .venv
fi
echo "→ installing Python deps"
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q --prefer-binary -r requirements.txt
.venv/bin/python -c "import spacy; spacy.load('en_core_web_sm')" 2>/dev/null \
  || .venv/bin/python -m spacy download en_core_web_sm >/dev/null

if [[ ! -d app/frontend/node_modules ]]; then
  echo "→ installing UI deps"
  (cd app/frontend && npm install --silent)
fi

[[ -f .env ]] || cp .env.example .env

if [[ "${SKIP_MODELS:-0}" != "1" ]]; then
  echo "→ prefetching models (first time: ~7.8 GB; set SKIP_MODELS=1 to skip)"
  .venv/bin/python -c "
import importlib.util
from vidbrief.config import load_settings
s = load_settings()  # loads .env (HF_HOME) before huggingface_hub reads it
from huggingface_hub import snapshot_download
spec = importlib.util.spec_from_file_location('t', 'scripts/transcribe.py'); t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
for repo in (t.resolve_model_repo(s.whisper_model), s.llm_model, s.tts_model):
    print('  ', repo); snapshot_download(repo)
"
fi

echo
echo "Ready. Try:"
echo "  .venv/bin/python -m vidbrief \"https://www.youtube.com/watch?v=...\""
echo "  ./scripts/dev.sh    # UI at http://127.0.0.1:5174"

# VidBrief

Paste a YouTube or X video URL and get a written executive brief. Everything runs on your Mac with open-source models: no API keys, no cost per video.

```text
URL → yt-dlp (audio) → MLX Whisper (transcript) → local LLM via mlx-lm (two-pass summary) → brief.md
```

> Work in progress. Full setup guide, model/RAM table, and configuration docs are coming.

## Quick start

Requires an Apple Silicon Mac (16 GB RAM recommended), Python 3.10+, `yt-dlp`, and `ffmpeg`.

```bash
brew install yt-dlp ffmpeg
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m vidbrief "https://www.youtube.com/watch?v=..."
```

The first run downloads the Whisper and LLM weights (~6.5 GB) into the Hugging Face cache (`HF_HOME`).

## License

MIT

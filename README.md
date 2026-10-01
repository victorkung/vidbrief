# VidBrief

Paste a YouTube or X video URL and get a written executive brief: a high-level overview, context on who is talking, timestamped chapters, and key takeaways. Everything runs on your Mac with open-source models. No API keys, no cost per video.

```text
URL → transcript (YouTube captions, or yt-dlp audio + MLX Whisper) → local LLM via mlx-lm → brief.md
```

> Work in progress. Model/RAM guidance and configuration docs are still being written.

## Quick start

Requires an Apple Silicon Mac (16 GB RAM recommended), Python 3.10+, Node 18+, `yt-dlp`, and `ffmpeg`.

```bash
brew install yt-dlp ffmpeg node
./scripts/setup.sh        # venv, Python + UI deps, model download (~7.5 GB first time)
./scripts/dev.sh          # UI at http://127.0.0.1:5174
```

Or from the terminal:

```bash
.venv/bin/python -m vidbrief "https://www.youtube.com/watch?v=..."
```

## How it works

1. **Transcript.** YouTube videos use the video's own captions (creator-uploaded first, then YouTube's speech recognition), which takes seconds. X videos and YouTube videos without captions are downloaded with yt-dlp and transcribed locally with MLX Whisper.
2. **Condense.** The transcript is split into ~30-minute windows; the model writes one timestamped line per key point. Timestamps are then matched back to the transcript in code, so they are always real.
3. **Plan chapters.** One short call groups the key points into 3–6 chapters by topic (about one per 13 minutes).
4. **Write chapters.** One call per chapter, seeing only that chapter's key points: a two-sentence intro and 3–4 `[HH:MM:SS] **Label**: point` bullets.
5. **Overview, context, takeaways.** One call over the finished chapters.

Each step is small on purpose: a 9B model running locally follows short, focused instructions far better than one long prompt. The code, not the model, assembles the final structure.

Default model: [`mlx-community/Qwen3.5-9B-MLX-4bit`](https://huggingface.co/mlx-community/Qwen3.5-9B-MLX-4bit) (~6 GB on disk, ~6.7 GB peak memory). A one-hour video takes about 5–9 minutes to summarize on an M5 with 16 GB.

## Configuration

Copy `.env.example` to `.env`. The main settings:

| Setting | Default | What it does |
|---|---|---|
| `LLM_MODEL` | `mlx-community/Qwen3.5-9B-MLX-4bit` | Any mlx-lm model (Hugging Face id or local path) |
| `SUMMARY_MODE` | `chaptered` | `chaptered` (steps above) or `single_pass` (one call) |
| `TRANSCRIPT_SOURCE` | `auto` | `auto` (captions, else Whisper), `whisper`, or `captions` |
| `WHISPER_MODEL` | `turbo` | `turbo` (most accurate) or `small` (faster). Only used when a video has no captions |
| `HF_HOME` | `~/.cache/huggingface` | Where models are stored (an external drive works) |

### Editing prompts

Prompts are plain markdown in `prompts/`: `condense.md`, `chapters.md`, `chapter.md`, `overview.md`, `single_pass.md`. To customize one without touching the defaults, copy it into `prompts/private/` with the same name and edit it there (that folder is gitignored).

### Comparing models

```bash
.venv/bin/python scripts/eval.py --models mlx-community/Qwen3.5-9B-MLX-4bit mlx-community/gemma-4-e4b-it-4bit
```

Runs the summarize step for each model on every video you've already transcribed and prints time, memory, length, chapter count, and timeline coverage.

## Troubleshooting

- **YouTube HTTP 403:** set `YTDLP_COOKIES_FROM_BROWSER=chrome` in `.env` and run `brew upgrade yt-dlp`.
- **Out of memory:** use a smaller model (`LLM_MODEL=mlx-community/gemma-4-e4b-it-4bit`) and close other heavy apps.

## License

MIT

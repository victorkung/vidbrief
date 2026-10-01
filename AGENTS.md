# AGENTS.md — VidBrief

Free, local video briefs: `url → yt-dlp (audio) → MLX Whisper → local LLM (mlx-lm) → brief.md`. Apple Silicon only. No API keys.

## Get started (first clone)

1. `brew install yt-dlp ffmpeg` (and `node` for the UI).
2. `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`
3. Optional: `cp .env.example .env` (model choice, `HF_HOME`, cookies).
4. CLI: `.venv/bin/python -m vidbrief "<youtube or x url>"` prints the path to `brief.md`.

## Layout

| Path | What |
|------|------|
| `vidbrief/pipeline.py` | Stage orchestration, resumable from files in `briefs/<folder>/` |
| `vidbrief/media.py` | yt-dlp probe/download (403 hardening) + Whisper subprocess |
| `vidbrief/summarize.py` | two_pass (chunked extract → synthesize) or single_pass, validate + retry |
| `vidbrief/chunking.py` | 60s `HH:MM:SS` paragraphs → token windows |
| `scripts/llm_run.py` | mlx-lm runner subprocess (frees RAM when the stage ends) |
| `scripts/transcribe.py` | Chunked MLX Whisper (from clipgenerator) |
| `prompts/*.md` | Default prompts; `prompts/private/<same name>.md` overrides (gitignored) |
| `data/ledger.jsonl` | Per-stage tokens, tok/s, seconds, peak memory |

## Rules

- Tests: `.venv/bin/python -m pytest -q` before every commit.
- Never commit `.env`, `briefs/`, `data/`, `prompts/private/*` (except its README), media, transcripts, `.venv/`, `node_modules/`.
- Check `git status` and stage explicit paths; no `git add -A`.
- Commit and push to `origin main` as work lands (the human wants a paper trail).

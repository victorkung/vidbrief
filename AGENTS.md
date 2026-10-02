# AGENTS.md — VidBrief

Free, local video briefs on Apple Silicon: `url → YouTube captions or (yt-dlp audio → MLX Whisper) → local LLM (mlx-lm) → brief.md → Kokoro voice → brief.mp3`. No API keys. Human-facing docs: [README.md](README.md).

## Get started (first clone)

1. Check `uname -m` is `arm64`; `brew install python yt-dlp ffmpeg node espeak-ng` if any are missing.
2. `./scripts/setup.sh` (idempotent; `SKIP_MODELS=1` skips the ~7.8 GB model download).
3. `.venv/bin/python -m pytest -q` — must pass before and after every change.
4. App: `./scripts/dev.sh` → UI http://127.0.0.1:5174, API http://127.0.0.1:8788. CLI: `.venv/bin/python -m vidbrief "<url>"`.

## Layout

| Path | What |
|------|------|
| `vidbrief/pipeline.py` | Stage orchestration (resolve → captions or download+Whisper → summarize → voice), resumable from files in `briefs/<folder>/` |
| `vidbrief/media.py` | yt-dlp probe/download (403 hardening), YouTube captions (json3), Whisper subprocess |
| `vidbrief/summarize.py` | `chaptered`: condense → plan chapters → write chapters → overview, then length trim; or `single_pass` |
| `vidbrief/prompts.py` | Prompt loading (`{priorities}` injection, `prompts/private/` overrides), parsers, length targets, validator |
| `vidbrief/chunking.py` | 60 s `HH:MM:SS` paragraphs → token windows; grounds condensed timestamps in the transcript |
| `vidbrief/api.py` | FastAPI: ordered queue, one job at a time (run lock), batch ingest, resume on restart, safe delete |
| `vidbrief/modellock.py` | Machine-wide file lock: one model run at a time across all VidBrief processes |
| `vidbrief/speech.py` | Brief → narration script (strips timestamps/markdown) and the Kokoro subprocess wrapper |
| `vidbrief/voices.py` | Kokoro's 28 English voices; chosen default in `DATA_DIR/settings.json` |
| `scripts/tts_run.py` | Kokoro (mlx-audio) runner subprocess → brief.mp3 |
| `vidbrief/store.py` | JSON library (`data/library.json`); `Library.update` for atomic field merges |
| `scripts/llm_run.py` | mlx-lm runner subprocess (model unloads when the step ends) |
| `scripts/transcribe.py` | Chunked MLX Whisper |
| `scripts/eval.py` | Compare models on already-transcribed videos |
| `prompts/*.md` | Prompts; `priorities.md` defines what "important" means |
| `app/frontend/` | React + Vite UI (light theme, blue accent #2563eb; tokens in styles.css, shared with site/) |
| `docs/reference/` | PodBrief reference briefs (format and voice guide) |
| `docs/screenshots/` | README images, captured from a demo library (see below) |

## Rules

- Never commit `.env`, `briefs/`, `data/`, `prompts/private/*` (except its README), media, transcripts, `.venv/`, `node_modules/`.
- Stage explicit paths and check `git status`; no `git add -A`.
- Never run model work outside `modellock.model_slot` (it's built into `llm.run_jobs` and `media.transcribe`).
- Keep the brief layout: `## High-Level Overview`, `## Context`, `### Chapter N: Title` (intro + `- [HH:MM:SS] **Label**: text` bullets), `## Key Takeaways`. Length budget: `prompts.target_words` (max 1,250).

## Refreshing README screenshots

Run a separate demo instance so a personal library never appears:

```bash
DATA_DIR=~/vidbrief-demo/data BRIEFS_DIR=~/vidbrief-demo/briefs \
  VIDBRIEF_API_PORT=8790 VIDBRIEF_UI_PORT=5176 ./scripts/dev.sh
```

Add public videos there, then capture with headless Chrome, for example:
`"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --hide-scrollbars --force-device-scale-factor=2 --window-size=1280,900 --virtual-time-budget=8000 --screenshot=docs/screenshots/brief.png "http://127.0.0.1:5176/#/b/<id>"`

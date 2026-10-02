# CLAUDE.md — VidBrief

## "Start the servers" (do this directly, no exploration needed)

1. Run `./scripts/dev.sh` from the repo root **in the background** (it blocks; it's idempotent and skips anything already running).
2. Wait ~3 s, then check: `curl -s http://127.0.0.1:8788/api/health` → `{"ok": true, ...}`.
3. Tell the user: **UI http://127.0.0.1:5174** (API on 8788). That's it.

If it fails:
- "missing .venv" or "node_modules" → run `./scripts/setup.sh` (add `SKIP_MODELS=1` if models are already downloaded), then retry.
- Port already in use but health fails → `lsof -ti tcp:8788 | xargs kill; lsof -ti tcp:5174 | xargs kill`, then retry.

**Stop the servers:** `lsof -ti tcp:8788 | xargs kill; lsof -ti tcp:5174 | xargs kill`
**Restart only the API** (after backend changes): check `/api/health` shows `"active": null` and `"queue_length": 0` first (don't kill a running job), then kill port 8788 and run `./scripts/serve.sh` in the background.

## Other common requests

- **Deploy vidbrief.io:** `cd site && pnpm build && vercel --prod --yes` (Vercel project `vidbrief`, already linked).
- **Run tests:** `.venv/bin/python -m pytest -q`
- **Add audio to briefs missing it:** `.venv/bin/python scripts/backfill_audio.py`
- **Commit:** stage explicit paths, never `.env`, `briefs/`, `data/`, `site/.vercel`, `site/.env*`; push to `origin main`.

For architecture, layout and rules, see [AGENTS.md](AGENTS.md) (read it only when changing code).

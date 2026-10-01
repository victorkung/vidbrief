"""FastAPI for the local UI. One job runs at a time (Whisper and the LLM need the RAM)."""

from __future__ import annotations

import queue
import shutil
import subprocess
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from . import pipeline
from .config import MODES, load_settings

app = FastAPI(title="VidBrief")
settings = load_settings()
lib = pipeline.library(settings)

_jobs: "queue.Queue[tuple[str, dict[str, Any]]]" = queue.Queue()
_active: dict[str, Any] = {"id": None, "proc": None, "cancelled": set()}
_lock = threading.Lock()


def _set_proc(proc: subprocess.Popen) -> None:
    with _lock:
        _active["proc"] = proc


def _worker() -> None:
    while True:
        brief_id, opts = _jobs.get()
        if brief_id in _active["cancelled"]:
            _active["cancelled"].discard(brief_id)
            continue
        with _lock:
            _active["id"] = brief_id
        try:
            s = load_settings()
            if opts.get("mode") in MODES:
                s.mode = opts["mode"]
            pipeline.process(brief_id, s, lib, on_proc=_set_proc, resummarize=bool(opts.get("resummarize")))
        except Exception:  # noqa: BLE001 — error is recorded on the brief row
            pass
        finally:
            with _lock:
                _active.update(id=None, proc=None)
            if brief_id in _active["cancelled"]:
                _active["cancelled"].discard(brief_id)
                row = lib.get_brief(brief_id)
                if row:
                    lib.upsert_brief({**row, "status": "cancelled", "stage": "cancelled", "message": "Cancelled",
                                      "error": None, "detail": None})


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    # Rows left "running" by a previous server process can never finish; mark them resumable.
    for row in lib.list_briefs():
        if row.get("status") in {"running", "pending", "queued"}:
            lib.upsert_brief({**row, "status": "error", "stage": "error", "message": "Interrupted — retry to resume",
                              "error": "Interrupted — retry to resume"})
    threading.Thread(target=_worker, daemon=True).start()
    yield


app.router.lifespan_context = _lifespan


def _enqueue(brief_id: str, **opts: Any) -> None:
    row = lib.get_brief(brief_id)
    if row:
        lib.upsert_brief({**row, "status": "queued", "stage": "queued", "message": "Queued", "error": None})
    _jobs.put((brief_id, opts))


def _read(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.is_file() else None


class IngestBody(BaseModel):
    url: str
    whisper_model: str | None = None


class ResummarizeBody(BaseModel):
    mode: str | None = None


@app.get("/api/health")
def health() -> dict[str, Any]:
    s = load_settings()
    return {
        "ok": True,
        "llm_model": s.llm_model,
        "whisper_model": s.whisper_model,
        "mode": s.mode,
        "yt_dlp": bool(shutil.which("yt-dlp")),
        "ffmpeg": bool(shutil.which("ffmpeg")),
        "active": _active["id"],
    }


@app.get("/api/briefs")
def list_briefs() -> list[dict[str, Any]]:
    return lib.list_briefs()


@app.get("/api/briefs/{brief_id}")
def get_brief(brief_id: str) -> dict[str, Any]:
    row = lib.get_brief(brief_id)
    if not row:
        raise HTTPException(404, "Brief not found")
    if row.get("folder"):
        a = pipeline.artifacts(Path(row["folder"]))
        row["brief_md"] = _read(a["brief"])
        row["condensed_md"] = _read(a["key_points"]) or _read(a["condensed"])
        row["transcript"] = _read(a["transcript_md"])
    return row


@app.post("/api/ingest")
def ingest(body: IngestBody) -> dict[str, Any]:
    s = load_settings()
    if body.whisper_model:
        s.whisper_model = body.whisper_model
    try:
        row = pipeline.create(body.url, s, lib)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    _enqueue(row["id"])
    return row


@app.post("/api/briefs/{brief_id}/retry")
def retry(brief_id: str) -> dict[str, Any]:
    if not lib.get_brief(brief_id):
        raise HTTPException(404, "Brief not found")
    _enqueue(brief_id)
    return {"ok": True}


@app.post("/api/briefs/{brief_id}/resummarize")
def resummarize(brief_id: str, body: ResummarizeBody) -> dict[str, Any]:
    row = lib.get_brief(brief_id)
    if not row or not row.get("folder"):
        raise HTTPException(404, "Brief not found or not transcribed yet")
    _enqueue(brief_id, resummarize=True, mode=body.mode)
    return {"ok": True}


@app.post("/api/briefs/{brief_id}/cancel")
def cancel(brief_id: str) -> dict[str, Any]:
    _active["cancelled"].add(brief_id)
    with _lock:
        if _active["id"] == brief_id and _active["proc"] and _active["proc"].poll() is None:
            _active["proc"].terminate()
    return {"ok": True}


def _folder_to_delete(row: dict[str, Any]) -> Path | None:
    """The brief's folder, only if it really lives inside briefs/ (never delete anything else)."""
    if not row.get("folder"):
        return None
    folder = Path(row["folder"]).resolve()
    root = settings.briefs_dir.resolve()
    if folder == root or root not in folder.parents or not folder.is_dir():
        return None
    return folder


@app.delete("/api/briefs/{brief_id}")
def delete(brief_id: str, files: bool = False) -> dict[str, Any]:
    """Remove a brief from the library; with files=true also delete its folder (audio, transcript, briefs)."""
    row = lib.get_brief(brief_id)
    if not row:
        raise HTTPException(404, "Brief not found")
    cancel(brief_id)
    lib.delete_brief(brief_id)
    freed = 0
    folder = _folder_to_delete(row) if files else None
    if folder:
        freed = sum(p.stat().st_size for p in folder.rglob("*") if p.is_file())
        shutil.rmtree(folder, ignore_errors=True)
    return {"ok": True, "freed_bytes": freed, "deleted_folder": str(folder) if folder else None}

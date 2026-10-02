"""FastAPI for the local UI. One job runs at a time (Whisper and the LLM need the RAM)."""

from __future__ import annotations

import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import media, pipeline
from .config import MODES, load_settings
from .naming import clean_title, is_supported_url, media_key

app = FastAPI(title="VidBrief")
settings = load_settings()
lib = pipeline.library(settings)

# One job at a time: Whisper and the LLM each need several GB, so jobs must never overlap.
# `_pending` is the ordered wait list; `_active` is the job running now.
_pending: list[tuple[str, dict[str, Any]]] = []
_cv = threading.Condition()
_active: dict[str, Any] = {"id": None, "proc": None, "cancelled": set()}
_run_lock = threading.Lock()  # held for a whole job: even a second worker thread can't overlap jobs
_worker_started = threading.Event()
_resolver = ThreadPoolExecutor(max_workers=2, thread_name_prefix="resolve")
PLACEHOLDER_TITLE = "Resolving…"
MAX_BATCH = 25
STOP = "__stop__"


def _set_proc(proc: subprocess.Popen) -> None:
    with _cv:
        _active["proc"] = proc


def _worker() -> None:
    while True:
        with _run_lock:
            if not _run_one():
                return


def stop_worker() -> None:
    """Ask one worker thread to exit after its current job (used by tests)."""
    with _cv:
        _pending.append((STOP, {}))
        _cv.notify()


def _start_worker() -> None:
    if not _worker_started.is_set():
        _worker_started.set()
        threading.Thread(target=_worker, daemon=True, name="vidbrief-worker").start()


def _run_one() -> bool:
    """Take the next brief off the wait list and run it to completion (caller holds _run_lock).
    Returns False when told to stop."""
    with _cv:
        while not _pending:
            _cv.wait()
        brief_id, opts = _pending.pop(0)
        if brief_id == STOP:
            return False
        _active.update(id=brief_id, proc=None)
    try:
        s = load_settings()
        if opts.get("mode") in MODES:
            s.mode = opts["mode"]
        pipeline.process(brief_id, s, lib, on_proc=_set_proc, resummarize=bool(opts.get("resummarize")))
    except Exception:  # noqa: BLE001 — error is recorded on the brief row
        pass
    finally:
        with _cv:
            _active.update(id=None, proc=None)
            was_cancelled = brief_id in _active["cancelled"]
            _active["cancelled"].discard(brief_id)
        if was_cancelled:
            lib.update(brief_id, status="cancelled", stage="cancelled", message="Cancelled", error=None,
                       detail=None)
    return True


def _resolve(brief_id: str) -> None:
    """Fill in title/channel/date for a queued brief so the library shows it while it waits.
    Network only (yt-dlp metadata); never touches status or folder, so it can't race the worker."""
    row = lib.get_brief(brief_id)
    if not row or row.get("folder") or row.get("title") not in (None, "", PLACEHOLDER_TITLE):
        return
    try:
        meta = media.probe_url(row["url"])
    except Exception:  # noqa: BLE001 — the worker will surface real errors when it runs
        return
    lib.update(brief_id, only_if_status={"queued", "pending"}, title=clean_title(meta["title"]),
               uploader=meta["uploader"], duration=meta["duration"], published=meta["published"],
               description=meta["description"])


def _enqueue(brief_id: str, *, front: bool = False, **opts: Any) -> bool:
    """Queue a brief (no-op if it's already waiting or running). Returns True if queued."""
    with _cv:
        if _active["id"] == brief_id or any(pid == brief_id for pid, _ in _pending):
            return False
        _active["cancelled"].discard(brief_id)
        lib.update(brief_id, status="queued", stage="queued", message="Queued", error=None, detail=None)
        _pending.insert(0, (brief_id, opts)) if front else _pending.append((brief_id, opts))
        _cv.notify()
    _resolver.submit(_resolve, brief_id)
    return True


def _queue_positions() -> dict[str, int]:
    with _cv:
        return {pid: i + 1 for i, (pid, _) in enumerate(p for p in _pending if p[0] != STOP)}


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    # Resume what a previous server left unfinished: the running job first, then the queue in order.
    # pipeline.process picks up from the files already on disk.
    leftover = [r for r in lib.list_briefs() if r.get("status") in {"running", "queued", "pending"}]
    leftover.sort(key=lambda r: (r.get("status") != "running", str(r.get("created_at") or "")))
    for row in leftover:
        _enqueue(row["id"])
    _start_worker()
    yield


app.router.lifespan_context = _lifespan


def _submit(url: str, whisper_model: str | None) -> tuple[dict[str, Any] | None, str | None]:
    """Create-and-queue one URL. Returns (row, None) or (existing_row_or_None, reason skipped)."""
    url = (url or "").strip()
    if not is_supported_url(url):
        return None, "not a YouTube or X video link"
    key = media_key(url)
    existing = next((b for b in lib.list_briefs() if b.get("url") and media_key(b["url"]) == key), None)
    if existing:
        if existing.get("status") in {"error", "cancelled"}:
            _enqueue(existing["id"])  # resume from its files instead of duplicating
            return lib.get_brief(existing["id"]), None
        return existing, "already in library"
    s = load_settings()
    if whisper_model:
        s.whisper_model = whisper_model
    row = pipeline.create(url, s, lib)
    _enqueue(row["id"])
    return lib.get_brief(row["id"]), None


def _read(path: Path) -> str | None:
    return path.read_text(encoding="utf-8") if path.is_file() else None


class IngestBody(BaseModel):
    url: str
    whisper_model: str | None = None


class BatchBody(BaseModel):
    urls: list[str]
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
        "queue_length": len(_queue_positions()),
    }


@app.get("/api/briefs")
def list_briefs() -> list[dict[str, Any]]:
    positions = _queue_positions()
    rows = lib.list_briefs()
    for row in rows:
        if row["id"] in positions:
            row["queue_position"] = positions[row["id"]]
    return rows


@app.get("/api/briefs/{brief_id}")
def get_brief(brief_id: str) -> dict[str, Any]:
    row = lib.get_brief(brief_id)
    if not row:
        raise HTTPException(404, "Brief not found")
    if row.get("folder"):
        a = pipeline.artifacts(Path(row["folder"]))
        row["audio"] = a["brief_audio"].is_file()
        row["brief_md"] = _read(a["brief"])
        row["condensed_md"] = _read(a["key_points"]) or _read(a["condensed"])
        row["transcript"] = _read(a["transcript_md"])
    return row


@app.post("/api/ingest")
def ingest(body: IngestBody) -> dict[str, Any]:
    """One URL. A URL already in the library returns that brief instead of a duplicate."""
    row, reason = _submit(body.url, body.whisper_model)
    if row is None:
        raise HTTPException(400, "Paste a YouTube watch URL or an X status URL.")
    return {**row, "skipped": reason}


@app.post("/api/ingest/batch")
def ingest_batch(body: BatchBody) -> dict[str, Any]:
    """Several URLs at once. They queue in order and run one at a time."""
    urls = [u.strip() for u in body.urls if u.strip()]
    if len(urls) > MAX_BATCH:
        raise HTTPException(400, f"At most {MAX_BATCH} links at a time.")
    queued, skipped, seen = [], [], set()
    for url in urls:
        key = media_key(url) if is_supported_url(url) else url
        if key in seen:
            skipped.append({"url": url, "reason": "duplicate in this batch"})
            continue
        seen.add(key)
        row, reason = _submit(url, body.whisper_model)
        if reason:
            skipped.append({"url": url, "reason": reason, "id": row["id"] if row else None})
        else:
            queued.append(row["id"])
    return {"queued": queued, "skipped": skipped}


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


@app.get("/api/briefs/{brief_id}/audio")
def audio(brief_id: str) -> FileResponse:
    """The brief read aloud (MP3). Supports Range requests so the player can seek."""
    row = lib.get_brief(brief_id)
    path = pipeline.artifacts(Path(row["folder"]))["brief_audio"] if row and row.get("folder") else None
    if not path or not path.is_file():
        raise HTTPException(404, "No audio for this brief yet")
    name = f"{(row.get('title') or 'brief')[:80]}.mp3".replace("/", "-")
    return FileResponse(path, media_type="audio/mpeg", filename=name, content_disposition_type="inline")


@app.post("/api/briefs/{brief_id}/voice")
def regenerate_voice(brief_id: str) -> dict[str, Any]:
    """Queue (re)recording the audio for a finished brief."""
    row = lib.get_brief(brief_id)
    if not row or not row.get("folder"):
        raise HTTPException(404, "Brief not found")
    pipeline.artifacts(Path(row["folder"]))["brief_audio"].unlink(missing_ok=True)
    _enqueue(brief_id)
    return {"ok": True}


@app.post("/api/briefs/{brief_id}/cancel")
def cancel(brief_id: str) -> dict[str, Any]:
    with _cv:
        waiting = any(pid == brief_id for pid, _ in _pending)
        _pending[:] = [(pid, o) for pid, o in _pending if pid != brief_id]
        if _active["id"] == brief_id:
            _active["cancelled"].add(brief_id)  # the worker marks it cancelled when the process exits
            if _active["proc"] and _active["proc"].poll() is None:
                _active["proc"].terminate()
    if waiting:
        lib.update(brief_id, status="cancelled", stage="cancelled", message="Cancelled", error=None, detail=None)
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

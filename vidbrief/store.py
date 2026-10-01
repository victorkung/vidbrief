"""JSON library of briefs. Local only — no database."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class Library:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.is_file():
            self._write({"briefs": []})

    def _read(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"briefs": []}
        if not isinstance(data, dict):
            return {"briefs": []}
        briefs = data.get("briefs")
        if not isinstance(briefs, list):
            data["briefs"] = []
        return data

    def _write(self, data: dict[str, Any]) -> None:
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def list_briefs(self) -> list[dict[str, Any]]:
        with self._lock:
            briefs = list(self._read().get("briefs") or [])
        briefs.sort(key=lambda b: str(b.get("created_at") or ""), reverse=True)
        return briefs

    def get_brief(self, brief_id: str) -> dict[str, Any] | None:
        with self._lock:
            for b in self._read().get("briefs") or []:
                if b.get("id") == brief_id:
                    return dict(b)
        return None

    def upsert_brief(self, brief: dict[str, Any]) -> dict[str, Any]:
        brief = dict(brief)
        brief["updated_at"] = _now()
        with self._lock:
            data = self._read()
            rows: list[dict[str, Any]] = list(data.get("briefs") or [])
            found = False
            for i, row in enumerate(rows):
                if row.get("id") == brief.get("id"):
                    rows[i] = brief
                    found = True
                    break
            if not found:
                rows.append(brief)
            data["briefs"] = rows
            self._write(data)
        return brief

    def update(self, brief_id: str, *, only_if_status: set[str] | None = None, **fields: Any) -> dict[str, Any] | None:
        """Merge `fields` into one row atomically (no read-modify-write race with other threads).

        With `only_if_status`, the update is skipped unless the row's status is in that set.
        Returns the updated row, or None if the row is missing or the guard failed.
        """
        with self._lock:
            data = self._read()
            for row in data.get("briefs") or []:
                if row.get("id") != brief_id:
                    continue
                if only_if_status is not None and row.get("status") not in only_if_status:
                    return None
                row.update(fields)
                row["updated_at"] = _now()
                self._write(data)
                return dict(row)
        return None

    def delete_brief(self, brief_id: str) -> bool:
        with self._lock:
            data = self._read()
            rows = [b for b in (data.get("briefs") or []) if b.get("id") != brief_id]
            if len(rows) == len(data.get("briefs") or []):
                return False
            data["briefs"] = rows
            self._write(data)
        return True


def make_brief(
    *,
    title: str,
    url: str | None,
    whisper_model: str,
    status: str = "pending",
) -> dict[str, Any]:
    now = _now()
    return {
        "id": new_id(),
        "title": title,
        "url": url,
        "uploader": None,
        "duration": None,
        "whisper_model": whisper_model,
        "status": status,
        "error": None,
        "stage": "queued",
        "percent": 0,
        "message": "Queued",
        "folder": None,
        "audio_path": None,
        "transcript_json": None,
        "transcript_txt": None,
        "condensed_path": None,
        "brief_path": None,
        "input_tokens": 0,
        "output_tokens": 0,
        "created_at": now,
        "updated_at": now,
    }

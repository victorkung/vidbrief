"""One model on the GPU at a time, across every VidBrief process on this Mac.

The API server already runs one job at a time, but the CLI, scripts/eval.py and a second
server instance are separate processes. Whisper (~1.6 GB) plus the LLM (~6.7 GB peak), or two
LLMs, would overrun a 16 GB Mac, so every model run takes this file lock first.
"""

from __future__ import annotations

import fcntl
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator

LOCK_PATH = Path(os.environ.get("VIDBRIEF_LOCK") or Path.home() / "Library/Caches/vidbrief/model.lock")


@contextmanager
def model_slot(on_wait: Callable[[], None] | None = None, path: Path | None = None) -> Iterator[None]:
    """Hold the machine-wide model slot; calls `on_wait` once if another job has it."""
    path = path or LOCK_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            if on_wait:
                on_wait()
            fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)

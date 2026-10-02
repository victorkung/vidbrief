from pathlib import Path

import pytest

from vidbrief import pipeline, speech
from vidbrief.config import load_settings
from vidbrief.store import Library


@pytest.fixture
def ready_brief(tmp_path):
    settings = load_settings()
    settings.briefs_dir, settings.data_dir = tmp_path / "briefs", tmp_path / "data"
    folder = settings.briefs_dir / "show"
    folder.mkdir(parents=True)
    (folder / "source.transcript.json").write_text('{"segments": [{"start": 0, "text": "hi"}]}')
    (folder / "brief.md").write_text("## High-Level Overview\nHello.\n")
    lib = Library(settings.data_dir / "library.json")
    lib.upsert_brief({"id": "b1", "title": "T", "url": "https://youtu.be/aaaaaaaaaaa", "folder": str(folder),
                      "status": "queued"})
    return settings, lib, folder


def test_voice_failure_keeps_brief_ready(ready_brief, monkeypatch):
    settings, lib, folder = ready_brief

    def boom(*a, **k):
        raise RuntimeError("kokoro exploded")

    monkeypatch.setattr(speech, "synthesize", boom)
    pipeline.process("b1", settings, lib)
    row = lib.get_brief("b1")
    assert row["status"] == "ready"
    assert "kokoro exploded" in row["audio_error"]


def test_voice_skipped_when_disabled(ready_brief, monkeypatch):
    settings, lib, folder = ready_brief
    settings.tts_enabled = False
    called = []
    monkeypatch.setattr(speech, "synthesize", lambda *a, **k: called.append(1))
    pipeline.process("b1", settings, lib)
    assert not called
    assert lib.get_brief("b1")["status"] == "ready"


def test_voice_success_records_seconds(ready_brief, monkeypatch):
    settings, lib, folder = ready_brief

    def fake(text, out: Path, **k):
        assert "High-Level Overview." in text and "#" not in text
        out.write_bytes(b"mp3")
        return {"seconds": 12.5}

    monkeypatch.setattr(speech, "synthesize", fake)
    pipeline.process("b1", settings, lib)
    assert lib.get_brief("b1")["audio_seconds"] == 12.5
    assert (folder / "brief.mp3").is_file()

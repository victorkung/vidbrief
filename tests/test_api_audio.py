import pytest
from fastapi.testclient import TestClient

from vidbrief import api
from vidbrief.store import Library


@pytest.fixture
def client(tmp_path, monkeypatch):
    lib = Library(tmp_path / "library.json")
    monkeypatch.setattr(api, "lib", lib)
    folder = tmp_path / "briefs" / "show"
    folder.mkdir(parents=True)
    lib.upsert_brief({"id": "b1", "title": "A/B Show", "folder": str(folder), "status": "ready"})
    lib.upsert_brief({"id": "b2", "title": "No audio", "folder": str(folder.parent), "status": "ready"})
    (folder / "brief.mp3").write_bytes(b"ID3" + bytes(range(256)) * 40)
    # No lifespan: we don't want the queue worker for these tests.
    return TestClient(api.app)


def test_audio_served_with_range(client):
    full = client.get("/api/briefs/b1/audio")
    assert full.status_code == 200
    assert full.headers["content-type"] == "audio/mpeg"
    part = client.get("/api/briefs/b1/audio", headers={"Range": "bytes=0-99"})
    assert part.status_code == 206
    assert len(part.content) == 100


def test_audio_missing_is_404(client):
    assert client.get("/api/briefs/b2/audio").status_code == 404
    assert client.get("/api/briefs/nope/audio").status_code == 404


def test_brief_reports_audio_flag(client):
    assert client.get("/api/briefs/b1").json()["audio"] is True
    assert client.get("/api/briefs/b2").json()["audio"] is False

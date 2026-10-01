import threading
import time

import pytest

from vidbrief import api
from vidbrief.store import Library

YT = ["https://www.youtube.com/watch?v=aaaaaaaaaaa", "https://youtu.be/bbbbbbbbbbb", "https://www.youtube.com/watch?v=ccccccccccc"]


@pytest.fixture
def q(tmp_path, monkeypatch):
    """Fresh library + empty queue; no network, no models."""
    lib = Library(tmp_path / "library.json")
    monkeypatch.setattr(api, "lib", lib)
    monkeypatch.setattr(api.settings, "briefs_dir", tmp_path / "briefs")
    monkeypatch.setattr(api.media, "probe_url", lambda url: {
        "id": url[-11:], "title": f"Title {url[-3:]}", "uploader": "Chan", "duration": 600,
        "webpage_url": url, "published": "2026-08-05", "description": None})
    api._pending.clear()
    api._active.update(id=None, proc=None, cancelled=set())
    workers: list[threading.Thread] = []
    yield lib, workers
    for _ in workers:
        api.stop_worker()
    for t in workers:
        t.join(timeout=2)
    assert not any(t.is_alive() for t in workers)
    api._pending.clear()


def start_worker(workers):
    t = threading.Thread(target=api._worker, daemon=True)
    t.start()
    workers.append(t)


def wait_for(cond, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.02)
    return False


def test_batch_queues_valid_and_reports_skips(q):
    q, _ = q
    first = api.ingest_batch(api.BatchBody(urls=[YT[0]]))
    assert len(first["queued"]) == 1
    res = api.ingest_batch(api.BatchBody(urls=[YT[1], YT[2], "https://example.com/x", YT[0], YT[1]]))
    assert len(res["queued"]) == 2
    reasons = sorted(s["reason"] for s in res["skipped"])
    assert reasons == ["already in library", "duplicate in this batch", "not a YouTube or X video link"]


def test_queue_positions_in_order(q):
    q, _ = q
    res = api.ingest_batch(api.BatchBody(urls=YT))
    rows = {r["id"]: r for r in api.list_briefs()}
    assert [rows[i]["queue_position"] for i in res["queued"]] == [1, 2, 3]
    assert api.health()["queue_length"] == 3


def test_resolver_fills_titles_while_queued(q):
    q, _ = q
    res = api.ingest_batch(api.BatchBody(urls=YT[:1]))
    bid = res["queued"][0]
    assert wait_for(lambda: q.get_brief(bid)["title"] == "Title aaa")
    assert q.get_brief(bid)["status"] == "queued"


def test_cancel_queued_is_immediate_and_never_runs(q, monkeypatch):
    q, workers = q
    ran = []
    monkeypatch.setattr(api.pipeline, "process", lambda bid, *a, **k: ran.append(bid))
    ids = api.ingest_batch(api.BatchBody(urls=YT))["queued"]
    api.cancel(ids[1])
    assert q.get_brief(ids[1])["status"] == "cancelled"
    assert "queue_position" not in {r["id"]: r for r in api.list_briefs()}[ids[1]]
    start_worker(workers)
    assert wait_for(lambda: len(ran) == 2)
    time.sleep(0.1)
    assert ran == [ids[0], ids[2]]


def test_jobs_run_one_at_a_time(q, monkeypatch):
    q, workers = q
    running, peak, done = [0], [0], []

    def fake(bid, *a, **k):
        running[0] += 1
        peak[0] = max(peak[0], running[0])
        time.sleep(0.05)
        running[0] -= 1
        done.append(bid)

    monkeypatch.setattr(api.pipeline, "process", fake)
    for _ in range(2):
        start_worker(workers)  # even with two workers started by mistake
    ids = api.ingest_batch(api.BatchBody(urls=YT))["queued"]
    assert wait_for(lambda: len(done) == 3)
    assert done == ids
    assert peak[0] == 1


def test_errored_url_is_requeued_not_duplicated(q):
    q, _ = q
    bid = api.ingest_batch(api.BatchBody(urls=YT[:1]))["queued"][0]
    api._pending.clear()
    q.update(bid, status="error")
    res = api.ingest_batch(api.BatchBody(urls=[YT[0]]))
    assert res["queued"] == [bid]
    assert len(q.list_briefs()) == 1


def test_library_update_merges_without_clobbering(q):
    q, _ = q
    row = q.upsert_brief({"id": "x1", "status": "running", "title": "Resolving…"})
    assert q.update("x1", only_if_status={"queued"}, title="Late title") is None
    assert q.get_brief("x1")["title"] == "Resolving…"
    q.update("x1", stage="transcribing")
    assert q.get_brief("x1")["status"] == "running" and q.get_brief("x1")["stage"] == "transcribing"
    assert row["id"] == "x1"

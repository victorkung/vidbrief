import threading
import time

from vidbrief.modellock import model_slot


def test_model_slot_serializes_and_reports_waiting(tmp_path):
    lock = tmp_path / "model.lock"
    inside, peak, waited = [0], [0], []

    def job(name):
        with model_slot(on_wait=lambda: waited.append(name), path=lock):
            inside[0] += 1
            peak[0] = max(peak[0], inside[0])
            time.sleep(0.1)
            inside[0] -= 1

    threads = [threading.Thread(target=job, args=(n,)) for n in ("a", "b", "c")]
    for t in threads:
        t.start()
        time.sleep(0.01)
    for t in threads:
        t.join()
    assert peak[0] == 1
    assert len(waited) == 2

import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from app import JobQueue, QueueError, make_server


class QueueHTTPCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "test.sqlite3"
        self.server = make_server(port=0, db_path=self.db)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.temp.cleanup()

    def request(self, path, method="GET", payload=None):
        body = None if payload is None else json.dumps(payload).encode()
        req = urllib.request.Request(self.base + path, data=body, method=method,
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=3) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def wait_status(self, job_id, status, timeout=4):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            result = self.request(f"/api/jobs/{job_id}")[1]
            if result["status"] == status:
                return result
            time.sleep(.02)
        self.fail(f"job {job_id} did not reach {status}")

    def test_normal_job_completes(self):
        code, job = self.request("/api/jobs", "POST", {"title": "normal", "duration_ms": 100})
        self.assertEqual(code, 201)
        self.assertEqual(self.wait_status(job["id"], "completed")["attempt"], 1)

    def test_invalid_input_and_http_codes(self):
        self.assertEqual(self.request("/api/jobs", "POST", {"title": "", "duration_ms": 100})[0], 400)
        self.assertEqual(self.request("/api/jobs", "POST", {"title": "x", "duration_ms": 99})[0], 400)
        self.assertEqual(self.request("/api/jobs?status=bogus")[0], 400)
        self.assertEqual(self.request("/api/jobs/missing")[0], 404)
        _, job = self.request("/api/jobs", "POST", {"title": "x", "duration_ms": 100})
        self.wait_status(job["id"], "completed")
        self.assertEqual(self.request(f"/api/jobs/{job['id']}/retry", "POST", {})[0], 409)

    def test_concurrent_registration_never_exceeds_two_running(self):
        errors = []
        def add(i):
            try:
                self.request("/api/jobs", "POST", {"title": f"job-{i}", "duration_ms": 450})
            except Exception as e:
                errors.append(e)
        makers = [threading.Thread(target=add, args=(i,)) for i in range(12)]
        for t in makers: t.start()
        for t in makers: t.join()
        self.assertFalse(errors)
        peak = 0
        end = time.monotonic() + 4
        while time.monotonic() < end and self.request("/api/stats")[1]["queued"]:
            peak = max(peak, self.request("/api/stats")[1]["running_count"])
            time.sleep(.01)
        self.assertLessEqual(peak, 2)
        end = time.monotonic() + 4
        while time.monotonic() < end and self.request("/api/stats")[1]["completed"] < 12:
            time.sleep(.02)
        self.assertEqual(self.request("/api/stats")[1]["completed"], 12)

    def test_cancel_running_job(self):
        _, job = self.request("/api/jobs", "POST", {"title": "cancel", "duration_ms": 1800})
        self.wait_status(job["id"], "running")
        self.assertEqual(self.request(f"/api/jobs/{job['id']}/cancel", "POST", {})[1]["status"], "cancelled")
        time.sleep(.15)
        self.assertEqual(self.request(f"/api/jobs/{job['id']}")[1]["status"], "cancelled")

    def test_cancel_queued_job(self):
        running = [self.request("/api/jobs", "POST", {"title": f"block-{n}", "duration_ms": 900})[1]
                   for n in range(2)]
        for job in running:
            self.wait_status(job["id"], "running")
        _, queued = self.request("/api/jobs", "POST", {"title": "queued cancel", "duration_ms": 100})
        self.assertEqual(self.request(f"/api/jobs/{queued['id']}/cancel", "POST", {})[1]["status"], "cancelled")

    def test_first_attempt_fails_then_retry_succeeds(self):
        _, job = self.request("/api/jobs", "POST", {"title": "retry", "duration_ms": 100, "fail_first_attempt": True})
        failed = self.wait_status(job["id"], "failed")
        self.assertEqual(failed["attempt"], 1)
        code, retried = self.request(f"/api/jobs/{job['id']}/retry", "POST", {})
        self.assertEqual(code, 200)
        self.assertEqual(retried["id"], job["id"])
        complete = self.wait_status(job["id"], "completed")
        self.assertEqual(complete["attempt"], 2)

    def test_simultaneous_retry_requests_only_enqueue_once(self):
        _, job = self.request("/api/jobs", "POST", {"title": "only once", "duration_ms": 100, "fail_first_attempt": True})
        self.wait_status(job["id"], "failed")
        barrier = threading.Barrier(8)
        results = []
        def retry():
            barrier.wait()
            results.append(self.request(f"/api/jobs/{job['id']}/retry", "POST", {})[0])
        threads = [threading.Thread(target=retry) for _ in range(8)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(results.count(200), 1)
        self.assertEqual(results.count(409), 7)
        self.wait_status(job["id"], "completed")
        self.assertEqual(self.request(f"/api/jobs/{job['id']}")[1]["attempt"], 2)

    def test_cancel_then_retry_ignores_old_worker_result(self):
        _, job = self.request("/api/jobs", "POST", {"title": "generation guard", "duration_ms": 1500})
        self.wait_status(job["id"], "running")
        self.request(f"/api/jobs/{job['id']}/cancel", "POST", {})
        self.request(f"/api/jobs/{job['id']}/retry", "POST", {})
        self.assertEqual(self.wait_status(job["id"], "completed")["attempt"], 2)
        events = self.request("/api/events")[1]
        states = [e["new_status"] for e in reversed(events) if e["job_id"] == job["id"]]
        self.assertEqual(states, ["queued", "running", "cancelled", "queued", "running", "completed"])

    def test_restart_recovers_running_jobs(self):
        # A zero-worker instance leaves recovered work queued for deterministic inspection.
        path = Path(self.temp.name) / "restart.sqlite3"
        first = JobQueue(path, workers=0)
        created = first.create({"title": "recover", "duration_ms": 100})
        with first._connect() as db:
            first._transition(db, created["id"], "running")
        first.close()
        restarted = JobQueue(path, workers=0)
        try:
            self.assertEqual(restarted.get(created["id"])["status"], "queued")
            transitions = [e["new_status"] for e in restarted.events() if e["job_id"] == created["id"]]
            self.assertEqual(transitions, ["queued", "running", "queued"])
        finally:
            restarted.close()

    def test_persistence_and_atomic_event_history(self):
        _, job = self.request("/api/jobs", "POST", {"title": "persist", "duration_ms": 100})
        self.wait_status(job["id"], "completed")
        q = self.server.queue
        events = [e for e in q.events() if e["job_id"] == job["id"]]
        self.assertEqual([e["new_status"] for e in reversed(events)], ["queued", "running", "completed"])
        with q._connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events WHERE job_id=?", (job["id"],)).fetchone()[0], 3)
        self.assertEqual(q.get(job["id"])["status"], "completed")


if __name__ == "__main__":
    unittest.main()

import concurrent.futures
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from queue_server import JobQueue, QueueHTTPServer


class QueueTests(unittest.TestCase):
    def setUp(self):
        # Keep even temporary databases inside the requested workspace.
        root = Path(__file__).resolve().parents[1] / '.test-tmp'
        root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=root)
        self.path = Path(self.temp.name) / 'test.sqlite3'
        self.start()

    def start(self):
        self.queue = JobQueue(self.path)
        self.server = QueueHTTPServer(('127.0.0.1', 0), self.queue)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': .01}, name='test-http-server')
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.server.server_port}'

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)
        self.queue.close()
        self.assertFalse(self.thread.is_alive())
        self.assertTrue(all(not worker.is_alive() for worker in self.queue.workers))

    def tearDown(self):
        self.stop()
        self.temp.cleanup()

    def request(self, path, data=None, raw=None):
        body = raw if raw is not None else json.dumps(data).encode() if data is not None else None
        req = Request(self.base + path, data=body, headers={'Content-Type':'application/json'})
        try:
            with urlopen(req, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            with error:
                return error.code, json.load(error)

    def create(self, duration=100, fail=False, title='Test job'):
        status, job = self.request('/api/jobs', {'title':title, 'duration_ms':duration, 'fail_first_attempt':fail})
        self.assertEqual(status, 201)
        return job

    def wait_for(self, job_id, state, timeout=6):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            code, job = self.request(f'/api/jobs/{job_id}')
            self.assertEqual(code, 200)
            if job['status'] == state:
                return job
            time.sleep(.01)
        self.fail(f'Job {job_id}: expected {state}, got {job}')

    def test_create_complete_and_static_dashboard(self):
        job = self.create(title='<script>alert("x")</script>')
        result = self.wait_for(job['id'], 'completed')
        self.assertEqual(result['title'], job['title'])
        self.assertEqual(result['attempt'], 1)
        self.assertTrue(all(result[key] for key in ('created_at','started_at','ended_at')))
        self.assertEqual(self.request('/api/jobs?status=completed')[1]['jobs'][0]['id'], job['id'])
        for path in ('/', '/app.js', '/style.css'):
            with urlopen(self.base + path) as response:
                self.assertEqual(response.status, 200)
                self.assertGreater(len(response.read()), 100)
                self.assertIn("script-src 'self'", response.headers['Content-Security-Policy'])

    def test_validation_and_http_codes(self):
        invalid = [{}, [], {'title':'', 'duration_ms':100}, {'title':'x','duration_ms':True},
                   {'title':'x','duration_ms':99}, {'title':'x','duration_ms':5001},
                   {'title':'x','duration_ms':100.5}, {'title':'x','duration_ms':100,'fail_first_attempt':1},
                   {'title':'x'*201,'duration_ms':100}, {'title':'\ud800','duration_ms':100},
                   {'title':'x','duration_ms':100,'extra':1}]
        for data in invalid:
            with self.subTest(data=data):
                self.assertEqual(self.request('/api/jobs', data)[0], 400)
        self.assertEqual(self.request('/api/jobs', raw=b'{broken')[0], 400)
        for path in ('/api/jobs?status=unknown', '/api/jobs?status=', '/api/jobs?status=queued&status=running', '/api/jobs?bad=1', '/api/jobs/nope'):
            self.assertEqual(self.request(path)[0], 400)
        for path, data in [('/api/jobs/999', None), ('/api/jobs/999/cancel', {}), ('/api/jobs/999/retry', {}), ('/api/missing', None)]:
            self.assertEqual(self.request(path, data)[0], 404)
        job = self.create(600)
        self.assertEqual(self.request(f"/api/jobs/{job['id']}/retry", {})[0], 409)
        self.assertEqual(self.request(f"/api/jobs/{job['id']}/cancel", {'bad':True})[0], 400)
        self.wait_for(job['id'], 'completed')
        for action in ('retry','cancel'):
            self.assertEqual(self.request(f"/api/jobs/{job['id']}/{action}", {})[0], 409)

    def test_concurrent_submission_limit_and_fifo(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            jobs = list(pool.map(lambda _: self.create(250), range(12)))
        max_observed = 0
        deadline = time.monotonic() + 8
        while True:
            stats = self.request('/api/stats')[1]
            max_observed = max(max_observed, stats['running'])
            self.assertLessEqual(stats['running'], 2)
            self.assertLessEqual(stats['active_workers'], 2)
            if stats['counts']['completed'] == len(jobs):
                break
            self.assertLess(time.monotonic(), deadline)
            time.sleep(.005)
        self.assertEqual(max_observed, 2)
        events = self.request('/api/events')[1]['events']
        queued = [event['job_id'] for event in events if event['to_status'] == 'queued']
        started = [event['job_id'] for event in events if event['to_status'] == 'running']
        self.assertEqual(queued, started)
        active = set()
        for event in events:
            if event['to_status'] == 'running':
                active.add(event['job_id'])
            elif event['to_status'] == 'completed':
                active.remove(event['job_id'])
            self.assertLessEqual(len(active), 2)
        self.assertFalse(active)

    def test_running_cancel_and_duplicate_cancel(self):
        job = self.create(5000)
        self.wait_for(job['id'], 'running')
        start = time.monotonic()
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.request(f"/api/jobs/{job['id']}/cancel", {}), range(8)))
        self.assertTrue(all(code == 200 and value['status'] == 'cancelled' for code, value in results))
        self.assertLess(time.monotonic() - start, 2)
        deadline = time.monotonic() + 1
        while self.queue.stats()['active_workers'] and time.monotonic() < deadline:
            time.sleep(.005)
        self.assertEqual(self.queue.stats()['active_workers'], 0)
        events = self.request('/api/events')[1]['events']
        self.assertEqual(sum(event['to_status'] == 'cancelled' for event in events), 1)

    def test_first_failure_retry_success(self):
        job = self.create(fail=True)
        self.wait_for(job['id'], 'failed')
        code, retry = self.request(f"/api/jobs/{job['id']}/retry", {})
        self.assertEqual(code, 200)
        self.assertEqual(retry['id'], job['id'])
        self.assertEqual(retry['attempt'], 2)
        self.assertIsNone(retry['started_at'])
        self.assertIsNone(retry['ended_at'])
        self.wait_for(job['id'], 'completed')

    def test_simultaneous_retry_only_once(self):
        job = self.create(700, True)
        self.wait_for(job['id'], 'failed')
        barrier = threading.Barrier(12)
        def retry(_):
            barrier.wait()
            return self.request(f"/api/jobs/{job['id']}/retry", {})[0]
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
            codes = list(pool.map(retry, range(12)))
        self.assertEqual(codes.count(200), 1)
        self.assertEqual(codes.count(409), 11)
        self.assertEqual(self.wait_for(job['id'], 'completed')['attempt'], 2)
        events = self.queue.events()
        self.assertEqual(sum(event['reason'] == 'user_retry' for event in events), 1)
        self.assertEqual(sum(event['to_status'] == 'running' for event in events), 2)

    def test_cancel_retry_stale_worker_cannot_overwrite(self):
        old_waiting, release_old = threading.Event(), threading.Event()
        simulate = self.queue._simulate
        def controlled(row, signal):
            if row['attempt'] == 1:
                old_waiting.set()
                # Force the dangerous interleaving: old execution returns a normal
                # completion only AFTER attempt 2 has already started.
                signal.wait(3)
                release_old.wait(3)
                return False
            return simulate(row, signal)
        self.queue._simulate = controlled
        try:
            job = self.create(800)
            self.assertTrue(old_waiting.wait(2))
            self.assertEqual(self.request(f"/api/jobs/{job['id']}/cancel", {})[0], 200)
            self.assertEqual(self.request(f"/api/jobs/{job['id']}/retry", {})[0], 200)
            second = self.wait_for(job['id'], 'running')
            self.assertEqual(second['attempt'], 2)
            release_old.set()
            time.sleep(.05)
            current = self.request(f"/api/jobs/{job['id']}")[1]
            self.assertEqual(current['status'], 'running')
            self.assertEqual(current['started_at'], second['started_at'])
            self.assertIsNone(current['ended_at'])
            self.wait_for(job['id'], 'completed')
            terminal = [event for event in self.queue.events() if event['to_status'] == 'completed']
            self.assertEqual([event['attempt'] for event in terminal], [2])
        finally:
            release_old.set()

    def test_restart_recovers_running_and_queued(self):
        jobs = [self.create(500) for _ in range(3)]
        self.wait_for(jobs[0]['id'], 'running')
        self.wait_for(jobs[1]['id'], 'running')
        self.stop()
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM jobs WHERE status='running'").fetchone()[0], 2)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM jobs WHERE status='queued'").fetchone()[0], 1)
        self.start()
        for job in jobs:
            self.assertEqual(self.wait_for(job['id'], 'completed')['attempt'], 1)
        recovered = [event for event in self.queue.events() if event['reason'] == 'server_restart']
        self.assertEqual(len(recovered), 2)
        self.assertTrue(all(event['from_status'] == 'running' and event['to_status'] == 'queued' for event in recovered))

    def test_persistence_and_transactional_history(self):
        job = self.create(fail=True)
        self.wait_for(job['id'], 'failed')
        self.request(f"/api/jobs/{job['id']}/retry", {})
        finished = self.wait_for(job['id'], 'completed')
        before = self.request('/api/events')[1]['events']
        self.stop()
        self.start()
        self.assertEqual(self.request(f"/api/jobs/{job['id']}")[1], finished)
        self.assertEqual(self.request('/api/events')[1]['events'], before)
        self.assertEqual([event['to_status'] for event in before], ['queued','running','failed','queued','running','completed'])
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
            self.assertEqual(db.execute('SELECT status,attempt FROM jobs WHERE id=?', (job['id'],)).fetchone(),
                             (before[-1]['to_status'], before[-1]['attempt']))

    def test_queued_cancel_retry_and_transaction_rollback(self):
        for _ in range(2):
            self.create(1000)
        job = self.create(100)
        self.assertEqual(self.request(f"/api/jobs/{job['id']}/cancel", {})[1]['status'], 'cancelled')
        before = self.queue.events()
        # Force an actual SQLite failure between event insertion and row update.
        with self.queue.condition, self.queue.db:
            self.queue.db.execute("CREATE TRIGGER reject_retry BEFORE UPDATE ON jobs WHEN NEW.attempt=2 BEGIN SELECT RAISE(ABORT, 'test rollback'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.queue.change(job['id'], 'retry')
        self.assertEqual(self.queue.get(job['id'])['status'], 'cancelled')
        self.assertEqual(self.queue.events(), before)
        with self.queue.condition, self.queue.db:
            self.queue.db.execute('DROP TRIGGER reject_retry')
        self.assertEqual(self.request(f"/api/jobs/{job['id']}/retry", {})[0], 200)
        self.wait_for(job['id'], 'completed')


if __name__ == '__main__':
    unittest.main()

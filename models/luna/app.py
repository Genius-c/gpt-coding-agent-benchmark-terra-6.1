"""SQLite backed simulated asynchronous job queue."""
from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
STATUSES = ("queued", "running", "completed", "failed", "cancelled")


def now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class QueueError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


class JobQueue:
    def __init__(self, db_path=None, workers=2):
        self.db_path = str(db_path or ROOT / "jobs.sqlite3")
        self.lock = threading.RLock()
        self.cv = threading.Condition(self.lock)
        self.stopping = False
        self.worker_count = workers
        self.active = {}  # job id -> (generation, cancellation event)
        self.threads = []
        self._init_db()
        with self._connect() as db:
            rows = db.execute("SELECT id FROM jobs WHERE status='running'").fetchall()
            for (job_id,) in rows:
                self._transition(db, job_id, "queued", "Recovered after server restart", allow_running=True)
        self.start()

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _init_db(self):
        with self._connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS jobs (
              id TEXT PRIMARY KEY, title TEXT NOT NULL, duration_ms INTEGER NOT NULL,
              fail_first_attempt INTEGER NOT NULL, status TEXT NOT NULL,
              attempt INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
              started_at TEXT, finished_at TEXT, generation INTEGER NOT NULL DEFAULT 0,
              error TEXT
            );
            CREATE INDEX IF NOT EXISTS jobs_status_created ON jobs(status, created_at);
            CREATE TABLE IF NOT EXISTS events (
              id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL,
              old_status TEXT, new_status TEXT NOT NULL, at TEXT NOT NULL, detail TEXT,
              FOREIGN KEY(job_id) REFERENCES jobs(id)
            );
            """)

    def _transition(self, db, job_id, status, detail=None, *, allow_running=False):
        row = db.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise QueueError(404, "Job not found")
        old = row["status"]
        allowed = {"queued": {"running", "cancelled"}, "running": {"completed", "failed", "cancelled", "queued"},
                   "failed": {"queued"}, "cancelled": {"queued"}, "completed": set()}
        if status not in allowed[old] or (status == "queued" and old == "running" and not allow_running):
            raise QueueError(409, f"Cannot change job from {old} to {status}")
        stamp = now()
        started = stamp if status == "running" else None
        finished = stamp if status in ("completed", "failed", "cancelled") else None
        db.execute("UPDATE jobs SET status=?, started_at=COALESCE(?,started_at), finished_at=?, error=? WHERE id=?",
                   (status, started, finished, detail if status == "failed" else None, job_id))
        db.execute("INSERT INTO events(job_id,old_status,new_status,at,detail) VALUES(?,?,?,?,?)",
                   (job_id, old, status, stamp, detail))

    def start(self):
        with self.cv:
            if self.threads:
                return
            self.stopping = False
            self.threads = [threading.Thread(target=self._worker, name=f"job-worker-{i+1}", daemon=True)
                            for i in range(self.worker_count)]
            for thread in self.threads:
                thread.start()
            self.cv.notify_all()

    def close(self):
        with self.cv:
            self.stopping = True
            for _, cancel in self.active.values():
                cancel.set()
            self.cv.notify_all()
        for thread in self.threads:
            thread.join(timeout=3)
        self.threads.clear()

    def create(self, data):
        if not isinstance(data, dict):
            raise QueueError(400, "JSON object required")
        title, duration, fail = data.get("title"), data.get("duration_ms"), data.get("fail_first_attempt", False)
        if not isinstance(title, str) or not title.strip() or len(title) > 200:
            raise QueueError(400, "title must be a non-empty string of at most 200 characters")
        if isinstance(duration, bool) or not isinstance(duration, int) or not 100 <= duration <= 5000:
            raise QueueError(400, "duration_ms must be an integer from 100 to 5000")
        if not isinstance(fail, bool):
            raise QueueError(400, "fail_first_attempt must be a boolean")
        job_id, stamp = str(uuid.uuid4()), now()
        with self.cv, self._connect() as db:
            db.execute("INSERT INTO jobs(id,title,duration_ms,fail_first_attempt,status,created_at) VALUES(?,?,?,?,?,?)",
                       (job_id, title.strip(), duration, int(fail), "queued", stamp))
            db.execute("INSERT INTO events(job_id,old_status,new_status,at,detail) VALUES(?,NULL,'queued',?,?)",
                       (job_id, stamp, "Created"))
            self.cv.notify_all()
        return self.get(job_id)

    def get(self, job_id):
        with self._connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise QueueError(404, "Job not found")
        return dict(row)

    def list_jobs(self, status=None):
        if status is not None and status not in STATUSES:
            raise QueueError(400, "Invalid status filter")
        with self._connect() as db:
            query = "SELECT * FROM jobs" + (" WHERE status=?" if status else "") + " ORDER BY rowid"
            rows = db.execute(query, (status,) if status else ()).fetchall()
        return [dict(r) for r in rows]

    def cancel(self, job_id):
        with self.cv, self._connect() as db:
            job = db.execute("SELECT status,generation FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not job:
                raise QueueError(404, "Job not found")
            if job["status"] not in ("queued", "running"):
                raise QueueError(409, f"Cannot cancel job in {job['status']} state")
            self._transition(db, job_id, "cancelled", "Cancelled by request")
            running = self.active.get(job_id)
            if running and running[0] == job["generation"]:
                running[1].set()
            self.cv.notify_all()
        return self.get(job_id)

    def retry(self, job_id):
        with self.cv, self._connect() as db:
            row = db.execute("SELECT status FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                raise QueueError(404, "Job not found")
            if row["status"] not in ("failed", "cancelled"):
                raise QueueError(409, f"Cannot retry job in {row['status']} state")
            # Attempts count actual worker starts; the worker increments once when it claims this retry.
            db.execute("UPDATE jobs SET generation=generation+1,started_at=NULL,finished_at=NULL,error=NULL WHERE id=?", (job_id,))
            self._transition(db, job_id, "queued", "Retry requested")
            self.cv.notify_all()
        return self.get(job_id)

    def stats(self):
        with self._connect() as db:
            counts = {s: 0 for s in STATUSES}
            counts.update({r["status"]: r["n"] for r in db.execute("SELECT status,COUNT(*) n FROM jobs GROUP BY status")})
        counts["running_count"] = counts["running"]
        return counts

    def events(self):
        with self._connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM events ORDER BY id DESC")]

    def _worker(self):
        while True:
            with self.cv:
                if self.stopping:
                    return
                with self._connect() as db:
                    row = db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY rowid LIMIT 1").fetchone()
                    if row:
                        jid = row["id"]
                        self._transition(db, jid, "running")
                        db.execute("UPDATE jobs SET attempt=attempt+1,generation=generation+1 WHERE id=?", (jid,))
                        updated = db.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
                        generation = updated["generation"]
                        cancel = threading.Event()
                        self.active[jid] = (generation, cancel)
                    else:
                        self.cv.wait(timeout=0.5)
                        continue
            # Work is deliberately simulated; no external process is started.
            cancel.wait(row["duration_ms"] / 1000)
            with self.cv, self._connect() as db:
                active = self.active.get(jid)
                current = db.execute("SELECT status,generation,attempt,fail_first_attempt FROM jobs WHERE id=?", (jid,)).fetchone()
                if active == (generation, cancel) and current and current["generation"] == generation and current["status"] == "running":
                    failed = bool(current["fail_first_attempt"] and current["attempt"] == 1)
                    self._transition(db, jid, "failed" if failed else "completed", "Simulated first attempt failure" if failed else None)
                if active == (generation, cancel):
                    del self.active[jid]
                self.cv.notify_all()


class Handler(BaseHTTPRequestHandler):
    server_version = "LocalJobQueue/1.0"
    def _json(self, code, data):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw))); self.send_header("Cache-Control", "no-store")
        self.end_headers(); self.wfile.write(raw)

    def _body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 100_000: raise ValueError()
            return json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            raise QueueError(400, "Invalid JSON body")

    def _route(self):
        path = urlparse(self.path).path
        q = self.server.queue
        if path == "/" and self.command == "GET":
            html = (ROOT / "static" / "index.html").read_bytes()
            self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html))); self.end_headers(); self.wfile.write(html); return
        if path.startswith("/static/") and self.command == "GET":
            name = path.removeprefix("/static/")
            if name not in ("style.css", "app.js"): raise QueueError(404, "Not found")
            data = (ROOT / "static" / name).read_bytes()
            self.send_response(200); self.send_header("Content-Type", "text/css; charset=utf-8" if name.endswith("css") else "text/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data); return
        if path == "/api/jobs" and self.command == "POST": return self._json(201, q.create(self._body()))
        if path == "/api/jobs" and self.command == "GET":
            filt = parse_qs(urlparse(self.path).query).get("status", [None])[0]
            return self._json(200, q.list_jobs(filt))
        if path == "/api/stats" and self.command == "GET": return self._json(200, q.stats())
        if path == "/api/events" and self.command == "GET": return self._json(200, q.events())
        parts = path.strip("/").split("/")
        if len(parts) == 3 and parts[:2] == ["api", "jobs"]:
            return self._json(200, q.get(parts[2]))
        if len(parts) == 4 and parts[:2] == ["api", "jobs"] and self.command == "POST":
            if parts[3] == "cancel": return self._json(200, q.cancel(parts[2]))
            if parts[3] == "retry": return self._json(200, q.retry(parts[2]))
        raise QueueError(404, "Not found")

    def do_GET(self): self._handle()
    def do_POST(self): self._handle()
    def _handle(self):
        try: self._route()
        except QueueError as e: self._json(e.status, {"error": e.message})
        except (BrokenPipeError, ConnectionResetError): pass
        except Exception: self._json(500, {"error": "Internal server error"})
    def log_message(self, fmt, *args): pass


def make_server(host="127.0.0.1", port=8765, db_path=None):
    queue = JobQueue(db_path)
    server = ThreadingHTTPServer((host, port), Handler)
    server.daemon_threads = True
    server.queue = queue
    original_close = server.server_close
    def close():
        queue.close()
        original_close()
    server.server_close = close
    return server


def main():
    server = make_server()
    print("Dashboard: http://127.0.0.1:8765")
    try: server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt: pass
    finally: server.shutdown(); server.server_close()


if __name__ == "__main__": main()

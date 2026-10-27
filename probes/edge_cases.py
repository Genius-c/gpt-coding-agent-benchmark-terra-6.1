"""Additional queue semantics checks, separate from model-authored tests.

Run: python probes/edge_cases.py terra|luna|sol
Uses temporary SQLite databases. No model implementation files are modified.
"""
import importlib
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = sys.argv[1] if len(sys.argv) > 1 else ""
if MODEL not in ("terra", "luna", "sol"):
    raise SystemExit("usage: python probes/edge_cases.py terra|luna|sol")
sys.path.insert(0, str(ROOT / "models" / MODEL))
module = importlib.import_module("queue_server" if MODEL == "sol" else "app")
Queue = module.JobQueue if MODEL != "terra" else module.Queue


def create(q, title, duration=100, fail=False):
    return q.create({"title": title, "duration_ms": duration,
                     "fail_first_attempt": fail})


def get(q, job):
    return q.get(job["id"])


def change(q, job, action):
    if MODEL == "terra":
        return q.transition(job["id"], action)
    if MODEL == "sol":
        return q.change(job["id"], action)
    return getattr(q, action)(job["id"])


def until(q, job, states, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        row = get(q, job)
        if row["status"] in states:
            return row
        time.sleep(0.005)
    raise TimeoutError(f"job {job['id']} still {row['status']}")


def status(event):
    return event.get("new_status", event.get("to_status", event.get("status")))


def fifo_case(db):
    q = Queue(str(db))
    try:
        old = create(q, "retry-after-queue", fail=True)
        until(q, old, {"failed"})
        busy = [create(q, "blocker", 1000) for _ in range(2)]
        for item in busy:
            until(q, item, {"running"})
        prior = create(q, "queued-earlier")
        change(q, old, "retry")
        until(q, prior, {"completed"})
        until(q, old, {"completed"})
        records = sorted(q.events(), key=lambda e: e["id"])
        requeue_id = max(e["id"] for e in records
                         if e["job_id"] == old["id"] and status(e) == "queued")
        observed = [e["job_id"] for e in records
                    if e["id"] > requeue_id and status(e) == "running"
                    and e["job_id"] in (old["id"], prior["id"])]
        return {"observed": ["prior" if x == prior["id"] else "retried" for x in observed],
                "passed": observed[:2] == [prior["id"], old["id"]]}
    finally:
        q.close()


def never_started_case(db):
    q = Queue(str(db))
    try:
        busy = [create(q, "blocker", 1000) for _ in range(2)]
        for item in busy:
            until(q, item, {"running"})
        target = create(q, "unstarted", fail=True)
        initial = get(q, target)["attempt"]
        change(q, target, "cancel")
        change(q, target, "retry")
        final = until(q, target, {"failed", "completed"})
        return {"initial_attempt": initial, "final_attempt": final["attempt"],
                "first_real_execution_status": final["status"],
                "passed": final["attempt"] == 1 and final["status"] == "failed"}
    finally:
        q.close()


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    output = {"model": MODEL,
              "retry_fifo": fifo_case(root / "fifo.sqlite3"),
              "cancel_before_first_run": never_started_case(root / "never.sqlite3")}
print(json.dumps(output, indent=2, ensure_ascii=True))

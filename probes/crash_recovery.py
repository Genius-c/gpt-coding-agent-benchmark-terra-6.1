"""Abrupt process exit followed by restart with the same SQLite database.

Run: python probes/crash_recovery.py terra|luna|sol
Each invocation uses an isolated temporary database and a disposable child
process. No signal is sent to any external server.
"""
import importlib
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
model = sys.argv[1] if len(sys.argv) > 1 else ""
if model not in {"terra", "luna", "sol"}:
    raise SystemExit("usage: python probes/crash_recovery.py terra|luna|sol")
src = ROOT / "models" / model
module = "queue_server" if model == "sol" else "app"
cls = "Queue" if model == "terra" else "JobQueue"
with tempfile.TemporaryDirectory() as directory:
    database = Path(directory) / "crash.sqlite3"
    child = (
        "import sys,time,os\n"
        f"sys.path.insert(0,{str(src)!r})\n"
        f"from {module} import {cls}\n"
        f"q={cls}({str(database)!r})\n"
        "job=q.create({'title':'crash-test','duration_ms':1800,'fail_first_attempt':True})\n"
        "while q.get(job['id'])['status']!='running': time.sleep(.005)\n"
        "print(job['id'],flush=True)\n"
        "os._exit(0)\n"
    )
    p = subprocess.run([sys.executable, "-c", child], capture_output=True,
                       text=True, timeout=12)
    if p.returncode:
        raise RuntimeError(p.stderr)
    sys.path.insert(0, str(src))
    Queue = getattr(importlib.import_module(module), cls)
    q = Queue(str(database))
    try:
        job_id = p.stdout.strip()
        if model != "luna":
            job_id = int(job_id)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            row = q.get(job_id)
            if row["status"] in ("completed", "failed"):
                break
            time.sleep(.01)
        else:
            raise TimeoutError("recovered job did not finish")
        result = {"model": model, "status": row["status"],
                  "attempt": row["attempt"],
                  "passed": row["status"] == "completed" and row["attempt"] == 2}
        print(json.dumps(result, indent=2))
    finally:
        q.close()

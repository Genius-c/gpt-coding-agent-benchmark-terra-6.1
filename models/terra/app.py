import json
import sqlite3
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parent
STATES = ('queued', 'running', 'completed', 'failed', 'cancelled')

def now():
    return datetime.now(timezone.utc).isoformat()

class Conflict(Exception): pass
class Missing(Exception): pass

class Queue:
    def __init__(self, path):
        self.lock = threading.RLock()
        self.wake = threading.Condition(self.lock)
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, duration_ms INTEGER NOT NULL, fail_first_attempt INTEGER NOT NULL, status TEXT NOT NULL, attempt INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL, started_at TEXT, ended_at TEXT, generation INTEGER NOT NULL DEFAULT 0, queue_order INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER NOT NULL, status TEXT NOT NULL, attempt INTEGER NOT NULL, created_at TEXT NOT NULL);
        ''')
        self.stopping = False
        with self.lock, self.db:
            for row in self.db.execute("SELECT * FROM jobs WHERE status='running'").fetchall():
                self.db.execute("UPDATE jobs SET status='queued', generation=generation+1, started_at=NULL, ended_at=NULL WHERE id=?", (row['id'],))
                self.event(row['id'], 'queued', row['attempt'])
        self.workers = [threading.Thread(target=self.worker, name=f'queue-worker-{i}') for i in range(2)]
        for worker in self.workers: worker.start()

    def event(self, job_id, status, attempt):
        self.db.execute('INSERT INTO events(job_id,status,attempt,created_at) VALUES (?,?,?,?)', (job_id, status, attempt, now()))

    def item(self, row):
        if row is None: raise Missing()
        d = dict(row); d['fail_first_attempt'] = bool(d['fail_first_attempt']); d.pop('generation'); d.pop('queue_order')
        return d

    def get(self, job_id):
        with self.lock: return self.item(self.db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone())

    def list(self, status=None):
        with self.lock:
            rows = self.db.execute('SELECT * FROM jobs' + (' WHERE status=?' if status else '') + ' ORDER BY id DESC', (status,) if status else ()).fetchall()
            return [self.item(r) for r in rows]

    def create(self, data):
        if not isinstance(data, dict) or set(data) != {'title','duration_ms','fail_first_attempt'}: raise ValueError('title, duration_ms, fail_first_attempt가 필요합니다.')
        title, duration, fail = data['title'], data['duration_ms'], data['fail_first_attempt']
        if not isinstance(title, str) or not title.strip() or len(title) > 200: raise ValueError('제목은 1~200자여야 합니다.')
        if type(duration) is not int or not 100 <= duration <= 5000 or type(fail) is not bool: raise ValueError('실행 시간 또는 실패 설정이 올바르지 않습니다.')
        with self.wake, self.db:
            order = self.db.execute('SELECT COALESCE(MAX(queue_order),0)+1 FROM jobs').fetchone()[0]
            cur = self.db.execute("INSERT INTO jobs(title,duration_ms,fail_first_attempt,status,created_at,queue_order) VALUES (?,?,?,'queued',?,?)", (title.strip(),duration,int(fail),now(),order))
            self.event(cur.lastrowid, 'queued', 0)
            result = self.get(cur.lastrowid)
            self.wake.notify_all()
            return result

    def transition(self, job_id, action):
        with self.wake, self.db:
            row = self.db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
            if row is None: raise Missing()
            if action == 'cancel':
                if row['status'] == 'cancelled': return self.item(row)
                if row['status'] not in ('queued','running'): raise Conflict()
                self.db.execute("UPDATE jobs SET status='cancelled', ended_at=?, generation=generation+1 WHERE id=?", (now(),job_id))
                self.event(job_id, 'cancelled', row['attempt'])
            else:
                if row['status'] not in ('failed','cancelled'): raise Conflict()
                order = self.db.execute('SELECT COALESCE(MAX(queue_order),0)+1 FROM jobs').fetchone()[0]
                self.db.execute("UPDATE jobs SET status='queued', started_at=NULL, ended_at=NULL, generation=generation+1, queue_order=? WHERE id=?", (order,job_id))
                self.event(job_id, 'queued', row['attempt'])
            result = self.get(job_id)
            self.wake.notify_all()
            return result

    def worker(self):
        while True:
            with self.wake:
                while not self.stopping:
                    row = self.db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY queue_order,id LIMIT 1").fetchone()
                    if row: break
                    self.wake.wait()
                if self.stopping: return
                with self.db:
                    attempt = row['attempt'] + 1
                    generation = row['generation'] + 1
                    self.db.execute("UPDATE jobs SET status='running', attempt=?, generation=?, started_at=?, ended_at=NULL WHERE id=?", (attempt,generation,now(),row['id']))
                    self.event(row['id'], 'running', attempt)
                deadline = time.monotonic() + row['duration_ms']/1000
                while not self.stopping:
                    current = self.db.execute('SELECT status,generation FROM jobs WHERE id=?', (row['id'],)).fetchone()
                    if current['status'] != 'running' or current['generation'] != generation: break
                    remaining = deadline-time.monotonic()
                    if remaining <= 0:
                        status = 'failed' if row['fail_first_attempt'] and attempt == 1 else 'completed'
                        with self.db:
                            self.db.execute('UPDATE jobs SET status=?, ended_at=? WHERE id=? AND status=\'running\' AND generation=?', (status,now(),row['id'],generation))
                            self.event(row['id'], status, attempt)
                        break
                    self.wake.wait(remaining)
                if self.stopping: return

    def stats(self):
        with self.lock:
            counts = {s: 0 for s in STATES}
            for row in self.db.execute('SELECT status, COUNT(*) AS n FROM jobs GROUP BY status'): counts[row['status']] = row['n']
            return {'counts': counts, 'running': counts['running']}

    def events(self):
        with self.lock: return [dict(r) for r in self.db.execute('SELECT * FROM events ORDER BY id DESC')]

    def close(self):
        with self.wake:
            self.stopping = True
            self.wake.notify_all()
        for worker in self.workers: worker.join()
        with self.lock: self.db.close()

class Server(ThreadingHTTPServer):
    daemon_threads = False
    def __init__(self, address, db_path):
        self.queue = Queue(db_path)
        try: super().__init__(address, Handler)
        except BaseException:
            self.queue.close(); raise
    def server_close(self):
        super().server_close()
        self.queue.close()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args): pass
    def send_json(self, status, value):
        body = json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(status); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    def handle_api(self):
        parsed = urlparse(self.path); parts = parsed.path.strip('/').split('/'); q = self.server.queue
        try:
            if self.command == 'GET' and parts == ['api','jobs']:
                params = parse_qs(parsed.query, keep_blank_values=True)
                if set(params) - {'status'} or ('status' in params and (len(params['status']) != 1 or params['status'][0] not in STATES)): raise ValueError('상태 필터가 올바르지 않습니다.')
                return self.send_json(200,q.list(params.get('status',[None])[0]))
            if self.command == 'GET' and parts == ['api','stats']: return self.send_json(200,q.stats())
            if self.command == 'GET' and parts == ['api','events']: return self.send_json(200,q.events())
            if len(parts) >= 3 and parts[:2] == ['api','jobs'] and parts[2].isdigit():
                job_id = int(parts[2])
                if self.command == 'GET' and len(parts) == 3: return self.send_json(200,q.get(job_id))
                if self.command == 'POST' and len(parts) == 4 and parts[3] in ('cancel','retry'): return self.send_json(200,q.transition(job_id,parts[3]))
            if self.command == 'POST' and parts == ['api','jobs']:
                try:
                    length = int(self.headers.get('Content-Length','0'))
                    if length <= 0 or length > 65536: raise ValueError()
                    data = json.loads(self.rfile.read(length).decode('utf-8'))
                except (ValueError, UnicodeError): raise ValueError('JSON 요청 본문이 올바르지 않습니다.')
                return self.send_json(201,q.create(data))
            self.send_json(404,{'error':'경로를 찾을 수 없습니다.'})
        except ValueError as e: self.send_json(400,{'error':str(e)})
        except Missing: self.send_json(404,{'error':'작업을 찾을 수 없습니다.'})
        except Conflict: self.send_json(409,{'error':'현재 상태에서 허용되지 않는 요청입니다.'})
    def do_GET(self):
        if self.path.startswith('/api/'): return self.handle_api()
        files = {'/':('index.html','text/html'), '/style.css':('style.css','text/css'), '/app.js':('app.js','application/javascript')}
        item = files.get(urlparse(self.path).path)
        if not item: return self.send_error(404)
        body = (ROOT/'static'/item[0]).read_bytes()
        self.send_response(200); self.send_header('Content-Type',item[1]+'; charset=utf-8'); self.send_header('Content-Length',str(len(body))); self.end_headers(); self.wfile.write(body)
    def do_POST(self):
        if self.path.startswith('/api/'): return self.handle_api()
        self.send_json(404,{'error':'경로를 찾을 수 없습니다.'})

def main():
    server = Server(('127.0.0.1',8765), ROOT/'jobs.sqlite3')
    print('http://127.0.0.1:8765', flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__ == '__main__': main()

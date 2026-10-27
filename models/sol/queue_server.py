"""SQLite-backed simulated queue. All state transitions share one transaction lock."""
import json
import sqlite3
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

STATES = ('queued', 'running', 'completed', 'failed', 'cancelled')


def now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


class APIError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


class JobQueue:
    def __init__(self, db_path):
        self.condition = threading.Condition(threading.RLock())
        self.stopping = False
        self.active = {}
        self.db = sqlite3.connect(str(db_path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL,
                duration_ms INTEGER NOT NULL, fail_first_attempt INTEGER NOT NULL,
                status TEXT NOT NULL, attempt INTEGER NOT NULL, generation INTEGER NOT NULL,
                created_at TEXT NOT NULL, started_at TEXT, ended_at TEXT,
                queue_ticket INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT, job_id INTEGER NOT NULL,
                from_status TEXT, to_status TEXT NOT NULL, attempt INTEGER NOT NULL,
                generation INTEGER NOT NULL, timestamp TEXT NOT NULL, reason TEXT NOT NULL,
                FOREIGN KEY(job_id) REFERENCES jobs(id));
        ''')
        with self.condition, self.db:
            for row in self.db.execute("SELECT * FROM jobs WHERE status='running'").fetchall():
                self._transition(row, 'queued', 'server_restart',
                                 generation=row['generation'] + 1, started_at=None, ended_at=None)
        self.workers = [threading.Thread(target=self._worker, name=f'queue-worker-{i}') for i in range(2)]
        for worker in self.workers:
            worker.start()

    def _row(self, job_id):
        row = self.db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if row is None:
            raise APIError(404, '작업을 찾을 수 없어.')
        return row

    def _transition(self, row, status, reason, **fields):
        # Caller holds condition and transaction; event and row commit atomically.
        fields['status'] = status
        event = self.db.execute(
            'INSERT INTO events(job_id,from_status,to_status,attempt,generation,timestamp,reason) VALUES(?,?,?,?,?,?,?)',
            (row['id'], row['status'], status, fields.get('attempt', row['attempt']),
             fields.get('generation', row['generation']), now(), reason))
        if status == 'queued':
            fields['queue_ticket'] = event.lastrowid
        self.db.execute('UPDATE jobs SET ' + ','.join(f'{key}=?' for key in fields) + ' WHERE id=?',
                        (*fields.values(), row['id']))

    @staticmethod
    def _public(row):
        result = dict(row)
        result['fail_first_attempt'] = bool(result['fail_first_attempt'])
        result.pop('queue_ticket', None)
        result.pop('generation', None)
        return result

    def create(self, data):
        if not isinstance(data, dict) or set(data) - {'title', 'duration_ms', 'fail_first_attempt'}:
            raise APIError(400, '허용된 필드만 JSON 객체로 보내.')
        title, duration, fail = data.get('title'), data.get('duration_ms'), data.get('fail_first_attempt', False)
        if not isinstance(title, str) or not title.strip() or len(title) > 200:
            raise APIError(400, '제목은 1~200자여야 해.')
        try:
            title.encode('utf-8')
        except UnicodeError:
            raise APIError(400, '제목에 잘못된 Unicode 문자가 있어.')
        if type(duration) is not int or not 100 <= duration <= 5000 or type(fail) is not bool:
            raise APIError(400, 'duration_ms는 100~5000 정수, fail_first_attempt는 boolean이어야 해.')
        with self.condition, self.db:
            cursor = self.db.execute(
                "INSERT INTO jobs(title,duration_ms,fail_first_attempt,status,attempt,generation,created_at) VALUES(?,?,?,'queued',1,1,?)",
                (title.strip(), duration, fail, now()))
            job_id = cursor.lastrowid
            event = self.db.execute(
                "INSERT INTO events(job_id,from_status,to_status,attempt,generation,timestamp,reason) VALUES(?,NULL,'queued',1,1,?,'created')",
                (job_id, now()))
            self.db.execute('UPDATE jobs SET queue_ticket=? WHERE id=?', (event.lastrowid, job_id))
            result = self._public(self._row(job_id))
            self.condition.notify_all()
            return result

    def get(self, job_id):
        with self.condition:
            return self._public(self._row(job_id))

    def jobs(self, status=None):
        if status is not None and status not in STATES:
            raise APIError(400, '알 수 없는 상태야.')
        with self.condition:
            rows = self.db.execute('SELECT * FROM jobs' + (' WHERE status=?' if status else '') + ' ORDER BY id DESC',
                                   (status,) if status else ()).fetchall()
            return [self._public(row) for row in rows]

    def change(self, job_id, action):
        with self.condition, self.db:
            row = self._row(job_id)
            if action == 'cancel':
                if row['status'] == 'cancelled':
                    return self._public(row)
                if row['status'] not in ('queued', 'running'):
                    raise APIError(409, '대기 또는 실행 중인 작업만 취소할 수 있어.')
                self._transition(row, 'cancelled', 'user_cancel', ended_at=now())
                signal = self.active.get((job_id, row['generation']))
                if signal:
                    signal.set()
            else:
                if row['status'] not in ('failed', 'cancelled'):
                    raise APIError(409, '실패 또는 취소된 작업만 재시도할 수 있어.')
                self._transition(row, 'queued', 'user_retry', attempt=row['attempt'] + 1,
                                 generation=row['generation'] + 1, started_at=None, ended_at=None)
            result = self._public(self._row(job_id))
            self.condition.notify_all()
            return result

    def stats(self):
        with self.condition:
            counts = dict.fromkeys(STATES, 0)
            counts.update({row[0]: row[1] for row in self.db.execute('SELECT status,COUNT(*) FROM jobs GROUP BY status')})
            return {'counts': counts, 'running': counts['running'], 'active_workers': len(self.active), 'max_workers': 2}

    def events(self):
        with self.condition:
            return [dict(row) for row in self.db.execute('SELECT * FROM events ORDER BY id')]

    def _worker(self):
        while True:
            with self.condition:
                while True:
                    if self.stopping:
                        return
                    row = self.db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY queue_ticket LIMIT 1").fetchone()
                    if row:
                        break
                    self.condition.wait()
                key = (row['id'], row['generation'])
                signal = threading.Event()
                with self.db:
                    self._transition(row, 'running', 'worker_started', started_at=now(), ended_at=None)
                self.active[key] = signal
            # Event.wait simulates sleep, with immediate wakeup for cancellation/shutdown.
            interrupted = self._simulate(row, signal)
            with self.condition:
                self.active.pop(key, None)
                if self.stopping:
                    return
                current = self._row(row['id'])
                if not interrupted and current['generation'] == row['generation'] and current['status'] == 'running':
                    failed = row['fail_first_attempt'] and row['attempt'] == 1
                    with self.db:
                        self._transition(current, 'failed' if failed else 'completed',
                                         'simulated_failure' if failed else 'worker_completed', ended_at=now())
                self.condition.notify_all()

    def _simulate(self, row, signal):
        return signal.wait(row['duration_ms'] / 1000)

    def close(self):
        with self.condition:
            self.stopping = True
            for signal in self.active.values():
                signal.set()
            self.condition.notify_all()
        for worker in self.workers:
            worker.join()
        self.db.close()


class QueueHTTPServer(ThreadingHTTPServer):
    daemon_threads = False
    block_on_close = True

    def __init__(self, address, queue):
        self.queue = queue
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def _send(self, status, data, content_type='application/json; charset=utf-8'):
        body = json.dumps(data, ensure_ascii=False).encode() if content_type.startswith('application/json') else data
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _body(self):
        if self.headers.get('Transfer-Encoding'):
            raise APIError(400, 'Transfer-Encoding은 지원하지 않아.')
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 16384:
                raise ValueError()
            if self.headers.get_content_type() != 'application/json':
                raise ValueError()
            return json.loads(self.rfile.read(length).decode('utf-8'))
        except (ValueError, UnicodeError):
            raise APIError(400, '올바른 JSON 본문이 필요해. 최대 16KB야.')

    def do_GET(self):
        self._handle('GET')

    def do_POST(self):
        self._handle('POST')

    def _handle(self, method):
        self.connection.settimeout(5)
        try:
            url = urlsplit(self.path)
            parts = url.path.strip('/').split('/')
            queue = self.server.queue
            if method == 'GET' and url.path in ('/', '/app.js', '/style.css'):
                filename, mime = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'),
                                  '/style.css': ('style.css', 'text/css')}[url.path]
                return self._send(200, (Path(__file__).parent / 'static' / filename).read_bytes(), mime + '; charset=utf-8')
            if parts == ['api', 'jobs']:
                if method == 'POST':
                    return self._send(201, queue.create(self._body()))
                query = parse_qs(url.query, keep_blank_values=True)
                if set(query) - {'status'} or len(query.get('status', [])) > 1:
                    raise APIError(400, 'status 필터 하나만 사용할 수 있어.')
                return self._send(200, {'jobs': queue.jobs(query.get('status', [None])[0])})
            if method == 'GET' and parts == ['api', 'stats']:
                return self._send(200, queue.stats())
            if method == 'GET' and parts == ['api', 'events']:
                return self._send(200, {'events': queue.events()})
            if len(parts) in (3, 4) and parts[:2] == ['api', 'jobs']:
                try:
                    job_id = int(parts[2])
                    if job_id < 1:
                        raise ValueError()
                except ValueError:
                    raise APIError(400, '작업 ID는 양의 정수여야 해.')
                if method == 'GET' and len(parts) == 3:
                    return self._send(200, queue.get(job_id))
                if method == 'POST' and len(parts) == 4 and parts[3] in ('cancel', 'retry'):
                    data = self._body()
                    if data != {}:
                        raise APIError(400, '이 요청의 본문은 빈 JSON 객체여야 해.')
                    return self._send(200, queue.change(job_id, parts[3]))
            raise APIError(404, '경로를 찾을 수 없어.')
        except APIError as error:
            self._send(error.status, {'error': error.message})
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass


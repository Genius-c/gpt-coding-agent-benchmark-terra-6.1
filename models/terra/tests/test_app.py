import concurrent.futures
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import Server

ROOT = Path(__file__).resolve().parents[1]

class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT)
        self.path = Path(self.temp.name)/'test.sqlite3'
        self.start()
    def start(self):
        self.server = Server(('127.0.0.1',0),self.path)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.base = 'http://127.0.0.1:'+str(self.server.server_address[1])
    def stop(self):
        self.server.shutdown(); self.thread.join(); self.server.server_close()
    def tearDown(self):
        self.stop(); self.temp.cleanup()
        self.assertFalse(any(t.name.startswith('queue-worker-') for t in threading.enumerate()))
    def request(self,path, data=None, post=False):
        request=Request(self.base+path, data=json.dumps(data).encode() if data is not None else (b'' if post else None), headers={'Content-Type':'application/json'}, method='POST' if post or data is not None else 'GET')
        try:
            with urlopen(request, timeout=5) as response: return response.status,json.load(response)
        except HTTPError as e: return e.code,json.load(e)
    def create(self, duration=100, fail=False):
        return self.request('/api/jobs',{'title':'테스트','duration_ms':duration,'fail_first_attempt':fail})[1]
    def wait(self, job, state, timeout=5):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            item=self.request('/api/jobs/'+str(job))[1]
            if item['status']==state: return item
            time.sleep(.01)
        self.fail(f'{job}: expected {state}, got {item}')
    def test_completion(self):
        job=self.create(); result=self.wait(job['id'],'completed'); self.assertEqual(result['attempt'],1)
    def test_invalid(self):
        for body in ({}, {'title':'x','duration_ms':True,'fail_first_attempt':False}, {'title':'x','duration_ms':99,'fail_first_attempt':False}): self.assertEqual(self.request('/api/jobs',body)[0],400)
        self.assertEqual(self.request('/api/jobs?status=bad')[0],400)
        self.assertEqual(self.request('/api/jobs/999')[0],404)
        job=self.create(); self.wait(job['id'],'completed'); self.assertEqual(self.request(f"/api/jobs/{job['id']}/retry",post=True)[0],409)
    def test_concurrency_limit(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool: jobs=list(pool.map(lambda _:self.create(350),range(12)))
        maximum=0
        while True:
            counts=self.request('/api/stats')[1]['counts']; maximum=max(maximum,counts['running'])
            self.assertLessEqual(counts['running'],2)
            if counts['completed']==12: break
            time.sleep(.01)
        self.assertEqual(maximum,2)
        events=list(reversed(self.request('/api/events')[1])); active=set()
        for event in events:
            if event['status']=='running': active.add(event['job_id']); self.assertLessEqual(len(active),2)
            if event['status'] in ('completed','failed','cancelled'): active.discard(event['job_id'])
    def test_cancel(self):
        job=self.create(1000); self.wait(job['id'],'running'); self.assertEqual(self.request(f"/api/jobs/{job['id']}/cancel",post=True)[1]['status'],'cancelled'); self.assertEqual(self.request(f"/api/jobs/{job['id']}/cancel",post=True)[0],200)
    def test_failure_retry(self):
        job=self.create(100,True); self.wait(job['id'],'failed'); self.assertEqual(self.request(f"/api/jobs/{job['id']}/retry",post=True)[0],200); self.assertEqual(self.wait(job['id'],'completed')['attempt'],2)
    def test_concurrent_retry(self):
        job=self.create(200,True); self.wait(job['id'],'failed')
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool: results=list(pool.map(lambda _:self.request(f"/api/jobs/{job['id']}/retry",post=True)[0],range(12)))
        self.assertEqual(results.count(200),1); self.assertEqual(results.count(409),11); self.assertEqual(self.wait(job['id'],'completed')['attempt'],2)
    def test_cancel_retry_old_worker(self):
        job=self.create(600,True); self.wait(job['id'],'running'); self.request(f"/api/jobs/{job['id']}/cancel",post=True); self.request(f"/api/jobs/{job['id']}/retry",post=True)
        result=self.wait(job['id'],'completed'); self.assertEqual(result['attempt'],2); time.sleep(.1); self.assertEqual(self.request(f"/api/jobs/{job['id']}")[1]['status'],'completed')
        events=self.request('/api/events')[1]; self.assertNotIn('failed',[e['status'] for e in events])
    def test_restart(self):
        job=self.create(1000); self.wait(job['id'],'running'); self.stop(); self.start(); result=self.wait(job['id'],'completed'); self.assertEqual(result['attempt'],2)
        self.assertIn('queued',[e['status'] for e in self.request('/api/events')[1]])
    def test_persistence_history(self):
        job=self.create(); self.wait(job['id'],'completed'); self.stop(); self.start()
        self.assertEqual(self.request(f"/api/jobs/{job['id']}")[1]['status'],'completed')
        events=[e['status'] for e in reversed(self.request('/api/events')[1]) if e['job_id']==job['id']]; self.assertEqual(events,['queued','running','completed'])

if __name__=='__main__': unittest.main()

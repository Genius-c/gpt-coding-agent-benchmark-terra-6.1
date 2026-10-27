"""Independent HTTP probes. Run one model in each fresh interpreter."""
import importlib,sys,tempfile,threading,json,time
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError

def run(model, root):
 sys.path.insert(0,str(root/'models'/model))
 checks=[]
 with tempfile.TemporaryDirectory() as tmp:
  db=Path(tmp)/'probe.sqlite3'
  if model=='luna': server=importlib.import_module('app').make_server(port=0,db_path=db)
  elif model=='terra': server=importlib.import_module('app').Server(('127.0.0.1',0),db)
  else:
   m=importlib.import_module('queue_server');server=m.QueueHTTPServer(('127.0.0.1',0),m.JobQueue(db))
  thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01});thread.start()
  base=f'http://127.0.0.1:{server.server_port}'
  def req(path,data=None):
   r=Request(base+path,data=None if data is None else json.dumps(data,ensure_ascii=False).encode('utf-8'),headers={'Content-Type':'application/json'})
   try:
    with urlopen(r,timeout=5) as response:return response.status,json.load(response)
   except HTTPError as e:
    with e:return e.code,json.load(e)
  def check(name,fn):
   try: detail=fn();checks.append({'name':name,'passed':True,'detail':detail})
   except Exception as e:checks.append({'name':name,'passed':False,'detail':type(e).__name__+': '+str(e)})
  def expect(v,w):
   if v!=w:raise AssertionError(f'expected {w!r}, received {v!r}')
  def wait(job,state):
   end=time.monotonic()+8
   while time.monotonic()<end:
    code,value=req('/api/jobs/'+str(job));expect(code,200)
    if value['status']==state:return value
    time.sleep(.02)
   raise AssertionError('timeout waiting for '+state)
  def lifecycle():
   title='Unicode '+chr(0xd55c)+chr(0xae00)+' '+chr(0x1f680)
   code,j=req('/api/jobs',{'title':title,'duration_ms':100,'fail_first_attempt':True});expect(code,201)
   wait(j['id'],'failed');expect(req(f"/api/jobs/{j['id']}/retry",{})[0],200)
   done=wait(j['id'],'completed');expect(done['title'],title);expect(done['attempt'],2)
   expect(req(f"/api/jobs/{j['id']}/retry",{})[0],409)
   return 'UTF-8 title round trip, first failure, retry, completion, terminal conflict'
  def invalid():
   expect(req('/api/jobs',{'title':'x','duration_ms':True,'fail_first_attempt':False})[0],400)
  def blank_filter():expect(req('/api/jobs?status=')[0],400)
  def unknown_field():expect(req('/api/jobs',{'title':'x','duration_ms':100,'fail_first_attempt':False,'extra':1})[0],400)
  def cancel():
   code,j=req('/api/jobs',{'title':'cancel','duration_ms':1000,'fail_first_attempt':False});expect(code,201)
   wait(j['id'],'running');expect(req(f"/api/jobs/{j['id']}/cancel",{})[1]['status'],'cancelled')
   time.sleep(.15);expect(req('/api/jobs/'+str(j['id']))[1]['status'],'cancelled')
  try:
   for name,fn in [('failure_retry_unicode',lifecycle),('reject_boolean_duration',invalid),('reject_blank_status_filter',blank_filter),('reject_unknown_creation_field',unknown_field),('running_cancel_stays_cancelled',cancel)]:check(name,fn)
  finally:
   server.shutdown();server.server_close();thread.join(5)
   if model=='sol':server.queue.close()
 return {'model':model,'checks':checks}

if __name__=='__main__':print(json.dumps(run(sys.argv[1],Path(__file__).resolve().parents[1]),ensure_ascii=True))

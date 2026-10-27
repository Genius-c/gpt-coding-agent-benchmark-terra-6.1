"""Reproduce submitted suites and separate independent HTTP checks."""
from pathlib import Path
import datetime,json,locale,os,platform,sqlite3,subprocess,sys

root=Path(__file__).resolve().parents[1]
out=root/'results';out.mkdir(exist_ok=True)
env=dict(os.environ,PYTHONIOENCODING='utf-8',PYTHONUTF8='1',PYTHONDONTWRITEBYTECODE='1')
result={'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'environment':{'os':platform.system(),'release':platform.release(),'python':platform.python_version(),'sqlite':sqlite3.sqlite_version,'preferred_encoding':locale.getpreferredencoding(False),'locale':locale.getlocale(),'child_python_utf8':True},'submitted_suites':[],'independent_probes':[]}
for model in ('terra','luna','sol'):
 for kind,cmd,cwd in [('submitted',[sys.executable,'-m','unittest','discover','-s','tests','-v'],root/'models'/model),('independent',[sys.executable,str(root/'probes/http_probe.py'),model],root)]:
  try:
   p=subprocess.run(cmd,cwd=cwd,env=env,capture_output=True,encoding='utf-8',errors='replace',timeout=120)
   # Avoid publishing absolute local workspace paths in tracebacks.
   log=(p.stdout+p.stderr).replace(str(root),'<BENCHMARK_ROOT>').replace(str(Path(sys.executable).parent),'<PYTHON_DIR>')
   (out/f'{model}-{kind}.log').write_text(log,encoding='utf-8')
   entry={'model':model,'exit_code':p.returncode,'log':f'results/{model}-{kind}.log'}
   if kind=='independent' and p.returncode==0:entry['observations']=json.loads(p.stdout)['checks']
  except subprocess.TimeoutExpired:entry={'model':model,'timeout_seconds':120}
  result['submitted_suites' if kind=='submitted' else 'independent_probes'].append(entry)
(out/'reproduction.json').write_text(json.dumps(result,indent=2,ensure_ascii=True)+'\n',encoding='utf-8')
print(json.dumps(result,indent=2))

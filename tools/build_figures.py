"""Build English publication figures from sanitized JSON; requires matplotlib."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets';OUT.mkdir(exist_ok=True)
session=json.loads((ROOT/'results/session-report.json').read_text(encoding='utf-8'))
repro=json.loads((ROOT/'results/reproduction.json').read_text(encoding='utf-8'))
models=session['models']
ink='#132c43';muted='#53677a';blue='#326fa8';green='#146b5e';amber='#a76711'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'text.color':ink,'axes.labelcolor':ink,'xtick.color':muted,'ytick.color':ink,'axes.spines.top':False,'axes.spines.right':False,'axes.spines.left':False,'axes.spines.bottom':False,'figure.facecolor':'#f4f7fb','axes.facecolor':'#f4f7fb','savefig.facecolor':'#f4f7fb'})

fig,axes=plt.subplots(1,2,figsize=(15,7.2),gridspec_kw={'width_ratios':[1,1.35]})
fig.subplots_adjust(left=.07,right=.97,top=.73,bottom=.26,wspace=.38)
fig.text(.06,.93,'Reproduced behavior of three supplied artifacts',fontsize=23,weight='bold')
fig.text(.06,.87,'Publication reproduction | Separate evidence classes | No aggregate model ranking',fontsize=12,color=muted)
ax=axes[0]
counts=[]
import re
for m in models:
 text=(ROOT/f"results/{m['key']}-submitted.log").read_text(encoding='utf-8')
 assert re.search(r'\nOK\s*$',text),m['key']
 counts.append(int(re.search(r'Ran (\d+) tests',text).group(1)))
ax.set_title('Submitted suites, rerun as supplied',loc='left',fontsize=14,weight='bold',pad=20)
bars=ax.bar(range(3),counts,color=blue,width=.55)
for bar,n in zip(bars,counts):ax.text(bar.get_x()+bar.get_width()/2,n+.35,f'{n}/{n}\nOK',ha='center',va='bottom',fontsize=12,weight='bold')
ax.set_xticks(range(3),[m['label'] for m in models]);ax.set_ylim(0,12.7);ax.set_yticks([0,3,6,9,12]);ax.set_ylabel('Tests in each submitted suite');ax.grid(axis='y',alpha=.15);ax.set_axisbelow(True)
ax.text(0,-.24,'Different test collections and assertions.\nCounts do not measure comparable coverage.',transform=ax.transAxes,fontsize=11,color=muted,va='top')
ax=axes[1];ax.set_title('Separate independent HTTP probes',loc='left',fontsize=14,weight='bold',pad=20)
names=['Failure / retry + Unicode','Reject boolean duration','Reject blank status filter','Reject unknown field','Running cancel persists']
keys=['failure_retry_unicode','reject_boolean_duration','reject_blank_status_filter','reject_unknown_creation_field','running_cancel_stays_cancelled']
for col,m in enumerate(models):
 entry=next(x for x in repro['independent_probes'] if x['model']==m['key'])
 lookup={x['name']:x['passed'] for x in entry['observations']}
 for row,key in enumerate(keys):
  met=lookup[key];ax.add_patch(Rectangle((col-.48,row-.43),.96,.86,facecolor='#dceee9' if met else '#fae9ce',edgecolor='white',linewidth=2))
  ax.text(col,row,'Met' if met else 'Policy\ndifference',ha='center',va='center',fontsize=11,color=green if met else amber,weight='bold')
ax.set_xlim(-.5,2.5);ax.set_ylim(4.5,-.5);ax.set_xticks(range(3),[m['label'] for m in models]);ax.set_yticks(range(5),names);ax.tick_params(length=0)
ax.text(0,-.24,'Amber = observed acceptance under a strict rejection policy.\nThe detailed original requirements are unavailable.',transform=ax.transAxes,fontsize=11,color=muted,va='top')
fig.text(.06,.055,'Source: results/reproduction.json and the submitted-suite logs. One recorded reproduction; no uncertainty estimates.',fontsize=10,color=muted)
fig.savefig(OUT/'results-overview.png',dpi=150);plt.close(fig)

fig,axes=plt.subplots(1,2,figsize=(15,6.5))
fig.subplots_adjust(left=.1,right=.96,top=.71,bottom=.25,wspace=.4)
fig.text(.065,.93,'Original sessions in Orbit, the contributor-built IDE',fontsize=22,weight='bold')
fig.text(.065,.86,'Reported Medium reasoning for all three | Deduplicated tool actions | Single runs',fontsize=12,color=muted)
for ax,field,title,unit in [(axes[0],'duration_seconds','UI-reported elapsed time','Seconds'),(axes[1],'action_count','UI-reported action count','Actions')]:
 vals=[m[field] for m in models];bars=ax.barh(range(3),vals,color=[blue,'#7294b5','#46627f'],height=.55)
 ax.set_yticks(range(3),[m['label'] for m in models]);ax.invert_yaxis();ax.set_xlim(0,max(vals)*1.35);ax.set_xlabel(unit);ax.set_title(title,loc='left',fontsize=14,weight='bold',pad=18);ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
 for i,v in enumerate(vals):
  label=f'{v//60}m {v%60:02d}s ({v}s)' if field=='duration_seconds' else str(v)
  ax.text(v+max(vals)*.035,i,label,va='center',fontsize=11,weight='bold')
fig.text(.065,.13,'Timing includes tools, retries and unequal verification work. Sol used Chrome and a mobile viewport; Terra did not visually inspect the UI.',fontsize=10.5,color=muted)
fig.text(.065,.075,'These are session summaries, not pure inference latency, task-token measurements, or a general speed ranking. Source: results/session-report.json.',fontsize=10.5,color=muted)
fig.savefig(OUT/'session-evidence.png',dpi=150);plt.close(fig)
print('Rendered two figures from sanitized session data and recorded reproduction logs.')

from __future__ import annotations
import json
from pathlib import Path
def n(v,d=0.):
 try:return float(v)
 except:return d
def clamp(x,a,b):return max(a,min(b,x))
DEFAULTS={'last_n':8,'decay':.88,'strength':.30,'attack_share':.40,'prior':360.}
def load_tuned_params(path='recent_form_ab_status.json'):
 p=Path(path)
 if not p.exists():return {**DEFAULTS,'promoted':False,'source':'defaults'}
 try:
  d=json.loads(p.read_text());sel=d.get('selected_params') or {};out={**DEFAULTS,**{k:sel[k] for k in DEFAULTS if k in sel}};out['promoted']=bool(d.get('promote'));out['source']='train_tuned_holdout_validated' if out['promoted'] else 'train_tuned_not_promoted';return out
 except Exception:return {**DEFAULTS,'promoted':False,'source':'defaults_error'}
def recent_signal(history,last_n=None,decay=None,strength=None,prior=None,params=None):
 p={**DEFAULTS,**(params or {})};last_n=int(last_n if last_n is not None else p['last_n']);decay=float(decay if decay is not None else p['decay']);strength=float(strength if strength is not None else p['strength']);prior=float(prior if prior is not None else p['prior']);rows=sorted(history,key=lambda r:int(r.get('round') or 0),reverse=True)[:last_n]
 if not rows:return {'multiplier':1.,'xgi90':0.,'minutes':0.,'matches':0,'confidence':0.}
 sxgi=smin=0.
 for age,r in enumerate(rows):
  w=decay**age;mins=n(r.get('minutes'));sxgi+=(n(r.get('expected_goals'))+n(r.get('expected_assists')))*w;smin+=mins*w
 xgi90=sxgi*90/max(smin,90);total_minutes=sum(n(r.get('minutes')) for r in rows);conf=total_minutes/(total_minutes+prior);raw=1+strength*(xgi90-.35);mult=1+(clamp(raw,.72,1.35)-1)*conf;return {'multiplier':clamp(mult,.84,1.20),'xgi90':xgi90,'minutes':total_minutes,'matches':len(rows),'confidence':conf}
def blend_rates(base,season_form,recent_form,attack_share=.40,enabled=True):
 out=dict(base);sm=n(season_form.get('multiplier'),1);rm=n(recent_form.get('multiplier'),1);combined=sm*(1+(rm-1)*attack_share) if enabled else sm;combined=clamp(combined,.80,1.24);out['goal90']*=combined;out['assist90']*=combined;return out,combined

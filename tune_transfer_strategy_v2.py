#!/usr/bin/env python3
"""Tune transfer horizon weights on old seasons, evaluate once on holdout."""
import argparse,json
from collections import defaultdict

def n(x,d=0.0):
 try:return float(x)
 except:return d

def pid(r):return str(r.get('player') or '').strip()

def evaluate(rows,seasons,weights):
 rows=[r for r in rows if r.get('season') in seasons]; pg={(r['season'],pid(r),int(n(r.get('gw')))):r for r in rows if pid(r)}; by=defaultdict(list)
 for r in rows:by[(r['season'],int(n(r.get('gw'))))].append(r)
 total=greedy=0.0;tests=0;wins=ties=losses=0
 for (season,gw),rs in sorted(by.items()):
  cand=[]
  for r in rs:
   p=pid(r);future=[]
   for k,w in enumerate(weights):
    rr=pg.get((season,p,gw+k))
    if rr:future.append((rr,w))
   if len(future)<min(2,len(weights)):continue
   pred=sum(n(rr.get('v2'))*w for rr,w in future);actual=sum(n(rr.get('actual'))*w for rr,w in future);one=n(r.get('v2'));cand.append((pred,one,actual))
  if len(cand)<20:continue
  a=max(cand,key=lambda x:x[0]);b=max(cand,key=lambda x:x[1]);total+=a[2];greedy+=b[2];tests+=1
  if a[2]>b[2]:wins+=1
  elif a[2]<b[2]:losses+=1
  else:ties+=1
 return {'tests':tests,'multi':round(total,2),'greedy':round(greedy,2),'delta':round(total-greedy,2),'wins':wins,'ties':ties,'losses':losses}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('dataset');ap.add_argument('--out',default='transfer_strategy_params.json');a=ap.parse_args();data=json.load(open(a.dataset));rows=data.get('rows',data) if isinstance(data,dict) else data
 seasons=sorted({r.get('season') for r in rows if r.get('season')});hold=seasons[-1];train=set(seasons[:-1])
 candidates=[(1,.95,.9),(1,.9,.8),(1,.85,.7),(1,.8,.65),(1,.9,.75,.6),(1,.85,.7,.55),(1,.8,.65,.5),(1,.9,.8,.7,.6,.5)]
 scored=[(evaluate(rows,train,w),w) for w in candidates];best_m,best=max(scored,key=lambda x:(x[0]['delta'],x[0]['wins']-x[0]['losses']));hold_m=evaluate(rows,{hold},best)
 out={'train_seasons':sorted(train),'holdout_season':hold,'weights':list(best),'train':best_m,'holdout':hold_m,'promote':hold_m['tests']>=20 and hold_m['delta']>=0 and hold_m['wins']>=hold_m['losses']}
 json.dump(out,open(a.out,'w'),indent=2);print(json.dumps(out,indent=2))
if __name__=='__main__':main()

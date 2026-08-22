#!/usr/bin/env python3
"""Leakage-safe captain model v3.
Tune on old seasons only. Uses calibrated xP plus ceiling, minutes, fixture attack
and volatility. The newest season is an untouched promotion holdout.
"""
import argparse,json
from collections import defaultdict

def n(x,d=0.):
 try:return float(x)
 except:return d

def score(r,w):
 xp=n(r.get('v2',r.get('predicted_xp'))); p90=n(r.get('p90'),xp); mins=n(r.get('expected_minutes'),60); atk=n(r.get('attack_multiplier'),1); vol=n(r.get('volatility'),0)
 # All extras are expressed as small tie-breakers around xP, not replacements.
 return xp + w['ceiling']*max(0,p90-xp) + w['mins']*((mins-70)/20) + w['attack']*(atk-1) - w['vol_penalty']*vol

def evaluate(rows,w,seasons):
 groups=defaultdict(list)
 for r in rows:
  if r.get('season') in seasons:groups[(r.get('season'),int(n(r.get('gw'))))].append(r)
 pts=base=oracle=0.;wins=ties=losses=0;weeks=0
 for g in groups.values():
  pool=[r for r in g if n(r.get('expected_minutes'))>=45]
  if len(pool)<20:continue
  pick=max(pool,key=lambda r:score(r,w)); b=max(pool,key=lambda r:n(r.get('v2',r.get('predicted_xp')))); o=max(pool,key=lambda r:n(r.get('actual')))
  a=n(pick.get('actual'));bb=n(b.get('actual'));pts+=a;base+=bb;oracle+=n(o.get('actual'));weeks+=1
  if a>bb:wins+=1
  elif a<bb:losses+=1
  else:ties+=1
 return {'gameweeks':weeks,'points':round(pts,1),'baseline_points':round(base,1),'oracle_points':round(oracle,1),'delta':round(pts-base,1),'wins':wins,'ties':ties,'losses':losses}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('dataset');ap.add_argument('--out',default='captain_v3_status.json');a=ap.parse_args();rows=json.load(open(a.dataset));rows=rows.get('rows',rows) if isinstance(rows,dict) else rows
 seasons=sorted({r.get('season') for r in rows if r.get('season')});hold=seasons[-1];train=set(seasons[:-1])
 grid=[]
 for ceiling in (0,.05,.10,.15,.20,.30):
  for mins in (0,.02,.04,.08):
   for attack in (0,.05,.10,.20):
    for vol in (0,.02,.05,.10):grid.append({'ceiling':ceiling,'mins':mins,'attack':attack,'vol_penalty':vol})
 # Require a real training advantage; among ties prefer simpler/smaller weights.
 def objective(w):
  e=evaluate(rows,w,train);complexity=sum(w.values());return (e['delta'],e['wins']-e['losses'],-complexity)
 best=max(grid,key=objective);tr=evaluate(rows,best,train);ho=evaluate(rows,best,{hold})
 promote=ho['delta']>0 and ho['wins']>=ho['losses'] and tr['delta']>=0
 out={'model':'captain-v3-ceiling-aware','holdout_season':hold,'train_seasons':sorted(train),'tested_configs':len(grid),'weights':best,'train':tr,'holdout':ho,'promote':promote}
 json.dump(out,open(a.out,'w'),indent=2);print(json.dumps(out,indent=2))
if __name__=='__main__':main()

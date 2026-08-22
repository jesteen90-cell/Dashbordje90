#!/usr/bin/env python3
"""Tune whether upside should influence captain choice beyond mean xP."""
import argparse,json
from collections import defaultdict

def n(x,d=0.0):
 try:return float(x)
 except:return d

def evaluate(rows,seasons,lmb):
 g=defaultdict(list)
 for r in rows:
  if r.get('season') in seasons:g[(r['season'],int(n(r['gw'])))].append(r)
 pts=base=0;wins=ties=losses=0
 for rs in g.values():
  elig=[r for r in rs if n(r.get('expected_minutes'))>=45]
  if not elig:continue
  pick=max(elig,key=lambda r:n(r['v2'])+lmb*max(0,n(r.get('p90'))-n(r['v2'])));b=max(elig,key=lambda r:n(r['v2']));a=n(pick['actual']);bb=n(b['actual']);pts+=a;base+=bb
  if a>bb:wins+=1
  elif a<bb:losses+=1
  else:ties+=1
 return {'gameweeks':len(g),'points':pts,'baseline':base,'delta':pts-base,'wins':wins,'ties':ties,'losses':losses}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('dataset');ap.add_argument('--out',default='upside_tuning_status.json');a=ap.parse_args();rows=json.load(open(a.dataset));seasons=sorted({r['season'] for r in rows});hold=seasons[-1];train=set(seasons[:-1]);grid=[-.30,-.15,0,.10,.20,.35,.50]
 best=max(grid,key=lambda x:(evaluate(rows,train,x)['delta'],-abs(x)));tr=evaluate(rows,train,best);ho=evaluate(rows,{hold},best);promote=best!=0 and ho['delta']>0 and ho['wins']>=ho['losses']
 out={'holdout_season':hold,'train_seasons':sorted(train),'upside_weight':best,'train':tr,'holdout':ho,'promote':promote}
 json.dump(out,open(a.out,'w'),indent=2);print(json.dumps(out,indent=2))
if __name__=='__main__':main()

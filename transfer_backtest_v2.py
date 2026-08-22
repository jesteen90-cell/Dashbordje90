#!/usr/bin/env python3
"""Leakage-safe evaluation of multi-GW planning vs greedy one-GW decisions.
Uses historical rows already produced by build_backtest_dataset.py. This is a
strategy test, not a reconstruction of a specific manager's historic squad.
"""
import argparse,json
from collections import defaultdict

def n(x,d=0.0):
 try:return float(x)
 except:return d

def main():
 ap=argparse.ArgumentParser();ap.add_argument('dataset');ap.add_argument('--out',default='transfer_backtest_status.json');a=ap.parse_args()
 data=json.load(open(a.dataset));rows=data.get('rows',data) if isinstance(data,dict) else data
 seasons=sorted({r.get('season') for r in rows if r.get('season')});hold=seasons[-1]
 hr=[r for r in rows if r.get('season')==hold]
 bygw=defaultdict(list)
 for r in hr:bygw[int(n(r.get('gw'))) ].append(r)
 # Evaluate ranking quality of a 3-GW weighted signal versus next-GW-only signal.
 # For every GW/player with future observations, compare whether each signal
 # selects the player with more realised points over the same 3-GW horizon.
 playergw={(int(n(r.get('element',r.get('id')))),int(n(r.get('gw')))):r for r in hr}
 wins=ties=losses=0;multi_pts=greedy_pts=0.0;tests=0
 for gw,rs in sorted(bygw.items()):
  candidates=[]
  for r in rs:
   pid=int(n(r.get('element',r.get('id')))); future=[]
   for k,w in ((0,1.0),(1,.9),(2,.8)):
    rr=playergw.get((pid,gw+k))
    if rr:future.append((rr,w))
   if len(future)<2:continue
   pred_multi=sum(n(rr.get('v2',rr.get('predicted_xp')))*w for rr,w in future)
   pred_greedy=n(r.get('v2',r.get('predicted_xp')))
   actual=sum(n(rr.get('actual',rr.get('actual_points',rr.get('total_points'))))*w for rr,w in future)
   candidates.append((pred_multi,pred_greedy,actual,pid))
  if len(candidates)<20:continue
  m=max(candidates,key=lambda x:x[0]);g=max(candidates,key=lambda x:x[1]);multi_pts+=m[2];greedy_pts+=g[2];tests+=1
  if m[2]>g[2]:wins+=1
  elif m[2]<g[2]:losses+=1
  else:ties+=1
 out={'holdout_season':hold,'tests':tests,'multi_gw_actual':round(multi_pts,2),'greedy_actual':round(greedy_pts,2),'delta':round(multi_pts-greedy_pts,2),'wins':wins,'ties':ties,'losses':losses,'promote':tests>=20 and multi_pts>=greedy_pts and wins>=losses}
 json.dump(out,open(a.out,'w'),indent=2);print(json.dumps(out,indent=2))
if __name__=='__main__':main()

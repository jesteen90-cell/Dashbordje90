#!/usr/bin/env python3
"""Leakage-safe test of multi-GW ranking versus next-GW-only ranking."""
import argparse,json
from collections import defaultdict

def n(x,d=0.0):
 try:return float(x)
 except:return d

def pid(r):return str(r.get('player') or r.get('element') or r.get('id') or '').strip()

def main():
 ap=argparse.ArgumentParser();ap.add_argument('dataset');ap.add_argument('--out',default='transfer_backtest_status.json');a=ap.parse_args()
 data=json.load(open(a.dataset));rows=data.get('rows',data) if isinstance(data,dict) else data
 seasons=sorted({r.get('season') for r in rows if r.get('season')});hold=seasons[-1];hr=[r for r in rows if r.get('season')==hold];bygw=defaultdict(list)
 for r in hr:bygw[int(n(r.get('gw')))].append(r)
 playergw={(pid(r),int(n(r.get('gw')))):r for r in hr if pid(r)}
 wins=ties=losses=0;multi_pts=greedy_pts=0.0;tests=covered=0
 for gw,rs in sorted(bygw.items()):
  candidates=[]
  for r in rs:
   p=pid(r);future=[]
   if not p:continue
   for k,w in ((0,1.0),(1,.9),(2,.8)):
    rr=playergw.get((p,gw+k))
    if rr:future.append((rr,w))
   if len(future)<2:continue
   covered+=1;pred_multi=sum(n(rr.get('v2',rr.get('predicted_xp')))*w for rr,w in future);pred_greedy=n(r.get('v2',r.get('predicted_xp')));actual=sum(n(rr.get('actual',rr.get('actual_points',rr.get('total_points'))))*w for rr,w in future);candidates.append((pred_multi,pred_greedy,actual,p))
  if len(candidates)<20:continue
  m=max(candidates,key=lambda x:x[0]);g=max(candidates,key=lambda x:x[1]);multi_pts+=m[2];greedy_pts+=g[2];tests+=1
  if m[2]>g[2]:wins+=1
  elif m[2]<g[2]:losses+=1
  else:ties+=1
 valid=tests>=20 and covered>=500 and (multi_pts>0 or greedy_pts>0)
 out={'holdout_season':hold,'tests':tests,'covered_player_windows':covered,'multi_gw_actual':round(multi_pts,2),'greedy_actual':round(greedy_pts,2),'delta':round(multi_pts-greedy_pts,2),'wins':wins,'ties':ties,'losses':losses,'valid':valid,'promote':bool(valid and multi_pts>=greedy_pts and wins>=losses)}
 json.dump(out,open(a.out,'w'),indent=2);print(json.dumps(out,indent=2))
 if not valid:raise SystemExit('Invalid transfer backtest: insufficient identity/points coverage')
if __name__=='__main__':main()

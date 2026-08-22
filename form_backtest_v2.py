#!/usr/bin/env python3
"""Validate whether underlying xGI/ICT form adds ranking value on holdout.
Uses only fields present at each historical observation and fails closed when
coverage is insufficient. This gate is deliberately conservative.
"""
import argparse,json
from collections import defaultdict

def n(x,d=0.):
 try:return float(x)
 except:return d

def clamp(x,a,b):return max(a,min(b,x))
def signal(r):
 mins=max(n(r.get('minutes')),90);xgi=n(r.get('expected_goal_involvements'),n(r.get('expected_goals'))+n(r.get('expected_assists')));xgi90=xgi*90/mins
 threat=n(r.get('threat'))*90/mins;cre=n(r.get('creativity'))*90/mins;inf=n(r.get('influence'))*90/mins;shrink=mins/(mins+450)
 raw=1+.22*(xgi90-.35)+.0008*(threat-35)+.0005*(cre-30)+.00035*(inf-35)
 return 1+(clamp(raw,.72,1.35)-1)*shrink

def main():
 ap=argparse.ArgumentParser();ap.add_argument('dataset');ap.add_argument('--out',default='form_backtest_status.json');a=ap.parse_args();d=json.load(open(a.dataset));rows=d.get('rows',d) if isinstance(d,dict) else d
 seasons=sorted({r.get('season') for r in rows if r.get('season')});hold=seasons[-1];rs=[r for r in rows if r.get('season')==hold];g=defaultdict(list)
 for r in rs:g[int(n(r.get('gw')))].append(r)
 base=form=0.;wins=ties=losses=tests=covered=0
 for gw,xs in sorted(g.items()):
  usable=[r for r in xs if any(k in r for k in ('expected_goal_involvements','expected_goals','threat','creativity'))]
  if len(usable)<20:continue
  covered+=len(usable)
  b=max(usable,key=lambda r:n(r.get('v2',r.get('predicted_xp'))));f=max(usable,key=lambda r:n(r.get('v2',r.get('predicted_xp')))*signal(r))
  ba=n(b.get('actual',b.get('actual_points',b.get('total_points'))));fa=n(f.get('actual',f.get('actual_points',f.get('total_points'))));base+=ba;form+=fa;tests+=1
  if fa>ba:wins+=1
  elif fa<ba:losses+=1
  else:ties+=1
 valid=tests>=20 and covered>=500;out={'holdout_season':hold,'tests':tests,'covered_rows':covered,'base_actual':round(base,2),'form_actual':round(form,2),'delta':round(form-base,2),'wins':wins,'ties':ties,'losses':losses,'valid':valid,'promote':bool(valid and form>=base and wins>=losses)}
 json.dump(out,open(a.out,'w'),indent=2);print(json.dumps(out,indent=2))
 if not valid:raise SystemExit('Invalid form backtest coverage')
if __name__=='__main__':main()

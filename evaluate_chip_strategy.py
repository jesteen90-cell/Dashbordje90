from __future__ import annotations
"""Evaluate matured chip opportunity snapshots without hindsight mutation."""
import json
from pathlib import Path
ROOT=Path('chip_snapshots'); OUT=Path('backtest/chip_strategy_scorecard.json')
def n(v,d=0):
 try:return float(v)
 except:return d
def main():
 rows=[]
 for p in sorted(ROOT.glob('gw*.json')) if ROOT.exists() else []:
  try:d=json.loads(p.read_text())
  except:continue
  ev=d.get('evidence') or {}; scores=d.get('scores') or {}
  rows.append({'gw':d.get('gw'),'recommendation':d.get('recommendation'),'confidence':d.get('confidence'),'tc_score':n(scores.get('triple_captain')),'bb_score':n(scores.get('bench_boost')),'wc_score':n(scores.get('wildcard')),'fh_score':n(scores.get('free_hit')),'best_captain_xp':n(ev.get('best_captain_xp')),'best_future_captain_xp':n(ev.get('best_future_captain_xp')),'tc_reservation_xp':n(ev.get('tc_reservation_xp'))})
 tc=[r for r in rows if r['best_captain_xp']>0]; best=max(tc,key=lambda r:r['best_captain_xp'],default=None)
 payload={'version':'1.0-opportunity','evaluated_snapshots':len(rows),'best_observed_tc_window':best,'rows':rows,'note':'Opportunity scorecard only until realized chip outcomes are available; no promotion from this file alone.'}
 OUT.parent.mkdir(exist_ok=True);OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2));print('Chip scorecard',len(rows),'snapshots')
if __name__=='__main__':main()

from __future__ import annotations
"""Chip Strategy v1: conservative shadow planner for WC/FH/BB/TC.
Uses production dashboard projections only. It never activates a chip; it emits
opportunity scores and evidence so decisions can later be frozen/backtested.
"""
import json
from pathlib import Path
DATA=Path('data.json'); OUT=Path('chip_strategy_shadow.json')
def n(v,d=0):
 try:return float(v)
 except:return d
def main():
 d=json.loads(DATA.read_text()); gw=int(d.get('gw') or 0); future=d.get('future') or []
 lineup=d.get('lineup') or []; bench=d.get('bench') or []; caps=d.get('captain_comparison') or []
 xi=sum(n(p.get('xp')) for p in lineup); bench_xp=sum(n(p.get('xp')) for p in bench)
 best_cap=max([n(p.get('xp')) for p in caps] or [0]); second=sorted([n(p.get('xp')) for p in caps],reverse=True)[1] if len(caps)>1 else 0
 # TC: incremental third captain score equals one extra captain score. Require a high absolute projection and separation.
 tc_score=max(0,best_cap-7.0)+max(0,best_cap-second)*0.35
 # BB: incremental value is bench points, discounted for uncertainty/minutes.
 bb_reliable=sum(n(p.get('xp'))*min(1,n(p.get('availability'),1))*min(1,n(p.get('expected_minutes'),90)/70) for p in bench)
 bb_score=max(0,bb_reliable-12.0)
 # WC: proxy for structural stress: recommended horizon gain + number of weak/changed slots.
 opt=d.get('optimizer') or {}; horizon=n(opt.get('weighted_gain')); changes=len((d.get('comparison') or {}).get('changes') or [])
 wc_score=max(0,horizon-4.0)+max(0,changes-2)*0.8
 # FH needs a future-round spike versus normal team. Use future XI dispersion as a safe opportunity detector.
 vals=[n(x.get('xi_xp')) for x in future if x.get('xi_xp') is not None]
 fh_score=0; fh_gw=None
 if vals:
  base=sum(vals)/len(vals); best=max(enumerate(vals),key=lambda z:z[1]); fh_score=max(0,best[1]-base-5.0); fh_gw=(future[best[0]].get('gw') if future else None)
 scores={'wildcard':round(wc_score,2),'free_hit':round(fh_score,2),'bench_boost':round(bb_score,2),'triple_captain':round(tc_score,2)}
 best=max(scores,key=scores.get); confidence='LOW' if scores[best]<1 else 'MEDIUM' if scores[best]<3 else 'HIGH'
 payload={'version':'1.0-shadow','gw':gw,'mode':'shadow_only','recommendation':best if confidence!='LOW' else 'hold','confidence':confidence,'scores':scores,'evidence':{'current_xi_xp':round(xi,2),'bench_xp':round(bench_xp,2),'bench_reliable_xp':round(bb_reliable,2),'best_captain_xp':round(best_cap,2),'captain_gap':round(best_cap-second,2),'optimizer_weighted_gain':round(horizon,2),'planned_changes':changes,'free_hit_candidate_gw':fh_gw},'guardrail':'No chip is activated by v1. Freeze and backtest before promotion.'}
 OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2)); print('Chip strategy shadow',payload['recommendation'],confidence,scores)
if __name__=='__main__':main()

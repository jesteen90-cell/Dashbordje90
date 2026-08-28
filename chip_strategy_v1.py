from __future__ import annotations
"""Chip Strategy v1.2: conservative shadow planner with half-season TC reservation."""
import json,math
from pathlib import Path
DATA=Path('data.json'); OUT=Path('chip_strategy_shadow.json')
def n(v,d=0):
 try:return float(v)
 except:return d
def main():
 d=json.loads(DATA.read_text()); gw=int(d.get('gw') or 0); future=d.get('future') or []
 lineup=d.get('lineup') or []; bench=d.get('bench') or []; caps=d.get('captain_comparison') or []
 xi=sum(n(p.get('xp')) for p in lineup); bench_xp=sum(n(p.get('xp')) for p in bench)
 cap_sorted=sorted(caps,key=lambda p:n(p.get('xp')),reverse=True); best_cap=n(cap_sorted[0].get('xp')) if cap_sorted else 0; second=n(cap_sorted[1].get('xp')) if len(cap_sorted)>1 else 0; best_name=cap_sorted[0].get('name') if cap_sorted else None
 # TC chip expires/reset at the end of each half. Use GW19 as first-half cutoff and GW38 as second-half cutoff.
 half=1 if gw<=19 else 2; cutoff=19 if half==1 else 38; rounds_left=max(0,cutoff-gw)
 future_caps=[]
 for x in future:
  xgw=int(x.get('gw') or 0)
  if not xgw or xgw>cutoff:continue
  cx=n(x.get('captain_xp') or x.get('captain_score') or 0)
  if cx:future_caps.append({'gw':xgw,'xp':round(cx,2),'name':x.get('captain')})
 future_caps=sorted(future_caps,key=lambda z:z['xp'],reverse=True)
 future_best=future_caps[0] if future_caps else None
 # Reservation value: keep TC if a better visible spot exists. As cutoff approaches, expiry pressure offsets some reservation value.
 opportunity=max(0,(future_best['xp'] if future_best else best_cap)-best_cap)
 expiry_pressure=max(0,1-rounds_left/8)  # rises materially inside final ~8 rounds of the half
 reservation_cost=opportunity*.85*(1-.55*expiry_pressure)
 # Persistent elite prior is deliberately modest and player-agnostic: long-run elite production is already reflected in Captain v4.
 elite_signal=max(0,best_cap-6.5)*.12
 tc_raw=max(0,best_cap-7.0)+max(0,best_cap-second)*.35+elite_signal
 # Near the cutoff, a good-but-not-perfect spot becomes more usable because an unused chip has zero terminal value.
 terminal_bonus=expiry_pressure*max(0,best_cap-6.0)*.45
 tc_score=max(0,tc_raw-reservation_cost+terminal_bonus)
 bb_reliable=sum(n(p.get('xp'))*min(1,n(p.get('availability'),1))*min(1,n(p.get('expected_minutes'),90)/70) for p in bench); bb_score=max(0,bb_reliable-12.0)
 opt=d.get('optimizer') or {}; horizon=n(opt.get('weighted_gain')); changes=len((d.get('comparison') or {}).get('changes') or []); wc_score=max(0,horizon-4.0)+max(0,changes-2)*.8
 vals=[n(x.get('xi_xp')) for x in future if x.get('xi_xp') is not None]; fh_score=0; fh_gw=None
 if vals:
  base=sum(vals)/len(vals); best=max(enumerate(vals),key=lambda z:z[1]); fh_score=max(0,best[1]-base-5.0); fh_gw=future[best[0]].get('gw')
 scores={'wildcard':round(wc_score,2),'free_hit':round(fh_score,2),'bench_boost':round(bb_score,2),'triple_captain':round(tc_score,2)}; best=max(scores,key=scores.get); confidence='LOW' if scores[best]<1 else 'MEDIUM' if scores[best]<3 else 'HIGH'
 tc_action='USE_NOW' if tc_score>=3 and reservation_cost<.6 else 'CONSIDER' if tc_score>=1.5 else 'HOLD'
 payload={'version':'1.2-half-season-reservation','gw':gw,'mode':'shadow_only','recommendation':best if confidence!='LOW' else 'hold','confidence':confidence,'scores':scores,'tc_decision':tc_action,'evidence':{'current_xi_xp':round(xi,2),'bench_xp':round(bench_xp,2),'bench_reliable_xp':round(bb_reliable,2),'best_captain':best_name,'best_captain_xp':round(best_cap,2),'captain_gap':round(best_cap-second,2),'tc_half':half,'tc_cutoff_gw':cutoff,'tc_rounds_left':rounds_left,'future_captain_spots':future_caps[:5],'future_best_captain_spot':future_best,'tc_opportunity_cost':round(opportunity,2),'tc_reservation_cost':round(reservation_cost,2),'tc_expiry_pressure':round(expiry_pressure,3),'tc_terminal_bonus':round(terminal_bonus,2),'optimizer_weighted_gain':round(horizon,2),'planned_changes':changes,'free_hit_candidate_gw':fh_gw},'guardrail':'No chip is activated. TC uses half-season reservation value and expiry pressure, and remains shadow-only until backtested.'}
 OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2));print('Chip strategy',payload['recommendation'],confidence,'TC',tc_action,scores)
if __name__=='__main__':main()

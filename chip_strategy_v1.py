from __future__ import annotations
"""Chip Strategy v1.3: multi-GW chip sequence planner with TC reservation."""
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
 cap_sorted=sorted(caps,key=lambda p:n(p.get('xp')),reverse=True); best_cap=n(cap_sorted[0].get('xp')) if cap_sorted else 0; second=n(cap_sorted[1].get('xp')) if len(cap_sorted)>1 else 0; best_name=cap_sorted[0].get('name') if cap_sorted else None
 half=1 if gw<=19 else 2; cutoff=19 if half==1 else 38; rounds_left=max(0,cutoff-gw)
 future_caps=[]
 for x in future:
  xgw=int(x.get('gw') or 0)
  if not xgw or xgw>cutoff:continue
  cx=n(x.get('captain_xp') or x.get('captain_score') or 0)
  if cx:future_caps.append({'gw':xgw,'xp':round(cx,2),'name':x.get('captain')})
 future_caps=sorted(future_caps,key=lambda z:z['xp'],reverse=True);future_best=future_caps[0] if future_caps else None
 opportunity=max(0,(future_best['xp'] if future_best else best_cap)-best_cap);expiry_pressure=max(0,1-rounds_left/8);reservation_cost=opportunity*.85*(1-.55*expiry_pressure);elite_signal=max(0,best_cap-6.5)*.12;tc_raw=max(0,best_cap-7.0)+max(0,best_cap-second)*.35+elite_signal;terminal_bonus=expiry_pressure*max(0,best_cap-6.0)*.45;tc_score=max(0,tc_raw-reservation_cost+terminal_bonus)
 bb_reliable=sum(n(p.get('xp'))*min(1,n(p.get('availability'),1))*min(1,n(p.get('expected_minutes'),90)/70) for p in bench);bb_score=max(0,bb_reliable-12.0)
 opt=d.get('optimizer') or {};horizon=n(opt.get('weighted_gain'));changes=len((d.get('comparison') or {}).get('changes') or []);wc_score=max(0,horizon-4.0)+max(0,changes-2)*.8
 # Future round diagnostics. Low XI projection = blank-like stress; unusually high XI/captain = double-like upside.
 vals=[n(x.get('xi_xp')) for x in future if x.get('xi_xp') is not None];base=sum(vals)/len(vals) if vals else xi
 round_diag=[]
 for x in future:
  xgw=int(x.get('gw') or 0);xx=n(x.get('xi_xp'));cx=n(x.get('captain_xp'));blank_stress=max(0,base-xx);double_upside=max(0,xx-base);round_diag.append({'gw':xgw,'xi_xp':round(xx,2),'captain_xp':round(cx,2),'blank_stress':round(blank_stress,2),'double_upside':round(double_upside,2)})
 fh_best=max(round_diag,key=lambda r:r['blank_stress'],default=None);fh_score=max(0,(fh_best or {}).get('blank_stress',0)-4.0);fh_gw=(fh_best or {}).get('gw')
 # BB prefers high-squad-output rounds; WC ideally precedes BB by 1-3 GWs if structural stress is high.
 bb_future=max(round_diag,key=lambda r:r['double_upside'],default=None);bb_future_gw=(bb_future or {}).get('gw');bb_future_bonus=max(0,(bb_future or {}).get('double_upside',0)-3.0)*.45
 bb_score+=bb_future_bonus
 wc_target_gw=None;wc_to_bb_synergy=0
 if bb_future_gw and wc_score>0:
  wc_target_gw=max(gw,bb_future_gw-2);wc_to_bb_synergy=min(1.2,wc_score*.18+bb_future_bonus*.25)
 # Allocate chips to distinct preferred GWs and charge collisions when two chips want same week.
 preferred={'triple_captain':gw if tc_score>=1.5 else ((future_best or {}).get('gw')),'bench_boost':bb_future_gw or gw,'free_hit':fh_gw,'wildcard':wc_target_gw or gw}
 collisions=[];seen={}
 for chip,cgw in preferred.items():
  if not cgw:continue
  if cgw in seen:collisions.append({'gw':cgw,'chips':[seen[cgw],chip]})
  else:seen[cgw]=chip
 collision_penalty={k:0.0 for k in preferred}
 for c in collisions:
  for chip in c['chips']:
   # WC may intentionally precede BB; same-GW chip collisions are always bad.
   collision_penalty[chip]+=0.65
 # Sequence-aware adjustments.
 wc_score=max(0,wc_score+wc_to_bb_synergy-collision_penalty['wildcard'])
 bb_score=max(0,bb_score+wc_to_bb_synergy*.35-collision_penalty['bench_boost'])
 fh_score=max(0,fh_score-collision_penalty['free_hit'])
 tc_score=max(0,tc_score-collision_penalty['triple_captain'])
 scores={'wildcard':round(wc_score,2),'free_hit':round(fh_score,2),'bench_boost':round(bb_score,2),'triple_captain':round(tc_score,2)};best=max(scores,key=scores.get);confidence='LOW' if scores[best]<1 else 'MEDIUM' if scores[best]<3 else 'HIGH'
 tc_action='USE_NOW' if tc_score>=3 and reservation_cost<.6 and preferred['triple_captain']==gw else 'CONSIDER' if tc_score>=1.5 else 'HOLD'
 # Build ordered chip roadmap, one chip per GW.
 roadmap=[]
 for chip in ('wildcard','free_hit','bench_boost','triple_captain'):
  cgw=preferred.get(chip);sc=scores.get(chip,0)
  if cgw and sc>=.75:roadmap.append({'gw':int(cgw),'chip':chip,'score':round(sc,2)})
 roadmap=sorted(roadmap,key=lambda r:(r['gw'],-r['score']))
 used=set();clean=[]
 for r in roadmap:
  if r['gw'] in used:continue
  clean.append(r);used.add(r['gw'])
 payload={'version':'1.3-sequence-planner','gw':gw,'mode':'shadow_only','recommendation':best if confidence!='LOW' else 'hold','confidence':confidence,'scores':scores,'tc_decision':tc_action,'chip_roadmap':clean,'collisions':collisions,'evidence':{'current_xi_xp':round(xi,2),'bench_xp':round(bench_xp,2),'bench_reliable_xp':round(bb_reliable,2),'best_captain':best_name,'best_captain_xp':round(best_cap,2),'captain_gap':round(best_cap-second,2),'tc_half':half,'tc_cutoff_gw':cutoff,'tc_rounds_left':rounds_left,'future_captain_spots':future_caps[:5],'future_best_captain_spot':future_best,'tc_opportunity_cost':round(opportunity,2),'tc_reservation_cost':round(reservation_cost,2),'tc_expiry_pressure':round(expiry_pressure,3),'tc_terminal_bonus':round(terminal_bonus,2),'optimizer_weighted_gain':round(horizon,2),'planned_changes':changes,'free_hit_candidate_gw':fh_gw,'bench_boost_candidate_gw':bb_future_gw,'wildcard_candidate_gw':wc_target_gw,'wc_to_bb_synergy':round(wc_to_bb_synergy,2),'round_diagnostics':round_diag[:8]},'guardrail':'No chip is activated. v1.3 plans distinct chip windows, models WC→BB synergy, blank-like FH stress and TC reservation.'}
 OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2));print('Chip sequence',payload['recommendation'],confidence,clean)
if __name__=='__main__':main()

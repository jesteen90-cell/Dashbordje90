"""Multi-GW captain ownership value.

The transfer optimizer already doubles the best captain in each future XI. This
module therefore does NOT add captain points again. Instead it identifies players
who are repeatedly near the global best captain projection so candidate pruning
and transfer diagnostics do not discard expensive elite captain options too early.
"""
from __future__ import annotations

def n(v,d=0.0):
 try:return float(v)
 except:return d

def horizon_values(players,gws,weights):
 out={int(p['id']):{'captain_horizon_bonus':0.0,'top1_gws':0,'top2_gws':0,'near_best_gws':0,'captain_gap_sum':0.0,'by_gw':{}} for p in players}
 for gw in gws:
  ranked=sorted(players,key=lambda p:n((p.get('_x') or {}).get(gw)),reverse=True)
  if not ranked:continue
  best=n((ranked[0].get('_x') or {}).get(gw));second=n((ranked[1].get('_x') or {}).get(gw)) if len(ranked)>1 else best;w=n(weights.get(gw),1)
  for i,p in enumerate(ranked[:16]):
   pid=int(p['id']);xp=n((p.get('_x') or {}).get(gw));gap=max(0.0,best-xp);rec=out[pid]
   rec['captain_gap_sum']+=gap*w
   if i==0:rec['top1_gws']+=1
   if i<=1:rec['top2_gws']+=1
   utility=0.0
   if gap<=0.75:
    rec['near_best_gws']+=1
    utility=(max(0.0,0.75-gap)/0.75)*0.55*w
   if i==1 and best-second<=0.35:utility+=0.10*w
   if utility>0:
    rec['captain_horizon_bonus']+=utility;rec['by_gw'][str(gw)]=round(utility,3)
 for rec in out.values():
  rec['captain_horizon_bonus']=round(min(2.2,rec['captain_horizon_bonus']),3);rec['captain_gap_sum']=round(rec['captain_gap_sum'],3)
 return out

def attach(players,gws,weights):
 vals=horizon_values(players,gws,weights)
 for p in players:p['_captain_horizon']=vals.get(int(p['id']),{'captain_horizon_bonus':0.0,'top1_gws':0,'top2_gws':0,'near_best_gws':0,'captain_gap_sum':0.0,'by_gw':{}})
 return vals

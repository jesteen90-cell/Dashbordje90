"""Multi-GW captain ownership value.

Quantifies the value of owning players who repeatedly project as elite captain
options across the planning horizon. This is deliberately bounded and is meant
as an ownership/transfer signal, not a replacement for single-GW captain choice.
"""
from __future__ import annotations

def n(v,d=0.0):
 try:return float(v)
 except:return d

def horizon_values(players,gws,weights):
 """Return per-player captain-option persistence metrics.

 For each GW we rank by projected xP. A player earns extra ownership utility only
 when he is very near the best captain option. This avoids rewarding expensive
 players merely for being generally strong.
 """
 out={int(p['id']):{'captain_horizon_bonus':0.0,'top1_gws':0,'top2_gws':0,'near_best_gws':0,'captain_gap_sum':0.0} for p in players}
 for gw in gws:
  ranked=sorted(players,key=lambda p:n((p.get('_x') or {}).get(gw)),reverse=True)
  if not ranked:continue
  best=n((ranked[0].get('_x') or {}).get(gw));second=n((ranked[1].get('_x') or {}).get(gw)) if len(ranked)>1 else best
  w=n(weights.get(gw),1)
  for i,p in enumerate(ranked[:12]):
   pid=int(p['id']);xp=n((p.get('_x') or {}).get(gw));gap=max(0.0,best-xp)
   rec=out[pid];rec['captain_gap_sum']+=gap*w
   if i==0:rec['top1_gws']+=1
   if i<=1:rec['top2_gws']+=1
   if gap<=0.75:
    rec['near_best_gws']+=1
    # Bounded ownership value: up to 0.55 weighted points per GW when essentially best.
    rec['captain_horizon_bonus']+=(max(0.0,0.75-gap)/0.75)*0.55*w
  # give the clear #2 some value when very close to #1
  if len(ranked)>1 and best-second<=0.35:
   out[int(ranked[1]['id'])]['captain_horizon_bonus']+=0.10*w
 for rec in out.values():
  rec['captain_horizon_bonus']=round(min(2.2,rec['captain_horizon_bonus']),3)
  rec['captain_gap_sum']=round(rec['captain_gap_sum'],3)
 return out

def attach(players,gws,weights):
 vals=horizon_values(players,gws,weights)
 for p in players:
  p['_captain_horizon']=vals.get(int(p['id']),{'captain_horizon_bonus':0.0,'top1_gws':0,'top2_gws':0,'near_best_gws':0,'captain_gap_sum':0.0})
 return vals

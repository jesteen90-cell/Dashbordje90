"""Premium captain squad-structure shadow evaluator.

Compares realistic two-transfer squad structures from the current 15-man squad:
A) premium forward + cheaper midfielder
B) premium midfielder + cheaper forward

It uses multi-GW player projections exported by generate_dashboard_v3 and scores
best XI + best captain every GW. This isolates whether tying budget up in an elite
captain forward (Haaland-type) is worth the opportunity cost elsewhere.
"""
from __future__ import annotations
import json,itertools
from pathlib import Path

PROJ=Path('projection_cache.json'); DATA=Path('data.json'); OUT=Path('premium_structure_shadow.json')
POS_COUNTS={1:2,2:5,3:5,4:3}

def n(v,d=0.0):
 try:return float(v)
 except:return d

def legal(sq):
 if len(sq)!=15 or len({int(p['id']) for p in sq})!=15:return False
 if {pos:sum(int(p['element_type'])==pos for p in sq) for pos in POS_COUNTS}!=POS_COUNTS:return False
 clubs={}
 for p in sq:clubs[int(p['team'])]=clubs.get(int(p['team']),0)+1
 return max(clubs.values(),default=0)<=3

def best_xi_value(sq,gw):
 by={pos:[p for p in sq if int(p['element_type'])==pos] for pos in POS_COUNTS};best=None
 for gk in itertools.combinations(by[1],1):
  for nd in range(3,6):
   for nm in range(2,6):
    nf=10-nd-nm
    if not 1<=nf<=3 or nd>len(by[2]) or nm>len(by[3]) or nf>len(by[4]):continue
    for ds in itertools.combinations(by[2],nd):
     for ms in itertools.combinations(by[3],nm):
      for fs in itertools.combinations(by[4],nf):
       xi=list(gk+ds+ms+fs);raw=sum(n(p.get('xp',{}).get(str(gw))) for p in xi)
       cap=max((n(p.get('xp',{}).get(str(gw))) for p in xi),default=0)
       val=raw+cap
       if best is None or val>best[0]:best=(val,xi,cap)
 return best or (0,[],0)

def horizon_value(sq,gws,weights):
 rows=[];total=0.0
 for gw in gws:
  val,xi,cap=best_xi_value(sq,gw);w=n(weights.get(str(gw)),1);total+=val*w
  cap_player=max(xi,key=lambda p:n(p.get('xp',{}).get(str(gw))),default=None)
  rows.append({'gw':gw,'weighted_value':round(val*w,3),'captain':cap_player.get('name') if cap_player else None,'captain_xp':round(cap,3)})
 return total,rows

def main():
 if not PROJ.exists() or not DATA.exists():
  print('Premium structure: projection cache missing');return
 pc=json.loads(PROJ.read_text());d=json.loads(DATA.read_text());players=pc['players'];byid={int(p['id']):p for p in players};gws=[int(x) for x in pc['gws']];weights={str(k):v for k,v in pc['weights'].items()};bank=int(pc.get('bank',0));squad=[byid[int(x)] for x in pc['squad_ids'] if int(x) in byid]
 if len(squad)!=15:return
 base,base_rows=horizon_value(squad,gws,weights)
 # Premium thresholds are price bands, not names. Price is tenths of a million.
 prem_f=[p for p in players if int(p['element_type'])==4 and int(p['now_cost'])>=115]
 prem_m=[p for p in players if int(p['element_type'])==3 and int(p['now_cost'])>=95]
 # Focus search on genuine high-end captain assets.
 def cap_score(p):return sum(n(p.get('xp',{}).get(str(g)))*n(weights.get(str(g)),1) for g in gws)
 prem_f=sorted(prem_f,key=cap_score,reverse=True)[:4];prem_m=sorted(prem_m,key=cap_score,reverse=True)[:5]
 cheap_m=sorted([p for p in players if int(p['element_type'])==3 and int(p['now_cost'])<=75],key=cap_score,reverse=True)[:14]
 cheap_f=sorted([p for p in players if int(p['element_type'])==4 and int(p['now_cost'])<=85],key=cap_score,reverse=True)[:12]
 scenarios=[]
 owned={int(p['id']) for p in squad}
 def add_structure(label,premium,sell_p,cheap,sell_support):
  if int(premium['id']) in owned or int(cheap['id']) in owned:return
  budget=bank+int(sell_p['now_cost'])+int(sell_support['now_cost'])
  cost=int(premium['now_cost'])+int(cheap['now_cost'])
  if cost>budget:return
  ns=[p for p in squad if int(p['id']) not in (int(sell_p['id']),int(sell_support['id']))]+[premium,cheap]
  if not legal(ns):return
  val,rows=horizon_value(ns,gws,weights);scenarios.append({'structure':label,'premium':premium['name'],'support':cheap['name'],'out':[sell_p['name'],sell_support['name']],'cost':cost,'bank_after':budget-cost,'horizon_value':round(val,3),'delta_vs_current':round(val-base,3),'captains':rows})
 for pf in prem_f:
  for sf in [p for p in squad if int(p['element_type'])==4]:
   for sm in [p for p in squad if int(p['element_type'])==3]:
    for cm in cheap_m[:8]:add_structure('premium_forward',pf,sf,cm,sm)
 for pm in prem_m:
  for sm in [p for p in squad if int(p['element_type'])==3]:
   for sf in [p for p in squad if int(p['element_type'])==4]:
    for cf in cheap_f[:8]:add_structure('premium_midfielder',pm,sm,cf,sf)
 # Deduplicate by resulting named pair and keep best opportunity-cost route.
 best={}
 for s in scenarios:
  k=(s['structure'],s['premium'],s['support'])
  if k not in best or s['horizon_value']>best[k]['horizon_value']:best[k]=s
 xs=sorted(best.values(),key=lambda x:x['horizon_value'],reverse=True)[:20]
 best_f=next((x for x in xs if x['structure']=='premium_forward'),None);best_m=next((x for x in xs if x['structure']=='premium_midfielder'),None)
 verdict='current_structure'
 if best_f and best_f['delta_vs_current']>0.75 and (not best_m or best_f['horizon_value']>best_m['horizon_value']+0.35):verdict='premium_forward'
 elif best_m and best_m['delta_vs_current']>0.75 and (not best_f or best_m['horizon_value']>best_f['horizon_value']+0.35):verdict='premium_midfielder'
 payload={'version':'1.0-shadow','gw':d.get('gw'),'gws':gws,'current_horizon_value':round(base,3),'current_captains':base_rows,'best_premium_forward':best_f,'best_premium_midfielder':best_m,'verdict':verdict,'scenarios':xs}
 OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2));print('Premium structure shadow',verdict,'base',round(base,2),'F',best_f and best_f['delta_vs_current'],'M',best_m and best_m['delta_vs_current'])
if __name__=='__main__':main()

"""Premium captain squad-structure shadow evaluator."""
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
       xi=list(gk+ds+ms+fs);raw=sum(n(p.get('xp',{}).get(str(gw))) for p in xi);cap_player=max(xi,key=lambda p:n(p.get('xp',{}).get(str(gw))),default=None);cap=n((cap_player or {}).get('xp',{}).get(str(gw)));val=raw+cap
       if best is None or val>best[0]:best=(val,xi,cap_player,cap)
 return best or (0,[],None,0)
def horizon_value(sq,gws,weights):
 rows=[];total=0.0
 for gw in gws:
  val,xi,cap_player,cap=best_xi_value(sq,gw);w=n(weights.get(str(gw)),1);total+=val*w
  rows.append({'gw':gw,'weighted_value':round(val*w,3),'xi_ids':[int(p['id']) for p in xi],'captain_id':int(cap_player['id']) if cap_player else None,'captain':cap_player.get('name') if cap_player else None,'captain_xp':round(cap,3)})
 return total,rows
def main():
 if not PROJ.exists() or not DATA.exists():return
 pc=json.loads(PROJ.read_text());d=json.loads(DATA.read_text());players=pc['players'];byid={int(p['id']):p for p in players};gws=[int(x) for x in pc['gws']];weights={str(k):v for k,v in pc['weights'].items()};bank=int(pc.get('bank',0));squad=[byid[int(x)] for x in pc['squad_ids'] if int(x) in byid]
 if len(squad)!=15:return
 base,base_rows=horizon_value(squad,gws,weights)
 prem_f=[p for p in players if int(p['element_type'])==4 and int(p['now_cost'])>=115];prem_m=[p for p in players if int(p['element_type'])==3 and int(p['now_cost'])>=95]
 def cap_score(p):return sum(n(p.get('xp',{}).get(str(g)))*n(weights.get(str(g)),1) for g in gws)
 prem_f=sorted(prem_f,key=cap_score,reverse=True)[:4];prem_m=sorted(prem_m,key=cap_score,reverse=True)[:5];cheap_m=sorted([p for p in players if int(p['element_type'])==3 and int(p['now_cost'])<=75],key=cap_score,reverse=True)[:14];cheap_f=sorted([p for p in players if int(p['element_type'])==4 and int(p['now_cost'])<=85],key=cap_score,reverse=True)[:12]
 scenarios=[];owned={int(p['id']) for p in squad}
 def add_structure(label,premium,sell_p,cheap,sell_support):
  if int(premium['id']) in owned or int(cheap['id']) in owned:return
  budget=bank+int(sell_p['now_cost'])+int(sell_support['now_cost']);cost=int(premium['now_cost'])+int(cheap['now_cost'])
  if cost>budget:return
  ns=[p for p in squad if int(p['id']) not in (int(sell_p['id']),int(sell_support['id']))]+[premium,cheap]
  if not legal(ns):return
  val,rows=horizon_value(ns,gws,weights);scenarios.append({'structure':label,'premium':premium['name'],'premium_id':int(premium['id']),'support':cheap['name'],'support_id':int(cheap['id']),'out':[sell_p['name'],sell_support['name']],'out_ids':[int(sell_p['id']),int(sell_support['id'])],'squad_ids':[int(p['id']) for p in ns],'cost':cost,'bank_after':budget-cost,'horizon_value':round(val,3),'delta_vs_current':round(val-base,3),'captains':rows})
 for pf in prem_f:
  for sf in [p for p in squad if int(p['element_type'])==4]:
   for sm in [p for p in squad if int(p['element_type'])==3]:
    for cm in cheap_m[:8]:add_structure('premium_forward',pf,sf,cm,sm)
 for pm in prem_m:
  for sm in [p for p in squad if int(p['element_type'])==3]:
   for sf in [p for p in squad if int(p['element_type'])==4]:
    for cf in cheap_f[:8]:add_structure('premium_midfielder',pm,sm,cf,sf)
 best={}
 for s in scenarios:
  k=(s['structure'],s['premium_id'],s['support_id'])
  if k not in best or s['horizon_value']>best[k]['horizon_value']:best[k]=s
 xs=sorted(best.values(),key=lambda x:x['horizon_value'],reverse=True)[:20];best_f=next((x for x in xs if x['structure']=='premium_forward'),None);best_m=next((x for x in xs if x['structure']=='premium_midfielder'),None);verdict='current_structure'
 if best_f and best_f['delta_vs_current']>0.75 and (not best_m or best_f['horizon_value']>best_m['horizon_value']+0.35):verdict='premium_forward'
 elif best_m and best_m['delta_vs_current']>0.75 and (not best_f or best_m['horizon_value']>best_f['horizon_value']+0.35):verdict='premium_midfielder'
 payload={'version':'1.1-backtest-ready','gw':d.get('gw'),'gws':gws,'weights':weights,'current_squad_ids':[int(p['id']) for p in squad],'current_horizon_value':round(base,3),'current_captains':base_rows,'best_premium_forward':best_f,'best_premium_midfielder':best_m,'verdict':verdict,'scenarios':xs};OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2));print('Premium structure',verdict)
if __name__=='__main__':main()

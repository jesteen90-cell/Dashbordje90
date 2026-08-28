"""Run production generator once, enrich feed safely, and export projections.

Keeps premium-structure tests on exactly the same xP surface as production,
without maintaining a second projection model. Feed enrichment is deliberately
post-generation so UI metadata cannot destabilise the projection engine.
"""
import json,runpy
from pathlib import Path
from team_strength_v2 import fixture_difficulty

ns=runpy.run_path('generate_dashboard_v3.py')
players=ns['players'];gws=ns['GWS'];weights=ns['weights'];squad=ns['squad'];bank=ns['bank'];ratings=ns['ratings'];fm=ns['fm'];teams=ns['teams']
byid={int(p['id']):p for p in players}

set_piece_roles={}
try:
 set_piece_roles=json.loads(Path('set_piece_roles.json').read_text())
except Exception:
 set_piece_roles={}
penalty_roles=set_piece_roles.get('penalties') or {}

def penalty_share_for(row):
 name=str(row.get('name') or '')
 full=None
 p=byid.get(int(row.get('id') or 0))
 if p:full=' '.join(x for x in (p.get('first_name'),p.get('second_name')) if x).strip()
 for key in (full,name):
  if key and key in penalty_roles:return float(penalty_roles[key])
 return 0.0

def outlook_for(row):
 pid=int(row.get('id') or 0);p=byid.get(pid);tid=int(row.get('team_id') or (p or {}).get('team') or 0);pos=row.get('position') or {1:'GK',2:'DEF',3:'MID',4:'FWD'}.get(int((p or {}).get('element_type') or 0),'')
 out=[]
 for g in gws[:3]:
  fs=fm.get(g,{}).get(tid,[])
  if not fs:out.append({'gw':g,'label':'BLANK','difficulty':5,'difficulty_basis':'blank','xp':0});continue
  for f in fs:
   diff,basis=fixture_difficulty(ratings,int(f['opp']),bool(f['home']),pos);xp=float((p or {}).get('_x',{}).get(g,0));out.append({'gw':g,'label':f"{teams.get(f['opp'],'?')[:3].upper()} {'H' if f['home'] else 'A'}",'difficulty':diff,'difficulty_basis':basis,'xp':round(xp,2)})
 return out

def reconcile_breakdown(row):
 bd=row.get('xp_breakdown')
 if not isinstance(bd,dict):return
 total=round(float(row.get('xp') or 0),2);shown=round(sum(float(v or 0) for v in bd.values()),2);residual=round(total-shown,2)
 if abs(residual)>=.01:bd['other_model_components']=residual
 bd['displayed_sum']=round(sum(float(v or 0) for k,v in bd.items() if k!='displayed_sum'),2);bd['reconciled']=abs(bd['displayed_sum']-total)<.011

def enrich(obj):
 if isinstance(obj,dict):
  if obj.get('id') is not None and obj.get('position') in ('GK','DEF','MID','FWD') and int(obj.get('id') or 0) in byid:
   obj['fixture_outlook']=outlook_for(obj);share=penalty_share_for(obj);obj['set_pieces']={'penalty_taker_share':round(share,3),'penalty_role':'first-choice' if share>=.8 else ('secondary' if share>0 else 'unknown'),'source':'set_piece_roles.json' if share>0 else 'none'};reconcile_breakdown(obj)
  for v in obj.values():enrich(v)
 elif isinstance(obj,list):
  for v in obj:enrich(v)

def budget_summary():
 market_value_raw=sum(int(p.get('now_cost') or 0) for p in squad);bank_raw=int(bank or 0);selling_live=all(p.get('selling_price') is not None for p in squad);selling_value_raw=sum(int(p.get('selling_price') if p.get('selling_price') is not None else p.get('now_cost') or 0) for p in squad)
 return {'bank':round(bank_raw/10,1),'squad_market_value':round(market_value_raw/10,1),'squad_selling_value':round(selling_value_raw/10,1),'market_budget_total':round((market_value_raw+bank_raw)/10,1),'selling_budget_total':round((selling_value_raw+bank_raw)/10,1),'bank_raw':bank_raw,'squad_market_value_raw':market_value_raw,'squad_selling_value_raw':selling_value_raw,'currency':'GBP','selling_value_live':selling_live,'selling_value_note':'Faktisk FPL-salgsverdi brukes.' if selling_live else 'Lagverdien er markedspris. Faktisk FPL-salgsverdi kan være lavere for spillere som har steget i pris.'}

def option_pool():
 """Compact public surface for future-flexibility analysis.

 Keeps the top 35 horizon players per position plus every currently owned
 player. This avoids publishing/depending on the full internal projection cache.
 """
 owned={int(p['id']) for p in squad};keep=set(owned)
 for pos in (1,2,3,4):
  xs=[p for p in players if int(p.get('element_type') or 0)==pos]
  xs.sort(key=lambda p:float(p.get('_h') or 0),reverse=True)
  keep.update(int(p['id']) for p in xs[:35])
 out=[]
 for pid in keep:
  p=byid.get(pid)
  if not p:continue
  out.append({'id':pid,'name':p.get('web_name'),'team':int(p.get('team') or 0),'element_type':int(p.get('element_type') or 0),'now_cost':int(p.get('now_cost') or 0),'horizon':round(float(p.get('_h') or 0),3),'xp':{str(g):round(float((p.get('_x') or {}).get(g,0)),3) for g in gws[:4]}})
 return out

feed_path=Path('data.json')
if feed_path.exists():
 feed=json.loads(feed_path.read_text());enrich(feed);feed['fixture_difficulty_model']={'version':'2.0-position-aware','defenders':'opponent-attack','attackers':'opponent-defence','home_away_adjusted':True};feed['budget']=budget_summary();feed['transfer_option_pool']={'version':'1.0-compact','players':option_pool(),'gws':gws[:4],'weights':{str(k):v for k,v in weights.items() if k in gws[:4]},'owned_ids':[int(p['id']) for p in squad]}
 model_version=str(feed.get('model_version') or '');projection_active=('set-piece-projection' in model_version);feed['set_piece_model']={'version':set_piece_roles.get('version','none'),'penalty_roles_loaded':len(penalty_roles),'projection_integration':'active' if projection_active else 'pending','display_metadata_active':bool(penalty_roles)}
 if projection_active and feed['set_piece_model']['projection_integration']!='active':raise RuntimeError('Set-piece projection is active but feed status is not active')
 feed_path.write_text(json.dumps(feed,ensure_ascii=False,indent=2));print('Applied fixture difficulty, xP reconciliation, budget, option pool and set-piece metadata')

rows=[]
for p in players:rows.append({'id':int(p['id']),'name':p['web_name'],'team':int(p['team']),'element_type':int(p['element_type']),'now_cost':int(p['now_cost']),'xp':{str(g):round(float(p['_x'].get(g,0)),4) for g in gws}})
out={'version':'1.2-sale-budget-aware','gws':gws,'weights':{str(k):v for k,v in weights.items()},'squad_ids':[int(p['id']) for p in squad],'bank':int(bank),'budget':budget_summary(),'players':rows}
Path('projection_cache.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print('Exported production projection cache',len(rows),'players')

runpy.run_path('budget_intelligence_v1.py',run_name='__main__')

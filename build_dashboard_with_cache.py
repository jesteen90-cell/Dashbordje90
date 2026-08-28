"""Run the production generator once, fix position-aware fixture outlook, and export projections.

Keeps premium-structure tests on exactly the same xP surface as production,
without maintaining a second projection model.
"""
import json,runpy
from pathlib import Path
from team_strength_v2 import fixture_difficulty

ns=runpy.run_path('generate_dashboard_v3.py')
players=ns['players'];gws=ns['GWS'];weights=ns['weights'];squad=ns['squad'];bank=ns['bank'];ratings=ns['ratings'];fm=ns['fm'];teams=ns['teams']
byid={int(p['id']):p for p in players}

def outlook_for(row):
 pid=int(row.get('id') or 0);p=byid.get(pid);tid=int(row.get('team_id') or (p or {}).get('team') or 0);pos=row.get('position') or {1:'GK',2:'DEF',3:'MID',4:'FWD'}.get(int((p or {}).get('element_type') or 0),'')
 out=[]
 for g in gws[:3]:
  fs=fm.get(g,{}).get(tid,[])
  if not fs:
   out.append({'gw':g,'label':'BLANK','difficulty':5,'difficulty_basis':'blank','xp':0});continue
  for f in fs:
   diff,basis=fixture_difficulty(ratings,int(f['opp']),bool(f['home']),pos)
   xp=float((p or {}).get('_x',{}).get(g,0))
   out.append({'gw':g,'label':f"{teams.get(f['opp'],'?')[:3].upper()} {'H' if f['home'] else 'A'}",'difficulty':diff,'difficulty_basis':basis,'xp':round(xp,2)})
 return out

def enrich(obj):
 if isinstance(obj,dict):
  if obj.get('id') is not None and obj.get('position') in ('GK','DEF','MID','FWD') and int(obj.get('id') or 0) in byid:
   obj['fixture_outlook']=outlook_for(obj)
  for v in obj.values():enrich(v)
 elif isinstance(obj,list):
  for v in obj:enrich(v)

feed_path=Path('data.json')
if feed_path.exists():
 feed=json.loads(feed_path.read_text());enrich(feed);feed['fixture_difficulty_model']={'version':'2.0-position-aware','defenders':'opponent-attack','attackers':'opponent-defence','home_away_adjusted':True};feed_path.write_text(json.dumps(feed,ensure_ascii=False,indent=2));print('Applied position-aware fixture difficulty')

rows=[]
for p in players:
 rows.append({'id':int(p['id']),'name':p['web_name'],'team':int(p['team']),'element_type':int(p['element_type']),'now_cost':int(p['now_cost']),'xp':{str(g):round(float(p['_x'].get(g,0)),4) for g in gws}})
out={'version':'1.0','gws':gws,'weights':{str(k):v for k,v in weights.items()},'squad_ids':[int(p['id']) for p in squad],'bank':int(bank),'players':rows}
Path('projection_cache.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print('Exported production projection cache',len(rows),'players')

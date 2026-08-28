"""Explain captain model component differences without affecting selection."""
import json
from pathlib import Path

SHADOW=Path('captain_v4_shadow.json'); DATA=Path('data.json')

def n(v,d=0.0):
 try:return float(v)
 except:return d

def main():
 d=json.loads(DATA.read_text())
 s=json.loads(SHADOW.read_text()) if SHADOW.exists() else {}
 rows=s.get('candidates') or []
 byname={str(r.get('name','')).lower():r for r in rows}

def pick_name(rows,needle):
 for r in rows:
  if needle in str(r.get('name','')).lower(): return r
 return None

def compact(r):
 if not r:return None
 hp=r.get('haul_probabilities') or {}
 return {
  'id':r.get('id'),'name':r.get('name'),'team':r.get('team'),
  'xp':r.get('xp'),'ceiling':r.get('ceiling'),'expected_minutes':r.get('expected_minutes'),
  'v3_score':r.get('v3_score'),'elite_prior':r.get('elite_prior'),'haul_bonus':r.get('haul_bonus'),'v41_score':r.get('v41_score'),
  'goal_lambda':hp.get('goal_lambda'),'assist_lambda':hp.get('assist_lambda'),
  'p_goal_2plus':hp.get('p_goal_2'),'p_multi_return':hp.get('p_multi_return'),'p10_plus':hp.get('p10'),'p15_plus':hp.get('p15'),
  'prev_minutes':r.get('prev_minutes'),'prev_points':r.get('prev_points')
 }

def delta(a,b):
 if not a or not b:return None
 keys=['xp','ceiling','expected_minutes','v3_score','elite_prior','haul_bonus','v41_score']
 out={}
 for k in keys: out[k]=round(n(a.get(k))-n(b.get(k)),4)
 for k in ['goal_lambda','p_goal_2plus','p_multi_return','p10_plus','p15_plus']:
  out[k]=round(n(a.get(k))-n(b.get(k)),4)
 return out

def run():
 s=json.loads(SHADOW.read_text()) if SHADOW.exists() else {}
 rows=s.get('candidates') or []
 leader=compact(rows[0]) if rows else None
 haaland=compact(pick_name(rows,'haaland'))
 joao=compact(pick_name(rows,'joão pedro') or pick_name(rows,'joao pedro'))
 payload={
  'version':'1.0','gw':s.get('gw'),'candidate_count':len(rows),'leader':leader,
  'haaland':haaland,'joao_pedro':joao,
  'haaland_vs_joao':delta(haaland,joao),
  'haaland_vs_leader':delta(haaland,leader),
  'note':'Diagnostics only. This file never changes captain selection.'
 }
 Path('captain_diagnostics.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2))
 print('Captain diagnostics:', 'leader=', leader and leader.get('name'), 'Haaland=', haaland and haaland.get('v41_score'), 'Joao=', joao and joao.get('v41_score'))

if __name__=='__main__':run()

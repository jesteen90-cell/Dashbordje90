"""Freeze Captain v3 vs v4 vs v4.1 haul-aware choices for regret evaluation."""
import json
from pathlib import Path
from captain_v4_prior import score
from captain_haul_v41 import haul_bonus

DATA=Path('data.json'); OUT=Path('captain_v4_shadow.json')
def main():
 d=json.loads(DATA.read_text()); players=d.get('captain_comparison') or []
 rows=[]
 for p in players:
  v3=float(p.get('score',p.get('xp',0)))
  raw={'minutes':p.get('season_minutes',p.get('expected_minutes',90)),'total_points':p.get('season_points',0),'expected_goals':p.get('season_xg',0),'expected_assists':p.get('season_xa',0),'goals_scored':p.get('season_goals',0),'assists':p.get('season_assists',0),'prev_minutes':p.get('prev_minutes',0),'prev_points':p.get('prev_points',0),'prev_goals':p.get('prev_goals',0),'prev_assists':p.get('prev_assists',0)}
  proj={'xmins':p.get('expected_minutes',0),'p90':p.get('ceiling',p.get('xp',0)),'xp':p.get('xp',0),'attack_multiplier':p.get('attack_multiplier',1.0)}
  v4,prior=score(raw,proj,v3);hb,hf=haul_bonus(raw,proj);v41=v4+hb
  rows.append({'id':p.get('id'),'name':p.get('name'),'team':p.get('team'),'v3_score':round(v3,4),'v4_score':round(v4,4),'v41_score':round(v41,4),'elite_prior':round(prior,4),'haul_bonus':round(hb,4),'haul_probabilities':{k:round(v,4) for k,v in hf.items()},'xp':p.get('xp'),'ceiling':p.get('ceiling'),'expected_minutes':p.get('expected_minutes'),'prev_minutes':p.get('prev_minutes',0),'prev_points':p.get('prev_points',0)} )
 rows.sort(key=lambda x:x['v41_score'],reverse=True);v4=sorted(rows,key=lambda x:x['v4_score'],reverse=True);v3=sorted(rows,key=lambda x:x['v3_score'],reverse=True)
 payload={'version':'4.2-haul-history-shadow','gw':d.get('gw'),'deadline_time':d.get('deadline_time'),'v3_pick':v3[0] if v3 else None,'v4_pick':v4[0] if v4 else None,'v41_pick':rows[0] if rows else None,'candidates':rows,'guardrail':'Historical prior is bounded and fades as current-season evidence grows; production promotion still requires frozen regret evidence.'}
 OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2));print('Captain shadow:',payload.get('v3_pick',{}).get('name'),'vs v4',payload.get('v4_pick',{}).get('name'),'vs history-haul',payload.get('v41_pick',{}).get('name'),'pool',len(rows))
if __name__=='__main__':main()

"""Freeze Captain v3 vs v4 choices for later regret evaluation."""
import json
from pathlib import Path
from captain_v4_prior import score

DATA=Path('data.json'); OUT=Path('captain_v4_shadow.json')
def main():
 d=json.loads(DATA.read_text()); players=d.get('captain_comparison') or []
 rows=[]
 for p in players:
  # captain_comparison already exposes production v3 score/ranking inputs.
  v3=float(p.get('score',p.get('xp',0)))
  # Build a compatible lightweight player/projection view from dashboard fields.
  raw={'minutes':p.get('season_minutes',p.get('expected_minutes',90)),'total_points':p.get('season_points',0),'expected_goals':p.get('season_xg',0),'expected_assists':p.get('season_xa',0),'goals_scored':p.get('season_goals',0)}
  proj={'xmins':p.get('expected_minutes',0),'p90':p.get('ceiling',p.get('xp',0))}
  v4,prior=score(raw,proj,v3)
  rows.append({'id':p.get('id'),'name':p.get('name'),'team':p.get('team'),'v3_score':round(v3,4),'v4_score':round(v4,4),'elite_prior':round(prior,4),'xp':p.get('xp'),'expected_minutes':p.get('expected_minutes')})
 rows.sort(key=lambda x:x['v4_score'],reverse=True)
 v3=sorted(rows,key=lambda x:x['v3_score'],reverse=True)
 payload={'version':'4.0-shadow','gw':d.get('gw'),'deadline_time':d.get('deadline_time'),'v3_pick':v3[0] if v3 else None,'v4_pick':rows[0] if rows else None,'candidates':rows}
 OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2));print('Captain v4 shadow:',payload.get('v3_pick',{}).get('name'),'vs',payload.get('v4_pick',{}).get('name'))
if __name__=='__main__':main()

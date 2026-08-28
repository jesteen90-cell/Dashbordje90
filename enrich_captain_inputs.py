"""Inject current and previous-season captain inputs before Captain v4/v4.1 scoring."""
import json,requests
from pathlib import Path
PATH=Path('data.json');BASE='https://fantasy.premierleague.com/api'

def main():
 d=json.loads(PATH.read_text(encoding='utf-8'))
 s=requests.Session();s.headers.update({'User-Agent':'fpl-autopilot-captain-v4-enrich'})
 r=s.get(f'{BASE}/bootstrap-static/',timeout=18);r.raise_for_status();boot=r.json();byid={int(p['id']):p for p in boot.get('elements',[])}
 rows=d.get('captain_comparison') or []
 for row in rows:
  pid=int(row.get('id') or -1);p=byid.get(pid)
  if not p:continue
  row['season_minutes']=float(p.get('minutes') or 0);row['season_points']=float(p.get('total_points') or 0);row['season_xg']=float(p.get('expected_goals') or 0);row['season_xa']=float(p.get('expected_assists') or 0);row['season_goals']=float(p.get('goals_scored') or 0);row['season_assists']=float(p.get('assists') or 0);row['selected_by_percent']=float(p.get('selected_by_percent') or 0)
  try:
   h=s.get(f'{BASE}/element-summary/{pid}/',timeout=18);h.raise_for_status();past=(h.json().get('history_past') or [])
   prev=past[-1] if past else {}
  except Exception:prev={}
  row['prev_season_name']=prev.get('season_name');row['prev_minutes']=float(prev.get('minutes') or 0);row['prev_points']=float(prev.get('total_points') or 0);row['prev_goals']=float(prev.get('goals_scored') or 0);row['prev_assists']=float(prev.get('assists') or 0)
 d['captain_comparison']=rows
 d['captain_v4_inputs']={'enriched':True,'source':'FPL bootstrap-static + element-summary history_past','candidate_count':len(rows),'fields':['season_minutes','season_points','season_xg','season_xa','season_goals','season_assists','prev_minutes','prev_points','prev_goals','prev_assists']}
 PATH.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');print('Enriched Captain v4 inputs for',len(rows),'candidates with previous-season priors')
if __name__=='__main__':main()

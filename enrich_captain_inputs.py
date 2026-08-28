"""Inject full-season captain inputs into data.json before Captain v4 shadow.

Keeps production xP logic unchanged. Uses current FPL bootstrap data to enrich
only captain candidates with long-run minutes, points, xG, xA and goals.
"""
import json,requests
from pathlib import Path
PATH=Path('data.json')

def main():
 d=json.loads(PATH.read_text(encoding='utf-8'))
 r=requests.get('https://fantasy.premierleague.com/api/bootstrap-static/',headers={'User-Agent':'fpl-autopilot-captain-v4-enrich'},timeout=18);r.raise_for_status();boot=r.json();byid={int(p['id']):p for p in boot.get('elements',[])}
 rows=d.get('captain_comparison') or []
 for row in rows:
  p=byid.get(int(row.get('id') or -1))
  if not p:continue
  row['season_minutes']=float(p.get('minutes') or 0)
  row['season_points']=float(p.get('total_points') or 0)
  row['season_xg']=float(p.get('expected_goals') or 0)
  row['season_xa']=float(p.get('expected_assists') or 0)
  row['season_goals']=float(p.get('goals_scored') or 0)
  row['season_assists']=float(p.get('assists') or 0)
  row['selected_by_percent']=float(p.get('selected_by_percent') or 0)
 d['captain_comparison']=rows
 d['captain_v4_inputs']={'enriched':True,'source':'FPL bootstrap-static','candidate_count':len(rows),'fields':['season_minutes','season_points','season_xg','season_xa','season_goals','season_assists']}
 PATH.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');print('Enriched Captain v4 inputs for',len(rows),'candidates')
if __name__=='__main__':main()

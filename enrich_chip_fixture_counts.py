from __future__ import annotations
"""Enrich chip shadow with exact FPL fixture counts by GW/team and squad exposure."""
import json,requests
from pathlib import Path
DATA=Path('data.json'); CHIP=Path('chip_strategy_shadow.json')
BASE='https://fantasy.premierleague.com/api'
def get(path):
 r=requests.get(f"{BASE}/{path.lstrip('/')}",headers={'Accept':'application/json','User-Agent':'fpl-autopilot-chip-fixture-counts'},timeout=18);r.raise_for_status();return r.json()
def main():
 if not DATA.exists() or not CHIP.exists():return
 d=json.loads(DATA.read_text()); c=json.loads(CHIP.read_text()); fixtures=get('fixtures/')
 gws=sorted({int(x.get('gw')) for x in d.get('future',[]) if x.get('gw') is not None} | {int(d.get('gw') or 0)})
 counts={gw:{} for gw in gws}
 for f in fixtures:
  gw=f.get('event')
  if gw not in counts:continue
  for tid in (int(f['team_h']),int(f['team_a'])):counts[gw][tid]=counts[gw].get(tid,0)+1
 squad=[]
 for k in ('lineup','bench'):
  for p in d.get(k,[]) or []:
   if p.get('id') is not None and p.get('team_id') is not None:squad.append({'id':int(p['id']),'team_id':int(p['team_id']),'name':p.get('name')})
 seen={}; squad=[seen.setdefault(p['id'],p) for p in squad if p['id'] not in seen]
 diagnostics=[]
 for gw in gws:
  team_counts=counts.get(gw,{})
  zero=[p for p in squad if int(team_counts.get(p['team_id'],0))==0]
  double=[p for p in squad if int(team_counts.get(p['team_id'],0))>=2]
  single=[p for p in squad if int(team_counts.get(p['team_id'],0))==1]
  diagnostics.append({'gw':gw,'squad_blank_count':len(zero),'squad_single_count':len(single),'squad_double_count':len(double),'blank_player_ids':[p['id'] for p in zero],'double_player_ids':[p['id'] for p in double],'team_fixture_counts':{str(k):v for k,v in sorted(team_counts.items())}})
 # Adjust FH/BB evidence conservatively; still shadow-only.
 if diagnostics:
  fh=max(diagnostics,key=lambda r:r['squad_blank_count']); bb=max(diagnostics,key=lambda r:r['squad_double_count'])
  c.setdefault('evidence',{})['exact_fixture_diagnostics']=diagnostics
  c['evidence']['exact_free_hit_candidate_gw']=fh['gw']
  c['evidence']['exact_free_hit_blank_players']=fh['squad_blank_count']
  c['evidence']['exact_bench_boost_candidate_gw']=bb['gw']
  c['evidence']['exact_bench_boost_double_players']=bb['squad_double_count']
  # Add only modest exact-fixture adjustments on top of v1.3 sequence scores.
  scores=c.setdefault('scores',{})
  scores['free_hit']=round(float(scores.get('free_hit',0))+max(0,fh['squad_blank_count']-3)*0.45,2)
  scores['bench_boost']=round(float(scores.get('bench_boost',0))+bb['squad_double_count']*0.22,2)
  c['fixture_count_model']={'version':'1.0-exact','source':'FPL fixtures API','gws':gws,'squad_players':len(squad)}
  c['version']='1.4-exact-fixtures'
 CHIP.write_text(json.dumps(c,ensure_ascii=False,indent=2));print('Enriched chip shadow with exact fixtures',[(x['gw'],x['squad_blank_count'],x['squad_double_count']) for x in diagnostics])
if __name__=='__main__':main()

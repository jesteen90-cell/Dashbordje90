"""Evaluate frozen v3/v4 captain picks against actual FPL points."""
import json,requests
from pathlib import Path
OUT=Path('backtest/captain_v4_scorecard.json')
def main():
 rows=[]
 for p in sorted(Path('captain_snapshots').glob('gw*.json')) if Path('captain_snapshots').exists() else []:
  d=json.loads(p.read_text());gw=int(d['gw'])
  live=requests.get(f'https://fantasy.premierleague.com/api/event/{gw}/live/',timeout=18).json()
  actual={int(x['id']):float((x.get('stats') or {}).get('total_points',0)) for x in live.get('elements',[])}
  a=d.get('v3_pick') or {};b=d.get('v4_pick') or {}
  if not a.get('id') or not b.get('id') or int(a['id']) not in actual or int(b['id']) not in actual:continue
  ap=actual[int(a['id'])];bp=actual[int(b['id'])]
  rows.append({'gw':gw,'v3':a['name'],'v4':b['name'],'v3_points':ap,'v4_points':bp,'delta':bp-ap})
 n=len(rows);delta=sum(x['delta'] for x in rows);wins=sum(x['delta']>0 for x in rows);loss=sum(x['delta']<0 for x in rows)
 # Conservative promotion: enough independent GWs and positive realized edge.
 promote=n>=8 and delta>=4 and wins>=loss
 OUT.parent.mkdir(exist_ok=True);OUT.write_text(json.dumps({'version':'1.0','evaluated_gws':n,'v4_delta_points':delta,'v4_wins':wins,'v4_losses':loss,'promote':promote,'rows':rows},ensure_ascii=False,indent=2));print('Captain v4 scorecard',n,delta,'promote=',promote)
if __name__=='__main__':main()

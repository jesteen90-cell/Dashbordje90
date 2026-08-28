"""Evaluate frozen v3/v4/v4.1 captain picks against actual FPL points."""
import json,requests
from pathlib import Path
OUT=Path('backtest/captain_v4_scorecard.json')
def main():
 rows=[]
 for p in sorted(Path('captain_snapshots').glob('gw*.json')) if Path('captain_snapshots').exists() else []:
  d=json.loads(p.read_text());gw=int(d['gw'])
  live=requests.get(f'https://fantasy.premierleague.com/api/event/{gw}/live/',timeout=18).json()
  actual={int(x['id']):float((x.get('stats') or {}).get('total_points',0)) for x in live.get('elements',[])}
  a=d.get('v3_pick') or {};b=d.get('v4_pick') or {};c=d.get('v41_pick') or d.get('v4_1_pick') or {}
  if not a.get('id') or not b.get('id') or int(a['id']) not in actual or int(b['id']) not in actual:continue
  ap=actual[int(a['id'])];bp=actual[int(b['id'])]
  cp=actual.get(int(c['id'])) if c.get('id') else None
  cand=d.get('candidates') or []
  eligible=[actual.get(int(x['id'])) for x in cand if x.get('id') and int(x['id']) in actual]
  best_actual=max(eligible) if eligible else max(ap,bp,cp if cp is not None else -1)
  row={'gw':gw,'v3':a.get('name'),'v4':b.get('name'),'v3_points':ap,'v4_points':bp,'v4_delta':bp-ap,'v3_regret':best_actual-ap,'v4_regret':best_actual-bp,'best_actual_candidate_points':best_actual}
  if cp is not None:
   row.update({'v41':c.get('name'),'v41_points':cp,'v41_delta_vs_v3':cp-ap,'v41_delta_vs_v4':cp-bp,'v41_regret':best_actual-cp})
  rows.append(row)
 n=len(rows);rows41=[x for x in rows if 'v41_points' in x]
 delta4=sum(x['v4_delta'] for x in rows);wins4=sum(x['v4_delta']>0 for x in rows);loss4=sum(x['v4_delta']<0 for x in rows)
 n41=len(rows41);d41v3=sum(x['v41_delta_vs_v3'] for x in rows41);d41v4=sum(x['v41_delta_vs_v4'] for x in rows41);w41=sum(x['v41_delta_vs_v4']>0 for x in rows41);l41=sum(x['v41_delta_vs_v4']<0 for x in rows41)
 regret3=sum(x['v3_regret'] for x in rows)/n if n else 0;regret4=sum(x['v4_regret'] for x in rows)/n if n else 0;regret41=sum(x['v41_regret'] for x in rows41)/n41 if n41 else None
 promote4=n>=8 and delta4>=4 and wins4>=loss4
 # v4.1 promotion is stricter: enough GWs, positive edge vs both baselines and lower mean regret than v4.
 promote41=n41>=8 and d41v4>=4 and d41v3>=4 and w41>=l41 and regret41 is not None and regret41<=regret4-.15
 payload={'version':'1.1-haul-regret','evaluated_gws':n,'v4_delta_points':delta4,'v4_wins':wins4,'v4_losses':loss4,'v4_mean_regret':round(regret4,3),'v3_mean_regret':round(regret3,3),'v4_promote':promote4,'v41_evaluated_gws':n41,'v41_delta_vs_v3':d41v3,'v41_delta_vs_v4':d41v4,'v41_wins_vs_v4':w41,'v41_losses_vs_v4':l41,'v41_mean_regret':round(regret41,3) if regret41 is not None else None,'v41_promote':promote41,'rows':rows}
 OUT.parent.mkdir(exist_ok=True);OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2));print('Captain scorecard',n,'v4',delta4,'v4.1',n41,d41v4,'promote41=',promote41)
if __name__=='__main__':main()

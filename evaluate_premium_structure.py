"""Evaluate frozen premium squad structures over their original GW horizon."""
import json,requests
from pathlib import Path
ROOT=Path('premium_structure_snapshots');OUT=Path('backtest/premium_structure_scorecard.json')
def get(gw):
 r=requests.get(f'https://fantasy.premierleague.com/api/event/{gw}/live/',timeout=18);r.raise_for_status();return {int(x['id']):float((x.get('stats') or {}).get('total_points',0)) for x in r.json().get('elements',[])}
def actual_structure(s,actual_by_gw,weights):
 total=0.0;rows=[]
 for c in s.get('captains') or []:
  gw=int(c['gw']);act=actual_by_gw.get(gw)
  if not act:return None
  xi=[int(x) for x in c.get('xi_ids') or []];cap=c.get('captain_id')
  if not xi or cap is None:return None
  raw=sum(act.get(pid,0) for pid in xi);val=raw+act.get(int(cap),0);w=float(weights.get(str(gw),1));total+=val*w;rows.append({'gw':gw,'actual_weighted_value':round(val*w,3),'captain_points':act.get(int(cap),0)})
 return round(total,3),rows
def current_scenario(d):return {'structure':'current_structure','squad_ids':d.get('current_squad_ids'),'captains':d.get('current_captains')}
def main():
 rows=[];wins={'current_structure':0,'premium_forward':0,'premium_midfielder':0};regret=[]
 for p in sorted(ROOT.glob('gw*.json')) if ROOT.exists() else []:
  d=json.loads(p.read_text());gws=[int(x) for x in d.get('gws') or []]
  if not gws:continue
  actual={}
  try:
   for gw in gws:actual[gw]=get(gw)
  except Exception:continue
  weights=d.get('weights') or {};opts=[current_scenario(d)]
  if d.get('best_premium_forward'):opts.append(d['best_premium_forward'])
  if d.get('best_premium_midfielder'):opts.append(d['best_premium_midfielder'])
  scored=[]
  for s in opts:
   res=actual_structure(s,actual,weights)
   if res:scored.append((s.get('structure'),res[0]))
  if len(scored)<2:continue
  best=max(scored,key=lambda x:x[1]);chosen=d.get('verdict','current_structure');chosen_val=next((v for k,v in scored if k==chosen),None)
  if chosen_val is None:continue
  wins[best[0]]=wins.get(best[0],0)+1;reg=best[1]-chosen_val;regret.append(reg);rows.append({'start_gw':int(d['gw']),'verdict':chosen,'actual_scores':dict(scored),'actual_best':best[0],'regret':round(reg,3)})
 n=len(rows);OUT.parent.mkdir(exist_ok=True);payload={'version':'1.0','evaluated_windows':n,'winner_counts':wins,'verdict_accuracy':(sum(r['verdict']==r['actual_best'] for r in rows)/n if n else None),'mean_regret':(sum(regret)/len(regret) if regret else None),'rows':rows};OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2));print('Premium structure scorecard',n,wins)
if __name__=='__main__':main()

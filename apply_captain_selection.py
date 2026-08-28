from __future__ import annotations
"""Apply the promoted captain model to dashboard C/V flags with safety gates and expose explanation metadata."""
import json
from pathlib import Path
DATA=Path('data.json'); SHADOW=Path('captain_v4_shadow.json')

def n(v,d=0.0):
 try:return float(v)
 except:return d

def main():
 d=json.loads(DATA.read_text())
 shadow=json.loads(SHADOW.read_text()) if SHADOW.exists() else {}
 sel=d.get('captain_model_selection') or {}
 model=sel.get('production_model','v3')
 key={'v3':'v3_score','v4':'v4_score','v4.1':'v41_score'}.get(model,'v3_score')
 selected=sel.get('selected_pick') or {}
 cap_id=int(selected.get('id') or 0)
 lineup=d.get('lineup') or []
 byid={int(p.get('id')):p for p in lineup if p.get('id') is not None}
 cand=byid.get(cap_id)
 safe=bool(cand) and n(cand.get('availability'),1)>=0.75 and n(cand.get('expected_minutes'))>=60
 if not safe:
  old=next((p for p in lineup if p.get('captain')),None)
  if old: cap_id=int(old['id'])
 ranked=sorted(shadow.get('candidates') or [],key=lambda x:n(x.get(key)),reverse=True)
 vice_id=0
 for r in ranked:
  rid=int(r.get('id') or 0); p=byid.get(rid)
  if rid!=cap_id and p and n(p.get('availability'),1)>=0.75 and n(p.get('expected_minutes'))>=55:
   vice_id=rid;break
 if not vice_id:
  oldv=next((p for p in lineup if p.get('vice') and int(p.get('id') or 0)!=cap_id),None)
  if oldv:vice_id=int(oldv['id'])
 def apply(rows):
  for p in rows or []:
   pid=int(p.get('id') or 0);p['captain']=pid==cap_id;p['vice']=pid==vice_id
 apply(d.get('lineup'))
 cmp=d.get('comparison') or {}
 apply(cmp.get('current_xi'));apply(cmp.get('transfer_xi'))
 cap_shadow=next((r for r in ranked if int(r.get('id') or 0)==cap_id),{})
 runner=next((r for r in ranked if int(r.get('id') or 0)!=cap_id and int(r.get('id') or 0) in byid),{})
 cap_row=byid.get(cap_id) or {}
 runner_row=byid.get(int(runner.get('id') or 0)) or {}
 hp=cap_shadow.get('haul_probabilities') or {};rhp=runner.get('haul_probabilities') or {}
 d['captain_explanation']={'version':'1.0','model':model,'captain':{'id':cap_id,'name':cap_row.get('name'),'team':cap_row.get('team'),'xp':round(n(cap_row.get('xp')),2),'expected_minutes':round(n(cap_row.get('expected_minutes')),1),'availability':round(n(cap_row.get('availability'),1),3),'model_score':round(n(cap_shadow.get(key)),3),'p10_plus':hp.get('p10'),'p15_plus':hp.get('p15'),'p_goal_2plus':hp.get('p_goal_2'),'p_multi_return':hp.get('p_multi_return')},'runner_up':{'id':runner.get('id'),'name':runner.get('name'),'team':runner.get('team'),'xp':round(n(runner_row.get('xp')),2),'expected_minutes':round(n(runner_row.get('expected_minutes')),1),'model_score':round(n(runner.get(key)),3),'p10_plus':rhp.get('p10'),'p15_plus':rhp.get('p15'),'p_goal_2plus':rhp.get('p_goal_2'),'p_multi_return':rhp.get('p_multi_return')},'score_gap':round(n(cap_shadow.get(key))-n(runner.get(key)),3) if runner else None,'xp_gap':round(n(cap_row.get('xp'))-n(runner_row.get('xp')),2) if runner else None,'selected_pick_safe':safe,'reason':sel.get('reason')}
 d['captain_model_selection']['applied']=True
 d['captain_model_selection']['applied_captain_id']=cap_id
 d['captain_model_selection']['applied_captain_name']=cap_row.get('name')
 d['captain_model_selection']['applied_vice_id']=vice_id
 d['captain_model_selection']['safety_gate']={'captain_min_minutes':60,'captain_min_availability':0.75,'vice_min_minutes':55,'vice_min_availability':0.75,'selected_pick_safe':safe}
 # Compatibility metadata: transfer_optimizer_v2 actively uses captain_horizon_v1 in candidate pruning.
 d.setdefault('optimizer',{})['captain_horizon_search']=True
 dl=d.get('decision_layer') or {}
 if dl.get('version')=='4.5-squad-consistent':
  dl['engine_version']='4.5-squad-consistent'
  dl['version']='4.4-premium-adaptive'
  dl['squad_view_consistent']=True
  d['decision_layer']=dl
 DATA.write_text(json.dumps(d,ensure_ascii=False,indent=2))
 print('Applied captain:',cap_row.get('name'),'model=',model,'safe=',safe,'runner=',runner.get('name'))
if __name__=='__main__':main()

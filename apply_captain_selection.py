from __future__ import annotations
"""Apply the promoted captain model to dashboard C/V flags with safety gates and expose explanation metadata."""
import json
from pathlib import Path
DATA=Path('data.json'); SHADOW=Path('captain_v4_shadow.json')
def n(v,d=0.0):
 try:return float(v)
 except:return d
def main():
 d=json.loads(DATA.read_text());shadow=json.loads(SHADOW.read_text()) if SHADOW.exists() else {};sel=d.get('captain_model_selection') or {};model=sel.get('production_model','v3');key={'v3':'v3_score','v4':'v4_score','v4.1':'v41_score'}.get(model,'v3_score');selected=sel.get('selected_pick') or {};cap_id=int(selected.get('id') or 0);lineup=d.get('lineup') or [];byid={int(p.get('id')):p for p in lineup if p.get('id') is not None};cand=byid.get(cap_id);safe=bool(cand) and n(cand.get('availability'),1)>=0.75 and n(cand.get('expected_minutes'))>=60
 if not safe:
  old=next((p for p in lineup if p.get('captain')),None)
  if old:cap_id=int(old['id'])
 ranked=sorted(shadow.get('candidates') or [],key=lambda x:n(x.get(key)),reverse=True);vice_id=0
 for r in ranked:
  rid=int(r.get('id') or 0);p=byid.get(rid)
  if rid!=cap_id and p and n(p.get('availability'),1)>=0.75 and n(p.get('expected_minutes'))>=55:vice_id=rid;break
 if not vice_id:
  oldv=next((p for p in lineup if p.get('vice') and int(p.get('id') or 0)!=cap_id),None)
  if oldv:vice_id=int(oldv['id'])
 def apply(rows):
  for p in rows or []:
   pid=int(p.get('id') or 0);p['captain']=pid==cap_id;p['vice']=pid==vice_id
 apply(d.get('lineup'));cmp=d.get('comparison') or {};apply(cmp.get('current_xi'));apply(cmp.get('transfer_xi'))
 cap_shadow=next((r for r in ranked if int(r.get('id') or 0)==cap_id),{});runner=next((r for r in ranked if int(r.get('id') or 0)!=cap_id and int(r.get('id') or 0) in byid),{});cap_row=byid.get(cap_id) or {};runner_row=byid.get(int(runner.get('id') or 0)) or {};hp=cap_shadow.get('haul_probabilities') or {};rhp=runner.get('haul_probabilities') or {};score_gap=round(n(cap_shadow.get(key))-n(runner.get(key)),3) if runner else None;xp_gap=round(n(cap_row.get('xp'))-n(runner_row.get('xp')),2) if runner else None;haul_gap=round(n(hp.get('p10'))-n(rhp.get('p10')),4) if runner and hp.get('p10') is not None and rhp.get('p10') is not None else None
 strengths=list((d.get('team_strength') or {}).values());sources={str(x.get('prior_source') or '') for x in strengths};market_active=bool((d.get('market_ensemble') or {}).get('active'))
 if 'fpl-bootstrap' in sources:team_quality=1.0;team_source='fpl-bootstrap'
 elif 'table-shrunk' in sources:team_quality=.45;team_source='table-shrunk'
 else:team_quality=0.0;team_source='neutral-fallback'
 quality_score=team_quality+(1.0 if market_active else 0.0);input_quality='HIGH' if quality_score>=1.5 else 'MEDIUM' if quality_score>=.4 else 'LOW'
 conf_raw=0.0
 if score_gap is not None:conf_raw+=max(-1,min(1,score_gap/.45))*1.6
 if xp_gap is not None:conf_raw+=max(-1,min(1,xp_gap/1.2))*1.1
 if haul_gap is not None:conf_raw+=max(-1,min(1,haul_gap/.12))*1.0
 cm=n(cap_row.get('expected_minutes'));ca=n(cap_row.get('availability'),1);conf_raw+=(1 if cm>=82 else .55 if cm>=72 else .15 if cm>=60 else -1);conf_raw+=(.8 if ca>=.95 else .45 if ca>=.85 else .1 if ca>=.75 else -1)
 if not safe:conf_raw-=2
 conf_raw-=max(0,2-quality_score)*.325
 conf_score=round(max(0,min(100,50+conf_raw*12)));conf_level='HØY' if conf_raw>=3.2 else 'MIDDELS' if conf_raw>=1.5 else 'LAV'
 d['captain_explanation']={'version':'1.3-confidence-source-quality','model':model,'captain':{'id':cap_id,'name':cap_row.get('name'),'team':cap_row.get('team'),'xp':round(n(cap_row.get('xp')),2),'expected_minutes':round(cm,1),'availability':round(ca,3),'model_score':round(n(cap_shadow.get(key)),3),'p10_plus':hp.get('p10'),'p15_plus':hp.get('p15'),'p_goal_2plus':hp.get('p_goal_2'),'p_multi_return':hp.get('p_multi_return')},'runner_up':{'id':runner.get('id'),'name':runner.get('name'),'team':runner.get('team'),'xp':round(n(runner_row.get('xp')),2),'expected_minutes':round(n(runner_row.get('expected_minutes')),1),'availability':round(n(runner_row.get('availability'),1),3),'model_score':round(n(runner.get(key)),3),'p10_plus':rhp.get('p10'),'p15_plus':rhp.get('p15'),'p_goal_2plus':rhp.get('p_goal_2'),'p_multi_return':rhp.get('p_multi_return')},'score_gap':score_gap,'xp_gap':xp_gap,'haul10_gap':haul_gap,'confidence':{'score':conf_score,'level':conf_level,'raw':round(conf_raw,3),'input_quality':input_quality},'input_quality':{'team_source':team_source,'team_quality':team_quality,'market_active':market_active,'quality_score':round(quality_score,2),'level':input_quality},'selected_pick_safe':safe,'reason':sel.get('reason')}
 d['captain_model_selection']['applied']=True;d['captain_model_selection']['applied_captain_id']=cap_id;d['captain_model_selection']['applied_captain_name']=cap_row.get('name');d['captain_model_selection']['applied_vice_id']=vice_id;d['captain_model_selection']['safety_gate']={'captain_min_minutes':60,'captain_min_availability':0.75,'vice_min_minutes':55,'vice_min_availability':0.75,'selected_pick_safe':safe}
 display=[]
 for r in ranked:
  pid=int(r.get('id') or 0);p=byid.get(pid)
  if not p:continue
  hp2=r.get('haul_probabilities') or {};display.append({'id':pid,'name':p.get('name'),'team':p.get('team'),'position':p.get('position'),'xp':round(n(p.get('xp')),2),'ceiling':round(n(p.get('xp_high'),p.get('xp')),2),'expected_minutes':round(n(p.get('expected_minutes')),0),'availability':round(n(p.get('availability'),1),2),'score':round(n(r.get(key)),3),'p10_plus':hp2.get('p10'),'p15_plus':hp2.get('p15'),'p_goal_2plus':hp2.get('p_goal_2'),'p_multi_return':hp2.get('p_multi_return'),'captain':pid==cap_id,'vice':pid==vice_id})
  if len(display)>=5:break
 if cap_id and all(int(x.get('id') or 0)!=cap_id for x in display) and cap_row:display[-1:] = [{'id':cap_id,'name':cap_row.get('name'),'team':cap_row.get('team'),'position':cap_row.get('position'),'xp':round(n(cap_row.get('xp')),2),'ceiling':round(n(cap_row.get('xp_high'),cap_row.get('xp')),2),'expected_minutes':round(cm,0),'availability':round(ca,2),'score':round(n(cap_shadow.get(key)),3),'p10_plus':hp.get('p10'),'p15_plus':hp.get('p15'),'p_goal_2plus':hp.get('p_goal_2'),'p_multi_return':hp.get('p_multi_return'),'captain':True,'vice':False}]
 d['captain_comparison']=display
 if isinstance(d.get('captain_pool'),dict):d['captain_pool']['display_count']=len(display)
 d.setdefault('optimizer',{})['captain_horizon_search']=True;dl=d.get('decision_layer') or {};dl['squad_view_consistent']=bool(dl.get('squad_view_consistent',True));d['decision_layer']=dl;DATA.write_text(json.dumps(d,ensure_ascii=False,indent=2));print('Applied captain:',cap_row.get('name'),'model=',model,'safe=',safe,'confidence=',conf_level,conf_score,'quality=',input_quality,team_source,'runner=',runner.get('name'),'pool=',len(ranked),'display=',len(display))
if __name__=='__main__':main()

from __future__ import annotations
"""Apply the promoted captain model to dashboard C/V flags with safety gates."""
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
 # Safety gate: captain must actually start, be broadly available, and project meaningful minutes.
 cand=byid.get(cap_id)
 safe=bool(cand) and n(cand.get('availability'),1)>=0.75 and n(cand.get('expected_minutes'))>=60
 if not safe:
  old=next((p for p in lineup if p.get('captain')),None)
  if old: cap_id=int(old['id'])
 # Vice: highest-ranked safe remaining captain candidate under selected production model.
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
 for k in ('lineup',):apply(d.get(k))
 cmp=d.get('comparison') or {}
 apply(cmp.get('current_xi'));apply(cmp.get('transfer_xi'))
 # Expose actual applied choice for UI/debugging.
 d['captain_model_selection']['applied']=True
 d['captain_model_selection']['applied_captain_id']=cap_id
 d['captain_model_selection']['applied_captain_name']=(byid.get(cap_id) or {}).get('name')
 d['captain_model_selection']['applied_vice_id']=vice_id
 d['captain_model_selection']['safety_gate']={'captain_min_minutes':60,'captain_min_availability':0.75,'vice_min_minutes':55,'vice_min_availability':0.75,'selected_pick_safe':safe}
 DATA.write_text(json.dumps(d,ensure_ascii=False,indent=2))
 print('Applied captain:',d['captain_model_selection']['applied_captain_name'],'model=',model,'safe=',safe,'vice=',vice_id)
if __name__=='__main__':main()

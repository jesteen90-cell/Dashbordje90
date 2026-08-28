"""Post Transfer State v1.
Turns the dashboard from transfer-decision mode into lineup-decision mode once the
current GW free transfer has been used. Does not invent FPL writes; it derives state
from current_squad plus the configured free-transfer allowance.
"""
import json
from pathlib import Path
P=Path('data.json')
d=json.loads(P.read_text(encoding='utf-8'))
cs=d.get('current_squad') or {}
completed=int(cs.get('transfer_count_current_gw') or 0)
ft_before=int(d.get('free_transfers_assumed') or 1)
remaining=max(0,ft_before-completed)
extra=max(0,completed-ft_before)
rows={int(p['id']):p for p in (cs.get('players') or []) if p.get('id') is not None}
# Names for IN players come from current squad. OUT may only exist in historic/candidate rows.
all_old={int(p['id']):p for p in ((d.get('confirmed_fpl') or {}).get('lineup') or [])+((d.get('confirmed_fpl') or {}).get('bench') or []) if p.get('id') is not None}
moves=[]
for t in cs.get('transfers_applied') or []:
    oid=int(t.get('out_id') or 0); iid=int(t.get('in_id') or 0)
    moves.append({'out_id':oid,'out_name':(all_old.get(oid) or {}).get('name',str(oid)),'in_id':iid,'in_name':(rows.get(iid) or {}).get('name',str(iid)),'source':t.get('source')})
post=completed>0 and remaining==0
d['current_transfer_state']={
  'version':'1.0','gw':int(d.get('gw') or 0),'completed_transfers':completed,'free_transfers_before':ft_before,
  'free_transfers_remaining':remaining,'additional_transfers_already_used':extra,'next_extra_transfer_cost_points':4 if remaining==0 else 0,
  'post_transfer_mode':post,'moves':moves,'predeadline_override_active':bool(cs.get('predeadline_override_active')),
  'status':'TRANSFER COMPLETE – LINEUP MODE' if post else 'TRANSFER DECISION MODE',
  'note':'Når FT er brukt flyttes hovedfokus til optimal XI, kaptein og benk. Nye transfers må vurderes separat med hit-kostnad.' if post else 'Gratisbytte er fortsatt tilgjengelig.'
}
P.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
print('Post-transfer state',d['current_transfer_state'])

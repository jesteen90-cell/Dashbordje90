"""Round-specific transfer state.
Current squad may include transfers from earlier GWs, but post-transfer mode only
activates when a transfer has actually been made for the current target GW.
"""
import json
from pathlib import Path
P=Path('data.json');d=json.loads(P.read_text(encoding='utf-8'));cs=d.get('current_squad') or {};gw=int(d.get('gw') or 0)
all_applied=cs.get('transfers_applied') or [];current=[t for t in all_applied if int(t.get('event') or 0)==gw];completed=len(current);ft_before=int(d.get('free_transfers_assumed') or 1);remaining=max(0,ft_before-completed);extra=max(0,completed-ft_before)
rows={int(p['id']):p for p in (cs.get('players') or []) if p.get('id') is not None};all_old={int(p['id']):p for p in ((d.get('confirmed_fpl') or {}).get('lineup') or [])+((d.get('confirmed_fpl') or {}).get('bench') or []) if p.get('id') is not None};moves=[]
for t in current:
 oid=int(t.get('out_id') or 0);iid=int(t.get('in_id') or 0);moves.append({'out_id':oid,'out_name':(all_old.get(oid) or {}).get('name',str(oid)),'in_id':iid,'in_name':(rows.get(iid) or {}).get('name',str(iid)),'source':t.get('source')})
post=completed>0 and remaining==0
d['current_transfer_state']={'version':'1.1-round-specific','gw':gw,'completed_transfers':completed,'free_transfers_before':ft_before,'free_transfers_remaining':remaining,'additional_transfers_already_used':extra,'next_extra_transfer_cost_points':4 if remaining==0 else 0,'post_transfer_mode':post,'moves':moves,'status':'TRANSFER COMPLETE – LINEUP MODE' if post else 'TRANSFER DECISION MODE','note':'Bare transfers i gjeldende target-GW avgjør post-transfer-modus. Tidligere GW-transfers brukes kun til å rekonstruere troppen.'}
P.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');print('Post-transfer state',d['current_transfer_state'])

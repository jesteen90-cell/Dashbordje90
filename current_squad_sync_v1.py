"""Current Squad Sync v1.
Reconstructs the squad owned right now by starting from the latest confirmed FPL
15-man squad and applying official transfers for the current GW.
This fixes the pre-deadline gap where event/{last_finished_gw}/picks is necessarily stale.
"""
from __future__ import annotations
import json, os
from pathlib import Path
import requests

BASE='https://fantasy.premierleague.com/api'
P=Path('data.json')
TEAM_ID=int(os.environ['FPL_TEAM_ID'])
POS={1:'GK',2:'DEF',3:'MID',4:'FWD'}

def get(path):
    r=requests.get(f"{BASE}/{path.lstrip('/')}",headers={'Accept':'application/json','User-Agent':'fpl-autopilot-current-squad/1.0'},timeout=18)
    r.raise_for_status();return r.json()

def main():
    d=json.loads(P.read_text(encoding='utf-8')); gw=int(d.get('gw') or 0)
    confirmed=d.get('confirmed_fpl') or {}; base=(confirmed.get('lineup') or [])+(confirmed.get('bench') or [])
    if len(base)!=15: raise RuntimeError(f'Need 15-player confirmed base squad, got {len(base)}')
    cache=json.loads(Path('projection_cache.json').read_text(encoding='utf-8'))
    cache_by={int(x['id']):x for x in cache.get('players') or []}; gkey=str(gw)
    boot=get('bootstrap-static/'); boot_by={int(x['id']):x for x in boot.get('elements') or []}; team_names={int(t['id']):t.get('name','') for t in boot.get('teams') or []}
    fixtures=get(f'fixtures/?event={gw}') if gw else []
    fixture_by={}
    for f in fixtures or []:
        h=int(f.get('team_h') or 0); a=int(f.get('team_a') or 0)
        if h: fixture_by[h]=f"{team_names.get(a,'?')[:3].upper()} (H)"
        if a: fixture_by[a]=f"{team_names.get(h,'?')[:3].upper()} (A)"

    owned={int(x['id']):dict(x) for x in base}
    transfers=get(f'entry/{TEAM_ID}/transfers/')
    current=[t for t in transfers or [] if int(t.get('event') or 0)==gw]
    current.sort(key=lambda t:str(t.get('time') or ''))
    applied=[]
    for t in current:
        out_id=int(t.get('element_out') or 0); in_id=int(t.get('element_in') or 0)
        if out_id in owned: owned.pop(out_id)
        bp=boot_by.get(in_id) or {}; cp=cache_by.get(in_id) or {}; tid=int(bp.get('team') or cp.get('team') or 0)
        chance=bp.get('chance_of_playing_next_round'); avail=(float(chance)/100.0) if chance is not None else 1.0
        owned[in_id]={
            'id':in_id,'name':bp.get('web_name') or cp.get('name') or str(in_id),'team_id':tid,'team':team_names.get(tid,'Ukjent lag'),
            'position':POS.get(int(bp.get('element_type') or cp.get('element_type') or 0),''),'price':round(float(bp.get('now_cost') or cp.get('now_cost') or 0)/10,1),
            'xp':round(float((cp.get('xp') or {}).get(gkey,0)),2),'fixture':fixture_by.get(tid,''),'availability':round(avail,2),
            'news':bp.get('news') or '','current_transfer_addition':True
        }
        applied.append({'out_id':out_id,'in_id':in_id,'time':t.get('time'),'event':gw})
    if len(owned)!=15: raise RuntimeError(f'Current squad reconstruction produced {len(owned)} players, expected 15')

    # Refresh xP/team/price metadata for every owned player from the current projection surface.
    rows=[]
    for pid,row in owned.items():
        bp=boot_by.get(pid) or {}; cp=cache_by.get(pid) or {}; tid=int(bp.get('team') or row.get('team_id') or cp.get('team') or 0)
        row=dict(row); row['team_id']=tid; row['team']=team_names.get(tid) or row.get('team') or 'Ukjent lag'; row['position']=POS.get(int(bp.get('element_type') or cp.get('element_type') or 0),row.get('position') or '')
        if cp: row['xp']=round(float((cp.get('xp') or {}).get(gkey,0)),2)
        if bp.get('now_cost') is not None: row['price']=round(float(bp['now_cost'])/10,1)
        row['fixture']=fixture_by.get(tid,row.get('fixture') or '')
        chance=bp.get('chance_of_playing_next_round'); row['availability']=round((float(chance)/100.0) if chance is not None else float(row.get('availability',1)),2)
        row['news']=bp.get('news') or row.get('news') or ''
        rows.append(row)
    rows.sort(key=lambda x:( {'GK':1,'DEF':2,'MID':3,'FWD':4}.get(x.get('position'),9), -float(x.get('xp') or 0), x.get('name','') ))
    d['current_squad']={'version':'1.0-official-transfers','gw':gw,'source':'confirmed-last-finished-gw + official-transfer-history','base_confirmed_gw':confirmed.get('gw'),'transfer_count_current_gw':len(applied),'transfers_applied':applied,'players':rows,'owned_ids':sorted(owned)}
    P.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Current squad synced GW',gw,'transfers',len(applied),'players',[x['name'] for x in rows])

if __name__=='__main__': main()

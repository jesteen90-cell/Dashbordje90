from __future__ import annotations
import json, os
from pathlib import Path
import requests

BASE='https://fantasy.premierleague.com/api'
PATH=Path('data.json')
TEAM_ID=int(os.environ['FPL_TEAM_ID'])


def get(path):
    r=requests.get(f"{BASE}/{path.lstrip('/')}",headers={'Accept':'application/json','User-Agent':'fpl-autopilot-confirmed-lineup/1.0'},timeout=18)
    r.raise_for_status();return r.json()


def main():
    data=json.loads(PATH.read_text(encoding='utf-8'))
    gw=int(data.get('source_snapshot_gw') or 0)
    if gw<=0: raise RuntimeError('Missing source_snapshot_gw')
    snap=get(f'entry/{TEAM_ID}/event/{gw}/picks/')
    picks=sorted(snap.get('picks') or [],key=lambda x:int(x.get('position') or 99))
    if len(picks)!=15: raise RuntimeError(f'Expected 15 confirmed picks, got {len(picks)}')
    # Use rows already enriched with current xP/fixture/news data. The FPL API is
    # authoritative only for which 11 started, bench order, captain and vice.
    rows={int(p['id']):dict(p) for p in (data.get('lineup') or [])+(data.get('bench') or []) if p.get('id') is not None}
    for side in ('current_xi','transfer_xi'):
        for p in ((data.get('comparison') or {}).get(side) or []):
            if p.get('id') is not None: rows.setdefault(int(p['id']),dict(p))
    confirmed=[]
    for pick in picks:
        pid=int(pick['element'])
        if pid not in rows: raise RuntimeError(f'Confirmed FPL player {pid} missing from dashboard squad rows')
        p=dict(rows[pid]);p['captain']=bool(pick.get('is_captain'));p['vice']=bool(pick.get('is_vice_captain'));p['confirmed_position']=int(pick['position']);p['confirmed_multiplier']=int(pick.get('multiplier') or 0)
        confirmed.append(p)
    xi=confirmed[:11];bench=confirmed[11:]
    if len([p for p in xi if p.get('captain')])!=1 or len([p for p in xi if p.get('vice')])!=1: raise RuntimeError('Confirmed captain/vice invalid')
    data.setdefault('comparison',{})['current_xi']=xi
    data['confirmed_fpl']={'gw':gw,'source':'official-picks-api','exact_order':True,'lineup':xi,'bench':bench,'captain_id':next(p['id'] for p in xi if p.get('captain')),'vice_id':next(p['id'] for p in xi if p.get('vice'))}
    PATH.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Applied exact confirmed FPL GW',gw,'XI=',[p['name'] for p in xi],'bench=',[p['name'] for p in bench])

if __name__=='__main__': main()

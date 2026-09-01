from __future__ import annotations
import json, os, runpy
from pathlib import Path
import requests

BASE='https://fantasy.premierleague.com/api'
PATH=Path('data.json')
TEAM_ID=int(os.environ['FPL_TEAM_ID'])
POS={1:'GK',2:'DEF',3:'MID',4:'FWD'}


def get(path):
    r=requests.get(f"{BASE}/{path.lstrip('/')}",headers={'Accept':'application/json','User-Agent':'fpl-autopilot-confirmed-lineup/1.6'},timeout=18)
    r.raise_for_status();return r.json()


def fallback_row(pid, bootstrap, team_names):
    p=bootstrap.get(pid)
    if not p: raise RuntimeError(f'Confirmed FPL player {pid} missing from bootstrap')
    team_id=int(p['team'])
    return {'id':pid,'name':p.get('web_name') or str(pid),'team_id':team_id,'team':team_names.get(team_id,'Ukjent lag'),'position':POS.get(int(p.get('element_type') or 0),''),'price':round(float(p.get('now_cost') or 0)/10,1),'xp':0,'xp_low':0,'xp_high':0,'risk':'ukjent','volatility':0,'fixture':'','fixture_outlook':[],'availability':1,'expected_minutes':0,'news':p.get('news') or '','confirmed_row_fallback':True}


def apply_automatic_subs(picks, automatic_subs):
    out=[dict(p) for p in picks];byid={int(p['element']):p for p in out};applied=[]
    for sub in automatic_subs or []:
        iid=int(sub.get('element_in') or 0);oid=int(sub.get('element_out') or 0)
        if iid not in byid or oid not in byid: continue
        pin,pout=byid[iid],byid[oid];pin['position'],pout['position']=pout['position'],pin['position']
        if int(pin.get('multiplier') or 0)==0: pin['multiplier']=1
        pout['multiplier']=0;applied.append({'element_in':iid,'element_out':oid})
    return sorted(out,key=lambda x:int(x.get('position') or 99)),applied


def norm(s): return str(s or '').strip().casefold().replace(' ','')
def resolve_name(name, bootstrap, preferred_ids=None):
    target=norm(name);matches=[]
    for pid,p in bootstrap.items():
        vals={norm(p.get('web_name')),norm(p.get('first_name')),norm(p.get('second_name')),norm((str(p.get('first_name') or '')+' '+str(p.get('second_name') or '')).strip())}
        if target in vals: matches.append(pid)
    if len(matches)==1:return matches[0]
    preferred=set(int(x) for x in (preferred_ids or []));pm=[pid for pid in matches if pid in preferred]
    if len(pm)==1:return pm[0]
    raise RuntimeError(f'Could not uniquely resolve lineup player {name!r}: matches={matches}, preferred={pm}')


def apply_manual_snapshot_if_newer(data, bootstrap, team_names, rows, official_gw):
    pth=Path('manual_confirmed_lineup_gw2.json')
    if not pth.exists(): return data, official_gw, False
    ov=json.loads(pth.read_text(encoding='utf-8'));mgw=int(ov.get('gw') or 0)
    if not ov.get('confirmed_by_user') or mgw<=official_gw: return data, official_gw, False
    names=list(ov.get('lineup') or [])+list(ov.get('bench') or [])
    if len(names)!=15: raise RuntimeError('Manual confirmed lineup must contain 15 players')
    preferred=set(rows)
    ids=[]
    for n in names:
        pid=resolve_name(n,bootstrap,preferred)
        ids.append(pid);preferred.add(pid)
    if len(set(ids))!=15:raise RuntimeError('Manual confirmed lineup resolved duplicate player IDs')
    for pid in ids: rows.setdefault(pid,fallback_row(pid,bootstrap,team_names))
    cap=resolve_name(ov.get('captain'),bootstrap,set(ids));vice=resolve_name(ov.get('vice_captain'),bootstrap,set(ids))
    confirmed=[]
    for i,pid in enumerate(ids,1):
        r=dict(rows[pid]);bp=bootstrap.get(pid) or {};tid=int(r.get('team_id') or bp.get('team') or 0);r['team_id']=tid;r['team']=team_names.get(tid) or r.get('team') or 'Ukjent lag';r['captain']=pid==cap;r['vice']=pid==vice;r['confirmed_position']=i;r['confirmed_multiplier']=2 if pid==cap else (1 if i<=11 else 0);confirmed.append(r)
    xi=confirmed[:11];bench=confirmed[11:]
    if len([p for p in xi if p.get('captain')])!=1 or len([p for p in xi if p.get('vice')])!=1:raise RuntimeError('Manual captain/vice invalid')
    data.setdefault('comparison',{})['current_xi']=xi
    data['confirmed_fpl']={'gw':mgw,'source':'user-confirmed-screenshot-fallback','view':'submitted-lineup','exact_order':True,'automatic_subs_applied':[],'lineup':xi,'bench':bench,'captain_id':cap,'vice_id':vice,'fallback_rows':[],'total_points':ov.get('total_points'),'temporary_until_official_snapshot':True}
    return data,mgw,True


def main():
    data=json.loads(PATH.read_text(encoding='utf-8'));gw=int(data.get('source_snapshot_gw') or 0)
    if gw<=0: raise RuntimeError('Missing source_snapshot_gw')
    snap=get(f'entry/{TEAM_ID}/event/{gw}/picks/');picks,auto_subs=apply_automatic_subs(snap.get('picks') or [],snap.get('automatic_subs') or [])
    if len(picks)!=15: raise RuntimeError(f'Expected 15 confirmed picks, got {len(picks)}')
    boot=get('bootstrap-static/');bootstrap={int(p['id']):p for p in boot.get('elements') or []};team_names={int(t['id']):t.get('name','') for t in boot.get('teams') or []}
    rows={int(p['id']):dict(p) for p in (data.get('lineup') or [])+(data.get('bench') or []) if p.get('id') is not None}
    for side in ('current_xi','transfer_xi'):
        for p in ((data.get('comparison') or {}).get(side) or []):
            if p.get('id') is not None: rows.setdefault(int(p['id']),dict(p))
    missing=[int(x['element']) for x in picks if int(x['element']) not in rows]
    for pid in missing: rows[pid]=fallback_row(pid,bootstrap,team_names)
    confirmed=[]
    for pick in picks:
        pid=int(pick['element']);p=dict(rows[pid]);bp=bootstrap.get(pid) or {};team_id=int(p.get('team_id') or bp.get('team') or 0)
        p['team_id']=team_id;p['team']=team_names.get(team_id) or p.get('team') or 'Ukjent lag'
        p['captain']=bool(pick.get('is_captain'));p['vice']=bool(pick.get('is_vice_captain'));p['confirmed_position']=int(pick['position']);p['confirmed_multiplier']=int(pick.get('multiplier') or 0);confirmed.append(p)
    xi=confirmed[:11];bench=confirmed[11:]
    if len([p for p in xi if p.get('captain')])!=1 or len([p for p in xi if p.get('vice')])!=1: raise RuntimeError('Confirmed captain/vice invalid')
    data.setdefault('comparison',{})['current_xi']=xi
    data['confirmed_fpl']={'gw':gw,'source':'official-picks-api','view':'effective-points-lineup','exact_order':True,'automatic_subs_applied':auto_subs,'lineup':xi,'bench':bench,'captain_id':next(p['id'] for p in xi if p.get('captain')),'vice_id':next(p['id'] for p in xi if p.get('vice')),'fallback_rows':missing}
    data,used_gw,manual=apply_manual_snapshot_if_newer(data,bootstrap,team_names,rows,gw)
    if manual:data['source_snapshot_gw']=used_gw
    PATH.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');print('Applied confirmed baseline GW',used_gw,'manual fallback',manual)
    runpy.run_path('current_squad_sync_v1.py',run_name='__main__')
    runpy.run_path('optimal_lineup_v1.py',run_name='__main__')
    runpy.run_path('post_transfer_state_v1.py',run_name='__main__')
    runpy.run_path('post_transfer_plan_v1.py',run_name='__main__')

if __name__=='__main__': main()

from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

DATA=Path('data.json');ROOT=Path('timing_snapshots')

def price_raw(p):
    if not isinstance(p,dict):return None
    try:
        v=p.get('now_cost')
        if v is not None:return int(v)
        v=p.get('price')
        if v is not None:return int(round(float(v)*10))
    except Exception:return None
    return None

def main():
    d=json.loads(DATA.read_text(encoding='utf-8'));gw=int(d['gw'])
    deadline=datetime.fromisoformat(str(d['deadline_time']).replace('Z','+00:00'));now=datetime.now(timezone.utc)
    ROOT.mkdir(exist_ok=True);path=ROOT/f'gw{gw:02d}.json'
    if now>=deadline:print('Timing snapshot: deadline passed');return
    if path.exists():print('Timing snapshot already frozen');return
    rows=[]
    for i,c in enumerate(d.get('candidates') or []):
        pair=(c.get('pairs') or [{}])[0];out=pair.get('out') or {};inn=pair.get('in') or {};tv=c.get('timing_value_shadow') or {}
        rows.append({'candidate_index':i,'out':{'id':out.get('id'),'name':out.get('name'),'price_raw':price_raw(out)},'in':{'id':inn.get('id'),'name':inn.get('name'),'price_raw':price_raw(inn)},'bank_after':c.get('bank_after'),'timing':tv})
    payload={'version':'1.0','gw':gw,'frozen_at':now.isoformat().replace('+00:00','Z'),'deadline_time':d.get('deadline_time'),'fpl_team_id':d.get('fpl_team_id'),'candidates':rows,'price_prediction':False}
    path.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8');print('Frozen timing snapshot',path,len(rows))

if __name__=='__main__':main()

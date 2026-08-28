from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path

DATA=Path('data.json');SHADOW=Path('market_ab_shadow.json');ROOT=Path('market_ab_snapshots');INDEX=ROOT/'index.json'

def main():
 if not DATA.exists() or not SHADOW.exists():return
 d=json.loads(DATA.read_text(encoding='utf-8'));s=json.loads(SHADOW.read_text(encoding='utf-8'));gw=int(d['gw'])
 deadline=datetime.fromisoformat(d['deadline_time'].replace('Z','+00:00'));now=datetime.now(timezone.utc)
 if now>=deadline:print('Market A/B: deadline passed; not freezing');return
 if int(s.get('gw',-1))!=gw:raise RuntimeError('Market A/B shadow GW mismatch')
 ROOT.mkdir(exist_ok=True);path=ROOT/f'gw{gw:02d}.json'
 if path.exists():print('Market A/B snapshot already frozen',path);return
 payload={**s,'frozen_at':now.isoformat().replace('+00:00','Z'),'deadline_time':d.get('deadline_time'),'model_version':d.get('model_version')}
 path.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
 idx=[]
 if INDEX.exists():
  try:idx=json.loads(INDEX.read_text(encoding='utf-8'))
  except:idx=[]
 idx=[x for x in idx if int(x.get('gw',-1))!=gw];idx.append({'gw':gw,'file':path.as_posix(),'frozen_at':payload['frozen_at'],'market_active':bool(payload.get('market_active')),'player_count':len(payload.get('players') or [])});idx.sort(key=lambda x:int(x['gw']))
 INDEX.write_text(json.dumps(idx,ensure_ascii=False,indent=2),encoding='utf-8');print('Frozen market A/B snapshot',path)
if __name__=='__main__':main()

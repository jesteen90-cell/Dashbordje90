from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path

DATA=Path('data.json');ROOT=Path('option_value_snapshots');INDEX=ROOT/'index.json'

def main():
    d=json.loads(DATA.read_text(encoding='utf-8'));gw=int(d['gw']);deadline=datetime.fromisoformat(d['deadline_time'].replace('Z','+00:00'));now=datetime.now(timezone.utc)
    ROOT.mkdir(exist_ok=True);snap=ROOT/f'gw{gw:02d}.json'
    if now>=deadline:
        print(f'GW{gw}: deadline passed; no option-value snapshot written');return
    if snap.exists():
        print(f'GW{gw}: option-value snapshot already frozen; keeping original');return
    tov=d.get('transfer_option_value') or {};bi=d.get('budget_intelligence') or {};candidates=[]
    for i,c in enumerate(d.get('candidates') or []):
        pair=(c.get('pairs') or [{}])[0];out=pair.get('out') or {};inn=pair.get('in') or {};ov=c.get('option_value_shadow') or {}
        candidates.append({'rank':i+1,'out':{'id':out.get('id'),'name':out.get('name')},'in':{'id':inn.get('id'),'name':inn.get('name')},'horizon_gain':c.get('horizon_gain'),'short_gain':c.get('short_gain'),'bank_after':c.get('bank_after'),'option_value':ov.get('total'),'option_vs_bank':ov.get('vs_bank'),'future_free_transfers':ov.get('future_free_transfers'),'upgrade_paths':ov.get('affordable_upgrade_paths'),'shadow_score':round(float(c.get('horizon_gain') or 0)+float(ov.get('vs_bank') or 0),3)})
    payload={'snapshot_version':'1.0','frozen_at':now.isoformat().replace('+00:00','Z'),'gw':gw,'deadline_time':d.get('deadline_time'),'model_version':d.get('model_version'),'budget':d.get('budget'),'free_transfers':d.get('free_transfers_assumed'),'budget_intelligence_version':bi.get('version'),'transfer_option_value_version':tov.get('version'),'baseline_bank_action':tov.get('baseline_bank_action'),'production_top_rank':1 if candidates else None,'shadow_top_rank':max(range(len(candidates)),key=lambda i:candidates[i]['shadow_score'])+1 if candidates else None,'candidates':candidates}
    snap.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    index=[]
    if INDEX.exists():
        try:index=json.loads(INDEX.read_text(encoding='utf-8'))
        except Exception:index=[]
    index=[x for x in index if int(x.get('gw',-1))!=gw];index.append({'gw':gw,'file':snap.as_posix(),'frozen_at':payload['frozen_at'],'deadline_time':payload['deadline_time'],'production_top_rank':payload['production_top_rank'],'shadow_top_rank':payload['shadow_top_rank'],'candidate_count':len(candidates)});index.sort(key=lambda x:int(x['gw']));INDEX.write_text(json.dumps(index,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Frozen option-value snapshot',snap,'production top',payload['production_top_rank'],'shadow top',payload['shadow_top_rank'])

if __name__=='__main__':main()

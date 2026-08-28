"""Optimal Current XI v1.
Chooses the highest projected legal GW XI from the current owned squad, then sets
bench order and captain/vice from the existing captain model where possible.
"""
from __future__ import annotations
import itertools, json
from pathlib import Path
P=Path('data.json')

def legal(xs):
    c={p:sum(1 for x in xs if x.get('position')==p) for p in ('GK','DEF','MID','FWD')}
    return c['GK']==1 and c['DEF']>=3 and c['MID']>=2 and c['FWD']>=1 and len(xs)==11

def score(xs): return sum(float(x.get('xp') or 0) for x in xs)

def main():
    d=json.loads(P.read_text(encoding='utf-8')); cs=d.get('current_squad') or {}; squad=cs.get('players') or []
    if len(squad)!=15: raise RuntimeError(f'Need 15-player current squad, got {len(squad)}')
    best=None; best_score=-1e9
    for combo in itertools.combinations(squad,11):
        if not legal(combo): continue
        s=score(combo)
        if s>best_score: best_score=s; best=list(combo)
    if not best: raise RuntimeError('No legal XI found')
    xi_ids={int(x['id']) for x in best}; bench=[x for x in squad if int(x['id']) not in xi_ids]
    outfield=sorted([x for x in bench if x.get('position')!='GK'],key=lambda x:float(x.get('xp') or 0),reverse=True)
    keepers=[x for x in bench if x.get('position')=='GK']; bench_order=outfield+keepers

    # Prefer the already validated captain model among players who are in the optimal XI.
    ranked=[]
    for p in d.get('captain_comparison') or []:
        try: pid=int(p.get('id'))
        except Exception: continue
        if pid in xi_ids and pid not in ranked: ranked.append(pid)
    for p in sorted(best,key=lambda x:float(x.get('xp') or 0),reverse=True):
        pid=int(p['id'])
        if pid not in ranked: ranked.append(pid)
    cap_id=ranked[0]; vice_id=ranked[1]
    for p in squad:
        p['optimal_start']=int(p['id']) in xi_ids; p['optimal_captain']=int(p['id'])==cap_id; p['optimal_vice']=int(p['id'])==vice_id
    best=sorted(best,key=lambda x:({'FWD':1,'MID':2,'DEF':3,'GK':4}.get(x.get('position'),9),-float(x.get('xp') or 0)))
    cap=next(x for x in squad if int(x['id'])==cap_id); vice=next(x for x in squad if int(x['id'])==vice_id)
    formation='-'.join(str(sum(1 for x in best if x.get('position')==p)) for p in ('DEF','MID','FWD'))
    d['optimal_current_lineup']={
        'version':'1.0-xp-legal-xi','gw':int(d.get('gw') or 0),'source_current_squad_version':cs.get('version'),'formation':formation,
        'expected_team_score':round(best_score,2),'lineup':best,'bench':bench_order,'captain_id':cap_id,'captain':cap.get('name'),'vice_id':vice_id,'vice':vice.get('name'),
        'method':'Enumerates every legal 11-player combination from the current owned 15 and maximizes current-GW production xP. Captain/vice prefer the validated captain ranking when available.',
        'transfer_count_current_gw':cs.get('transfer_count_current_gw',0)
    }
    P.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Optimal XI',formation,round(best_score,2),[x['name'] for x in best],'bench',[x['name'] for x in bench_order],'C',cap.get('name'),'VC',vice.get('name'))

if __name__=='__main__': main()

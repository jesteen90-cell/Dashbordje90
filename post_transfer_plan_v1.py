"""Post-transfer Plan v1.
Re-runs the validated beam-search transfer optimizer from the squad actually owned
after current-GW transfers. Current GW is lineup-only; planning begins next GW with
one new free transfer under normal FPL rules.
"""
from __future__ import annotations
import json
from pathlib import Path
from transfer_optimizer_v2 import optimize,best_xi
P=Path('data.json')

def main():
    d=json.loads(P.read_text(encoding='utf-8')); cs=d.get('current_squad') or {}; state=d.get('current_transfer_state') or {}
    if not state.get('post_transfer_mode'):
        d['post_transfer_plan']={'version':'1.0','active':False,'reason':'No completed current-GW transfer requiring post-transfer re-optimization.'};P.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');return
    cache=json.loads(Path('projection_cache.json').read_text(encoding='utf-8')); all_rows=cache.get('players') or []; gws=[int(g) for g in cache.get('gws') or []]; current_gw=int(d.get('gw') or 0); plan_gws=[g for g in gws if g>current_gw][:3]
    if not plan_gws: raise RuntimeError('No future GWs available in projection cache')
    weights={int(k):float(v) for k,v in (cache.get('weights') or {}).items()}; by={}
    for r in all_rows:
        by[int(r['id'])]={'id':int(r['id']),'web_name':r.get('name'),'team':int(r.get('team') or 0),'element_type':int(r.get('element_type') or 0),'now_cost':int(r.get('now_cost') or 0),'_x':{int(k):float(v) for k,v in (r.get('xp') or {}).items()},'_proj':{}}
    owned=[]; current_meta={int(p['id']):p for p in cs.get('players') or []}
    for pid in cs.get('owned_ids') or []:
        p=dict(by[int(pid)]); meta=current_meta.get(int(pid)) or {}; sp=meta.get('selling_price'); price=meta.get('price')
        if sp is not None: p['selling_price']=int(round(float(sp)*10))
        elif price is not None: p['selling_price']=int(round(float(price)*10))
        owned.append(p)
    bank_raw=int(round(float((d.get('budget') or {}).get('bank') or 0)*10))
    res=optimize(list(by.values()),owned,bank_raw,plan_gws,weights,free_transfers=1,beam_width=70,per_pos=12,save_ft_value=.45,max_saved_ft=5,hit_cost=4.0,max_transfers_per_gw=2)
    sq=list(owned); bank=bank_raw; ft=1; steps=[]
    for mv in res.get('moves') or []:
        gw=int(mv['gw']); ft_before=ft; pairs=[]
        if mv.get('action')=='transfer':
            for oid,iid in mv.get('pairs') or []:
                sell=next(p for p in sq if int(p['id'])==int(oid)); buy=by[int(iid)]; bank+=int(sell.get('selling_price',sell.get('now_cost',0)))-int(buy.get('now_cost',0)); sq=[p for p in sq if int(p['id'])!=int(oid)]+[buy]; pairs.append({'out_id':int(oid),'out_name':sell.get('web_name'),'in_id':int(iid),'in_name':buy.get('web_name')})
            k=len(pairs); hit=max(0,k-ft_before)*4; ft=min(5,max(0,ft_before-k)+1)
        else:
            hit=0; ft=min(5,ft_before+1)
        xi=best_xi(sq,gw); cap=xi.get('captain'); raw=float(xi.get('raw') or 0); capxp=float((cap or {}).get('_x',{}).get(gw,0)) if cap else 0
        steps.append({'gw':gw,'action':mv.get('action'),'pairs':pairs,'hit':hit,'free_transfers_before':ft_before,'free_transfers_after':ft,'bank_after':round(bank/10,1),'expected_xi_score':round(raw,2),'captain':(cap or {}).get('web_name'),'captain_xp':round(capxp,2),'expected_score_with_captain':round(raw+capxp-hit,2),'xi_ids':[int(p['id']) for p in xi.get('xi') or []]})
    d['post_transfer_plan']={'version':'1.0-validated-optimizer','active':True,'source_current_squad_version':cs.get('version'),'starting_gw':plan_gws[0],'gws':plan_gws,'starting_free_transfers':1,'starting_bank':round(bank_raw/10,1),'optimizer_gain':round(float(res.get('gain') or 0),2),'final_bank':round(float(res.get('bank') or 0)/10,1),'final_free_transfers':int(res.get('free_transfers') or 0),'total_hit_points':int(res.get('hit_points') or 0),'steps':steps,'method':'Existing validated transfer_optimizer_v2 beam search, restarted from the post-transfer owned squad.'}
    P.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');print('Post-transfer plan',d['post_transfer_plan'])
if __name__=='__main__': main()

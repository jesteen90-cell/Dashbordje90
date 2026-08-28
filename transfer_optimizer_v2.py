from __future__ import annotations
import itertools,json
from pathlib import Path
from captain_horizon_v1 import horizon_values

POS_COUNTS={1:2,2:5,3:5,4:3}
BENCH_RESILIENCE_WEIGHT=.055

def _captain_weights():
    """Use the promoted production captain weights when available.

    The final dashboard can still promote a later shadow model, but transfer
    planning should at minimum optimize against the same validated captain
    surface used by the production generator instead of raw xP only.
    """
    default={'xp':1.0,'ceiling':0.0,'minutes':0.0,'attack':0.0,'volatility_penalty':0.0}
    p=Path('captain_v3_status.json')
    if not p.exists():return default
    try:
        d=json.loads(p.read_text())
        if not d.get('promote'):return default
        w=d.get('weights') or {}
        return {k:float(w.get(k,default[k])) for k in default}
    except Exception:return default

CAPTAIN_WEIGHTS=_captain_weights()

def legal(squad):
    if len(squad)!=15 or len({int(p['id']) for p in squad})!=15:return False
    if {pos:sum(int(p['element_type'])==pos for p in squad) for pos in POS_COUNTS}!=POS_COUNTS:return False
    clubs={}
    for p in squad:clubs[int(p['team'])]=clubs.get(int(p['team']),0)+1
    return max(clubs.values(),default=0)<=3

def captain_value(p,gw):
    xp=float(p['_x'].get(gw,0));proj=(p.get('_proj') or {}).get(gw,{}) or {};w=CAPTAIN_WEIGHTS
    ceiling=float(proj.get('p90',xp));mins=float(proj.get('xmins',90))/90;attack=float(proj.get('attack_multiplier',1));vol=float(proj.get('volatility',0))
    return w['xp']*xp+w['ceiling']*ceiling+w['minutes']*mins+w['attack']*attack-w['volatility_penalty']*vol

def best_xi(squad,gw):
    by={p:[x for x in squad if int(x['element_type'])==p] for p in POS_COUNTS};best=None
    for gk in itertools.combinations(by[1],1):
      for nd in range(3,6):
       for nm in range(2,6):
        nf=10-nd-nm
        if not 1<=nf<=3 or nd>len(by[2]) or nm>len(by[3]) or nf>len(by[4]):continue
        for ds in itertools.combinations(by[2],nd):
         for ms in itertools.combinations(by[3],nm):
          for fs in itertools.combinations(by[4],nf):
           xi=list(gk+ds+ms+fs);raw=sum(float(p['_x'].get(gw,0)) for p in xi)
           if best is None or raw>best[0]:best=(raw,xi)
    if not best:return {'raw':0,'captain':None,'xi':[]}
    cap=max(best[1],key=lambda p:captain_value(p,gw))
    return {'raw':best[0],'captain':cap,'xi':best[1]}

def bench_resilience(squad,xi,gw):
    """Small insurance value for useful bench depth, never close to XI value."""
    xi_ids={int(p['id']) for p in xi};bench=[p for p in squad if int(p['id']) not in xi_ids]
    outfield=sorted((p for p in bench if int(p['element_type'])!=1),key=lambda p:float(p['_x'].get(gw,0)),reverse=True)
    keepers=sorted((p for p in bench if int(p['element_type'])==1),key=lambda p:float(p['_x'].get(gw,0)),reverse=True)
    slot_weights=(1.0,.55,.28)
    value=sum(float(p['_x'].get(gw,0))*slot_weights[i] for i,p in enumerate(outfield[:3]))
    if keepers:value+=float(keepers[0]['_x'].get(gw,0))*.18
    return BENCH_RESILIENCE_WEIGHT*value

def gw_value(squad,gw):
    o=best_xi(squad,gw)
    # Captain receives one extra copy of his xP. Selection uses captain_value,
    # while the points contribution remains expected FPL points to avoid mixing
    # utility-score units into the squad objective.
    captain_xp=float(o['captain']['_x'].get(gw,0)) if o['captain'] else 0
    return o['raw']+captain_xp+bench_resilience(squad,o['xi'],gw)

def _incoming_pools(players,squad,gws,weights,per_pos=12):
    owned={int(p['id']) for p in squad};pools={};caph=horizon_values(players,gws,weights)
    for pos in POS_COUNTS:
        xs=[p for p in players if int(p['element_type'])==pos and int(p['id']) not in owned]
        def pool_score(p):
            vals=[float(p['_x'].get(g,0))*weights.get(g,1) for g in gws];h=caph.get(int(p['id']),{});persistence=float(h.get('captain_horizon_bonus',0));near=int(h.get('near_best_gws',0))
            cap_peak=max((captain_value(p,g)*weights.get(g,1) for g in gws),default=0)
            return sum(vals)+0.14*max(vals,default=0)+0.08*cap_peak+0.55*persistence+0.08*near
        xs.sort(key=pool_score,reverse=True);limit=per_pos+2 if pos in (3,4) else per_pos;pools[pos]=xs[:limit]
    return pools

def _one_transfer_states(st,pools):
    owned={int(p['id']) for p in st['squad']};out=[]
    for sell in st['squad']:
        budget=st['bank']+int(sell['now_cost'])
        for buy in pools[int(sell['element_type'])]:
            if int(buy['id']) in owned or int(buy['now_cost'])>budget:continue
            ns=[p for p in st['squad'] if int(p['id'])!=int(sell['id'])]+[buy]
            if not legal(ns):continue
            out.append((ns,budget-int(buy['now_cost']),[(int(sell['id']),int(buy['id']))]))
    return out

def optimize(players,squad,bank,gws,weights,free_transfers=1,beam_width=70,per_pos=12,save_ft_value=.45,max_saved_ft=5,hit_cost=4.0,max_transfers_per_gw=2):
    """Fast beam-search transfer planner across multiple GWs."""
    assert legal(squad);beam_width=max(24,min(int(beam_width),70));per_pos=max(8,min(int(per_pos),12));pools=_incoming_pools(players,squad,gws,weights,per_pos);cache={}
    def cv(sq,gw):
        key=(gw,tuple(sorted(int(p['id']) for p in sq)))
        if key not in cache:cache[key]=gw_value(sq,gw)
        return cache[key]
    start_ft=max(1,min(max_saved_ft,int(free_transfers)));beam=[{'squad':list(squad),'bank':int(bank),'ft':start_ft,'score':0.0,'moves':[],'hits':0}]
    for gw in gws:
        nxt=[]
        for st in beam:
            nft=min(max_saved_ft,st['ft']+1);flex_delta=save_ft_value*(nft-st['ft']);val=cv(st['squad'],gw)*weights.get(gw,1)+flex_delta;nxt.append({**st,'ft':nft,'score':st['score']+val,'moves':st['moves']+[{'gw':gw,'action':'bank','transfers':0,'hit':0}]})
            first=_one_transfer_states(st,pools)
            for ns,nb,pairs in first:
                k=1;hit=max(0,k-st['ft'])*hit_cost;nft=min(max_saved_ft,max(0,st['ft']-k)+1);flex_delta=save_ft_value*(nft-st['ft']);val=cv(ns,gw)*weights.get(gw,1)-hit+flex_delta;nxt.append({'squad':ns,'bank':nb,'ft':nft,'score':st['score']+val,'hits':st['hits']+int(hit),'moves':st['moves']+[{'gw':gw,'action':'transfer','pairs':pairs,'transfers':1,'hit':int(hit)}]})
            if max_transfers_per_gw>=2 and first:
                ranked=sorted(first,key=lambda x:cv(x[0],gw),reverse=True)[:7]
                for ns1,nb1,p1 in ranked:
                    owned={int(p['id']) for p in ns1};sell_candidates=sorted(ns1,key=lambda p:sum(float(p['_x'].get(g,0))*weights.get(g,1) for g in gws))[:8]
                    for sell in sell_candidates:
                        if int(sell['id'])==p1[0][1]:continue
                        budget=nb1+int(sell['now_cost'])
                        for buy in pools[int(sell['element_type'])][:6]:
                            if int(buy['id']) in owned or int(buy['now_cost'])>budget:continue
                            ns2=[p for p in ns1 if int(p['id'])!=int(sell['id'])]+[buy]
                            if not legal(ns2):continue
                            k=2;hit=max(0,k-st['ft'])*hit_cost;nft=min(max_saved_ft,max(0,st['ft']-k)+1);nb=budget-int(buy['now_cost']);flex_delta=save_ft_value*(nft-st['ft']);val=cv(ns2,gw)*weights.get(gw,1)-hit+flex_delta;nxt.append({'squad':ns2,'bank':nb,'ft':nft,'score':st['score']+val,'hits':st['hits']+int(hit),'moves':st['moves']+[{'gw':gw,'action':'transfer','pairs':p1+[(int(sell['id']),int(buy['id']))],'transfers':2,'hit':int(hit)}]})
        dedup={}
        for st in nxt:
            key=(tuple(sorted(int(p['id']) for p in st['squad'])),st['bank'],st['ft'])
            if key not in dedup or st['score']>dedup[key]['score']:dedup[key]=st
        beam=sorted(dedup.values(),key=lambda s:s['score'],reverse=True)[:beam_width]
    best=beam[0];baseline=sum(cv(squad,g)*weights.get(g,1) for g in gws)
    return {'score':best['score'],'baseline_score':baseline,'gain':best['score']-baseline,'bank':best['bank'],'free_transfers':best['ft'],'hit_points':best['hits'],'moves':best['moves'],'squad':best['squad'],'cache_entries':len(cache),'captain_horizon_search':True,'captain_selection_aligned':True,'captain_weights':CAPTAIN_WEIGHTS,'bench_resilience':True,'bench_resilience_weight':BENCH_RESILIENCE_WEIGHT}

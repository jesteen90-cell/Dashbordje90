from __future__ import annotations
import itertools

POS_COUNTS={1:2,2:5,3:5,4:3}

def legal(squad):
    if len(squad)!=15 or len({int(p['id']) for p in squad})!=15:return False
    if {pos:sum(int(p['element_type'])==pos for p in squad) for pos in POS_COUNTS}!=POS_COUNTS:return False
    clubs={}
    for p in squad:clubs[int(p['team'])]=clubs.get(int(p['team']),0)+1
    return max(clubs.values(),default=0)<=3

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
    cap=max(best[1],key=lambda p:float(p['_x'].get(gw,0)))
    return {'raw':best[0],'captain':cap,'xi':best[1]}

def gw_value(squad,gw,captain_multiplier=1.0):
    o=best_xi(squad,gw);return o['raw']+(float(o['captain']['_x'].get(gw,0))*captain_multiplier if o['captain'] else 0)

def _incoming_pools(players,squad,gws,weights,per_pos=14):
    owned={int(p['id']) for p in squad};pools={}
    for pos in POS_COUNTS:
        xs=[p for p in players if int(p['element_type'])==pos and int(p['id']) not in owned]
        xs.sort(key=lambda p:sum(float(p['_x'].get(g,0))*weights.get(g,1) for g in gws),reverse=True)
        pools[pos]=xs[:per_pos]
    return pools

def optimize(players,squad,bank,gws,weights,free_transfers=1,beam_width=45,per_pos=14,save_ft_value=.55,max_saved_ft=5):
    """Beam-search 0/1-transfer sequences across gameweeks.

    State explicitly values saved transfers, bank and future xP. Hits are not
    generated yet; this first version only spends available free transfers.
    Prices use current FPL now_cost units (tenths of a million).
    """
    assert legal(squad)
    pools=_incoming_pools(players,squad,gws,weights,per_pos)
    initial={'squad':list(squad),'bank':int(bank),'ft':max(1,min(max_saved_ft,int(free_transfers))),'score':0.0,'moves':[]}
    beam=[initial]
    for i,gw in enumerate(gws):
        nxt=[]
        for st in beam:
            # Bank transfer. Carry FT forward, capped at five.
            banked=min(max_saved_ft,st['ft']+1)
            val=gw_value(st['squad'],gw)*weights.get(gw,1)+save_ft_value*banked
            nxt.append({**st,'ft':banked,'score':st['score']+val,'moves':st['moves']+[{'gw':gw,'action':'bank'}]})
            if st['ft']<=0:continue
            owned={int(p['id']) for p in st['squad']}
            for out in st['squad']:
                budget=st['bank']+int(out['now_cost'])
                for inn in pools[int(out['element_type'])]:
                    if int(inn['id']) in owned or int(inn['now_cost'])>budget:continue
                    ns=[p for p in st['squad'] if int(p['id'])!=int(out['id'])]+[inn]
                    if not legal(ns):continue
                    nb=budget-int(inn['now_cost']);nft=min(max_saved_ft,st['ft']) # spend one, then earn next GW after this state
                    val=gw_value(ns,gw)*weights.get(gw,1)+save_ft_value*nft
                    nxt.append({'squad':ns,'bank':nb,'ft':nft,'score':st['score']+val,'moves':st['moves']+[{'gw':gw,'action':'transfer','out':int(out['id']),'in':int(inn['id'])}]})
        # Deduplicate equivalent squad/bank/FT states, keep best path.
        dedup={}
        for st in nxt:
            key=(tuple(sorted(int(p['id']) for p in st['squad'])),st['bank'],st['ft'])
            if key not in dedup or st['score']>dedup[key]['score']:dedup[key]=st
        beam=sorted(dedup.values(),key=lambda s:s['score'],reverse=True)[:beam_width]
    best=beam[0]
    baseline=sum(gw_value(squad,g)*weights.get(g,1) for g in gws)
    return {'score':best['score'],'baseline_score':baseline,'gain':best['score']-baseline,'bank':best['bank'],'free_transfers':best['ft'],'moves':best['moves'],'squad':best['squad']}

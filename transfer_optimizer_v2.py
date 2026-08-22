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

def gw_value(squad,gw):
    o=best_xi(squad,gw);return o['raw']+(float(o['captain']['_x'].get(gw,0)) if o['captain'] else 0)

def _incoming_pools(players,squad,gws,weights,per_pos=12):
    owned={int(p['id']) for p in squad};pools={}
    for pos in POS_COUNTS:
        xs=[p for p in players if int(p['element_type'])==pos and int(p['id']) not in owned]
        xs.sort(key=lambda p:sum(float(p['_x'].get(g,0))*weights.get(g,1) for g in gws),reverse=True)
        pools[pos]=xs[:per_pos]
    return pools

def _one_transfer_states(st,players,pools,gw):
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
    """Beam-search transfer sequences across GWs.

    Correct FPL-style FT accounting: after k transfers, next week's FT is
    min(5, max(0, current_ft-k)+1). Transfers beyond current FT cost 4 points.
    Search includes bank, one-transfer and (optionally) two-transfer paths.
    """
    assert legal(squad)
    pools=_incoming_pools(players,squad,gws,weights,per_pos)
    beam=[{'squad':list(squad),'bank':int(bank),'ft':max(1,min(max_saved_ft,int(free_transfers))),'score':0.0,'moves':[],'hits':0}]
    for gw in gws:
        nxt=[]
        for st in beam:
            # 0 transfers
            nft=min(max_saved_ft,st['ft']+1);val=gw_value(st['squad'],gw)*weights.get(gw,1)+save_ft_value*nft
            nxt.append({**st,'ft':nft,'score':st['score']+val,'moves':st['moves']+[{'gw':gw,'action':'bank','transfers':0,'hit':0}]})
            # 1 transfer
            first=_one_transfer_states(st,players,pools,gw)
            for ns,nb,pairs in first:
                k=1;hit=max(0,k-st['ft'])*hit_cost;nft=min(max_saved_ft,max(0,st['ft']-k)+1)
                val=gw_value(ns,gw)*weights.get(gw,1)-hit+save_ft_value*nft
                nxt.append({'squad':ns,'bank':nb,'ft':nft,'score':st['score']+val,'hits':st['hits']+int(hit),'moves':st['moves']+[{'gw':gw,'action':'transfer','pairs':pairs,'transfers':1,'hit':int(hit)}]})
            # 2 transfers: expand only the strongest first-step states to control combinatorics
            if max_transfers_per_gw>=2:
                ranked=sorted(first,key=lambda x:gw_value(x[0],gw),reverse=True)[:18]
                for ns1,nb1,p1 in ranked:
                    tmp={'squad':ns1,'bank':nb1};owned={int(p['id']) for p in ns1}
                    for sell in ns1:
                        if int(sell['id'])==p1[0][1]:continue
                        budget=nb1+int(sell['now_cost'])
                        for buy in pools[int(sell['element_type'])][:8]:
                            if int(buy['id']) in owned or int(buy['now_cost'])>budget:continue
                            ns2=[p for p in ns1 if int(p['id'])!=int(sell['id'])]+[buy]
                            if not legal(ns2):continue
                            k=2;hit=max(0,k-st['ft'])*hit_cost;nft=min(max_saved_ft,max(0,st['ft']-k)+1);nb=budget-int(buy['now_cost'])
                            val=gw_value(ns2,gw)*weights.get(gw,1)-hit+save_ft_value*nft
                            nxt.append({'squad':ns2,'bank':nb,'ft':nft,'score':st['score']+val,'hits':st['hits']+int(hit),'moves':st['moves']+[{'gw':gw,'action':'transfer','pairs':p1+[(int(sell['id']),int(buy['id']))],'transfers':2,'hit':int(hit)}]})
        dedup={}
        for st in nxt:
            key=(tuple(sorted(int(p['id']) for p in st['squad'])),st['bank'],st['ft'])
            if key not in dedup or st['score']>dedup[key]['score']:dedup[key]=st
        beam=sorted(dedup.values(),key=lambda s:s['score'],reverse=True)[:beam_width]
    best=beam[0];baseline=sum(gw_value(squad,g)*weights.get(g,1) for g in gws)
    return {'score':best['score'],'baseline_score':baseline,'gain':best['score']-baseline,'bank':best['bank'],'free_transfers':best['ft'],'hit_points':best['hits'],'moves':best['moves'],'squad':best['squad']}

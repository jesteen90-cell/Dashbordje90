"""Shadow-model the future option value of FPL transfer choices.

Uses the compact transfer_option_pool embedded in data.json, so the analysis is
fully reproducible from the published feed and has no hidden cache dependency.
It does not change production transfer ranking.
"""
from __future__ import annotations
import json
from pathlib import Path

DATA=Path('data.json')
FT_POINT_VALUE=0.45
BANK_POINT_VALUE=0.16
MAX_BANK_CREDIT=1.5
UPGRADE_THRESHOLD=0.75


def n(v,d=0.0):
    try:return float(v)
    except Exception:return d


def horizon_xp(p,gws,weights):
    xp=p.get('xp') or {}
    return sum(n(xp.get(str(g)))*n(weights.get(str(g),weights.get(g,1.0)),1.0) for g in gws)


def bank_utility(bank_m):return min(max(n(bank_m),0.0),MAX_BANK_CREDIT)*BANK_POINT_VALUE

def ft_after_one_move(ft):return min(5,max(0,int(ft)-1)+1)

def build_state_ids(squad_ids,candidate):
    ids=set(int(x) for x in squad_ids)
    for pair in candidate.get('pairs') or []:
        out=(pair.get('out') or {}).get('id');inn=(pair.get('in') or {}).get('id')
        if out is not None:ids.discard(int(out))
        if inn is not None:ids.add(int(inn))
    return ids


def affordable_upgrade_surface(state_ids,bank_m,players,gws,weights):
    byid={int(p['id']):p for p in players};owned=[byid[i] for i in state_ids if i in byid];owned_ids=set(state_ids);best_paths=[]
    for sell in owned:
        pos=int(sell.get('element_type') or 0);sale=n(sell.get('now_cost'))/10.0;current=horizon_xp(sell,gws,weights);buying_power=n(bank_m)+sale;best=None
        for buy in players:
            if int(buy.get('id') or 0) in owned_ids or int(buy.get('element_type') or 0)!=pos:continue
            if n(buy.get('now_cost'))/10.0>buying_power+1e-9:continue
            gain=horizon_xp(buy,gws,weights)-current
            if gain<UPGRADE_THRESHOLD:continue
            row={'out_id':int(sell['id']),'out_name':sell.get('name'),'in_id':int(buy['id']),'in_name':buy.get('name'),'gain':round(gain,2),'cost':round(n(buy.get('now_cost'))/10.0,1)}
            if best is None or row['gain']>best['gain']:best=row
        if best:best_paths.append(best)
    best_paths.sort(key=lambda x:x['gain'],reverse=True);count=len(best_paths);quality=sum(x['gain'] for x in best_paths[:3]);surface=min(0.60,0.035*count+0.025*quality)
    return {'count':count,'top_paths':best_paths[:5],'quality_sum':round(quality,2),'shadow_points':round(surface,3)}


def main():
    d=json.loads(DATA.read_text());pool=d.get('transfer_option_pool') or {};players=pool.get('players') or [];squad_ids=pool.get('owned_ids') or []
    if not players or len(squad_ids)!=15:raise RuntimeError('Published transfer_option_pool is missing or incomplete')
    raw_gws=[int(g) for g in pool.get('gws') or []];gws=raw_gws[1:4] if len(raw_gws)>1 else raw_gws[:3];weights=pool.get('weights') or {}
    ft=int(d.get('free_transfers_assumed') or 1);bank=n((d.get('budget') or {}).get('bank'));bank_ft=min(5,ft+1)
    bank_surface=affordable_upgrade_surface(set(int(x) for x in squad_ids),bank,players,gws,weights);baseline_shadow=bank_utility(bank)+FT_POINT_VALUE*bank_ft+bank_surface['shadow_points'];rows=[]
    for idx,c in enumerate(d.get('candidates') or []):
        state=build_state_ids(squad_ids,c);after=n(c.get('bank_after'));aft_ft=ft_after_one_move(ft);surf=affordable_upgrade_surface(state,after,players,gws,weights)
        components={'bank_value':round(bank_utility(after),3),'free_transfer_value':round(FT_POINT_VALUE*aft_ft,3),'upgrade_surface_value':surf['shadow_points']};total=round(sum(components.values()),3);delta=round(total-baseline_shadow,3)
        c['option_value_shadow']={'version':'1.1','total':total,'vs_bank':delta,'components':components,'future_free_transfers':aft_ft,'affordable_upgrade_paths':surf['count'],'top_upgrade_paths':surf['top_paths'],'affects_ranking':False}
        pair=(c.get('pairs') or [{}])[0];rows.append({'candidate_index':idx,'label':((pair.get('out') or {}).get('name','')+' → '+(pair.get('in') or {}).get('name','')).strip(),'horizon_gain':c.get('horizon_gain'),'bank_after':after,'option_value':total,'vs_bank':delta,'upgrade_paths':surf['count']})
    d['transfer_option_value']={'version':'1.1-shadow','mode':'shadow','affects_transfer_ranking':False,'source':'data.json transfer_option_pool','free_transfer_point_value':FT_POINT_VALUE,'bank_point_value_per_million':BANK_POINT_VALUE,'bank_value_cap_million':MAX_BANK_CREDIT,'upgrade_threshold':UPGRADE_THRESHOLD,'baseline_bank_action':{'bank':round(bank,1),'future_free_transfers':bank_ft,'option_value':round(baseline_shadow,3),'affordable_upgrade_paths':bank_surface['count'],'top_upgrade_paths':bank_surface['top_paths']},'candidates':rows,'note':'Shadow-mål: verdien av bank, lagrede gratisbytter og realistiske oppgraderingsveier. Påvirker ikke anbefalingen før backtest viser gevinst.'}
    DATA.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8');print('Transfer option value shadow written',d['transfer_option_value']['baseline_bank_action'],'candidates=',len(rows))

if __name__=='__main__':main()

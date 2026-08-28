from __future__ import annotations
import json
from pathlib import Path
import requests

DATA=Path('data.json')
BOOT='https://fantasy.premierleague.com/api/bootstrap-static/'

def n(v,d=0.0):
    try:return float(v)
    except Exception:return d

def clamp(v,a,b):return max(a,min(b,v))

def market_signal(p):
    tin=int(n(p.get('transfers_in_event')));tout=int(n(p.get('transfers_out_event')));net=tin-tout
    # Deliberately conservative proxy. FPL's price algorithm is not public;
    # this signal is for timing context only and is NOT a price prediction.
    scale=max(50000, int((tin+tout)*0.35))
    score=clamp(net/scale,-2.0,2.0)/2.0
    change=int(n(p.get('cost_change_event')))
    if change>0: label='steget allerede'
    elif change<0: label='falt allerede'
    elif score>=0.55: label='sterkt kjøpspress'
    elif score>=0.22: label='kjøpspress'
    elif score<=-0.55: label='sterkt salgspress'
    elif score<=-0.22: label='salgspress'
    else: label='rolig'
    return {'score':round(score,3),'label':label,'net_transfers':net,'transfers_in':tin,'transfers_out':tout,'cost_change_event':change,'prediction':False}

def flexibility(bank_after):
    b=n(bank_after)
    if b>=1.5:return {'grade':'HØY','score':1.0,'note':'God reserve til senere oppgraderinger.'}
    if b>=0.8:return {'grade':'GOD','score':0.75,'note':'Gir nyttig spillerom til neste trekk.'}
    if b>=0.3:return {'grade':'MIDDELS','score':0.45,'note':'Noe spillerom, men fortsatt ganske låst.'}
    return {'grade':'LAV','score':0.15,'note':'Lite eller ingen reserve til neste trekk.'}

def main():
    d=json.loads(DATA.read_text())
    r=requests.get(BOOT,headers={'Accept':'application/json','User-Agent':'fpl-autopilot-budget-intelligence-v1'},timeout=18);r.raise_for_status();boot=r.json()
    byid={int(p['id']):p for p in boot.get('elements',[])}
    confirmed=d.get('confirmed_fpl') or {}
    squad=(confirmed.get('lineup') or [])+(confirmed.get('bench') or [])
    if len(squad)!=15:squad=(d.get('comparison') or {}).get('current_xi',[])+(d.get('confirmed_fpl') or {}).get('bench',[])
    squad_ids={int(p['id']) for p in squad if p.get('id') is not None}
    squad_boot=[byid[x] for x in squad_ids if x in byid]
    # If public lineup enrichment is temporarily absent, the production budget
    # remains the authoritative market-value fallback.
    market_total=sum(n(p.get('now_cost'))/10 for p in squad_boot)
    if len(squad_boot)!=15:market_total=n((d.get('budget') or {}).get('squad_market_value'))
    premium_total=sum(n(p.get('now_cost'))/10 for p in squad_boot if n(p.get('now_cost'))>=100)
    premium_share=premium_total/max(market_total,0.1)
    current_bank=n((d.get('budget') or {}).get('bank'))
    current_flex=flexibility(current_bank)
    watch=[]
    for c in d.get('candidates') or []:
        bank_after=n(c.get('bank_after'))
        c['budget_flexibility']=flexibility(bank_after)
        pair=(c.get('pairs') or [{}])[0]
        inn=pair.get('in') or {};out=pair.get('out') or {}
        ip=byid.get(int(inn.get('id') or 0),{});op=byid.get(int(out.get('id') or 0),{})
        ims=market_signal(ip) if ip else None;oms=market_signal(op) if op else None
        c['market_timing']={'incoming':ims,'outgoing':oms,'shadow_only':True}
        notes=[]
        if ims and ims['score']>=0.55:notes.append(f"{inn.get('name','Spilleren inn')}: sterkt kjøpspress")
        if oms and oms['score']<=-0.55:notes.append(f"{out.get('name','Spilleren ut')}: sterkt salgspress")
        if bank_after<0.3:notes.append('nesten ingen bankreserve etter byttet')
        c['timing_notes']=notes
        if ims:watch.append({'id':inn.get('id'),'name':inn.get('name'),'signal':ims,'bank_after':round(bank_after,1),'horizon_gain':c.get('horizon_gain')})
    watch.sort(key=lambda x:(n((x.get('signal') or {}).get('score')),n(x.get('horizon_gain'))),reverse=True)
    d['budget_intelligence']={
        'version':'1.2-shadow',
        'mode':'shadow',
        'affects_transfer_ranking':False,
        'squad_source':'confirmed_fpl + bootstrap-static',
        'squad_players_found':len(squad_boot),
        'bank':round(current_bank,1),
        'flexibility':current_flex,
        'premium_locked_value':round(premium_total,1),
        'squad_market_value':round(market_total,1),
        'premium_share':round(premium_share,3),
        'premium_share_pct':round(100*premium_share,1),
        'price_pressure_method':'net event transfers + event price change; timing context only',
        'price_prediction':False,
        'watchlist':watch[:5],
        'note':'Prispress brukes kun som timing-/tie-break-informasjon. Forventede poeng og fler-GW-plan har prioritet.'
    }
    DATA.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Budget intelligence shadow written',d['budget_intelligence'])

if __name__=='__main__':main()

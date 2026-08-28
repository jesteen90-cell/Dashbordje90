from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

DATA=Path('data.json')

def n(v,d=0.0):
    try:return float(v)
    except Exception:return d

def clamp(v,a=0.0,b=1.0):return max(a,min(b,v))

def parse_time(v):
    try:return datetime.fromisoformat(str(v).replace('Z','+00:00'))
    except Exception:return None

def player_uncertainty(p):
    if not isinstance(p,dict):return 0.15
    availability=n(p.get('availability'),1.0)
    mins=n(p.get('expected_minutes'),90.0)
    u=0.0
    if availability<.75:u=max(u,.85)
    elif availability<.9:u=max(u,.55)
    if mins<55:u=max(u,.8)
    elif mins<70:u=max(u,.55)
    elif mins<82:u=max(u,.3)
    return u

def pressure_risk(signal,direction='in'):
    if not isinstance(signal,dict):return 0.0
    score=n(signal.get('score'))
    changed=int(n(signal.get('cost_change_event')))
    if direction=='in':
        if changed>0:return .2
        return clamp(max(0.0,score))
    if changed<0:return .2
    return clamp(max(0.0,-score))

def fragility(bank_after):
    b=n(bank_after)
    if b<=0.0:return 1.0
    if b<=0.1:return .85
    if b<=0.2:return .65
    if b<=0.4:return .35
    return .1

def recommendation(hours,lock_risk,info_value):
    if hours<=2:return ('DEADLINE NÆR','Gjør kun et allerede godkjent trekk; ikke vent på prisinformasjon nå.')
    if lock_risk>=.62 and info_value<=.42:return ('TIDLIG KAN FORSVARES','Byttet er økonomisk skjørt og prispresset er høyt. Tidlig trekk kan forsvares dersom spillerstatusen er trygg.')
    if info_value>=.55:return ('VENT PÅ MER INFO','Informasjonsverdien er høyere enn prisrisikoen akkurat nå.')
    if lock_risk>=.42:return ('FØLG TETT','Ikke jag pris, men dette trekket kan bli økonomisk låst. Revurder når ny lag-/skadeinfo kommer.')
    return ('VENT NÆRMERE DEADLINE','Lite som tilsier at prisrisikoen bør overstyre verdien av ferskere informasjon.')

def main():
    d=json.loads(DATA.read_text(encoding='utf-8'))
    deadline=parse_time(d.get('deadline_time'));now=datetime.now(timezone.utc)
    hours=max(0.0,(deadline-now).total_seconds()/3600) if deadline else 0.0
    rows=[]
    for idx,c in enumerate(d.get('candidates') or []):
        pair=(c.get('pairs') or [{}])[0];inn=pair.get('in') or {};out=pair.get('out') or {}
        mt=c.get('market_timing') or {};in_pressure=pressure_risk(mt.get('incoming'),'in');out_pressure=pressure_risk(mt.get('outgoing'),'out')
        bank_after=n(c.get('bank_after'));frag=fragility(bank_after)
        lock=clamp(frag*(.72*in_pressure+.38*out_pressure))
        uncertainty=max(player_uncertainty(inn),player_uncertainty(out))
        time_weight=clamp(hours/30.0)
        info=clamp(.16+uncertainty*.64+time_weight*.20)
        label,note=recommendation(hours,lock,info)
        shadow={'version':'1.0','label':label,'note':note,'hours_to_deadline':round(hours,1),'affordability_fragility':round(frag,3),'incoming_price_pressure_risk':round(in_pressure,3),'outgoing_price_pressure_risk':round(out_pressure,3),'lock_risk':round(lock,3),'information_value':round(info,3),'net_early_action_case':round(lock-info,3),'price_prediction':False,'affects_ranking':False}
        c['timing_value_shadow']=shadow
        rows.append({'candidate_index':idx,'label':f"{out.get('name','')} → {inn.get('name','')}",'timing':shadow})
    d['transfer_timing']={'version':'1.0-shadow','mode':'shadow','hours_to_deadline':round(hours,1),'affects_transfer_ranking':False,'price_prediction':False,'method':'price-pressure risk x affordability fragility versus information value','candidates':rows,'note':'Timing-signalet avgjør når et ellers godt bytte eventuelt bør gjøres. Det skal ikke gjøre et dårlig bytte godt, og det forsøker ikke å forutsi FPLs skjulte prisalgoritme.'}
    DATA.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Transfer timing shadow written',len(rows),'candidates','hours',round(hours,1))

if __name__=='__main__':main()

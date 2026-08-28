"""Explain how necessary the leading transfer really is.
Conservative shadow layer: combines absence, bench cover and multi-GW gain.
Never changes candidate ranking or promotes a rejected transfer.
"""
import json
from pathlib import Path
P=Path('data.json'); d=json.loads(P.read_text()); cands=d.get('candidates') or []

def n(v,default=0.0):
    try:return float(v)
    except:return default

for c in cands:
    ab=c.get('absence_severity_shadow') or {}
    ba=c.get('bench_adjustment_shadow') or {}
    rob=c.get('robustness_shadow') or {}
    sev=ab.get('severity','LAV'); urg=ab.get('replacement_urgency','LAV')
    nextg=n(ba.get('bench_adjusted_next_gw_gain'), n(c.get('short_gain')))
    three=n(ba.get('bench_adjusted_short_gain'), n(c.get('short_gain')))
    horizon=n(ba.get('bench_adjusted_horizon_gain'), n(c.get('horizon_gain')))
    score=0.0
    score += {'HØY':3.0,'MIDDELS':1.8,'USIKKER':0.8,'LAV':0.0}.get(sev,0)
    score += {'HØY':2.0,'MIDDELS':1.1,'LAV/MIDDELS':0.6,'LAV':0.0}.get(urg,0)
    score += max(-1.0,min(1.5,nextg*.35))
    score += max(-.5,min(1.5,three*.18))
    score += max(-.5,min(1.5,horizon*.08))
    if ba.get('applied') and nextg <= .25: score -= 1.2
    if rob.get('label')=='FRAGIL': score -= 1.0
    if score>=5.0: label='NØDVENDIG'
    elif score>=3.2: label='FORNUFTIG'
    elif score>=1.6: label='LUKSUSBYTTE'
    else: label='SPAR FT'
    reasons=[]
    if sev in ('HØY','MIDDELS'): reasons.append(f'Fraværsgrad {sev.lower()} trekker mot salg.')
    if ba.get('applied') and nextg<=.25: reasons.append('Benken dekker neste runde så godt at hasteverdien faller.')
    if three>=2: reasons.append(f'Benkekorrigert 3-GW-gevinst er +{three:.1f} p.')
    elif three<1: reasons.append(f'Benkekorrigert 3-GW-gevinst er bare {three:+.1f} p.')
    if horizon>=4: reasons.append('Langsiktig gevinst er sterk nok til å være relevant selv om GW2-effekten er liten.')
    if rob.get('label')=='FRAGIL': reasons.append('Trekket er fragilt på tvers av tidshorisonter.')
    c['transfer_necessity_shadow']={'version':'1.0-shadow','affects_ranking':False,'score':round(score,2),'label':label,'reasons':reasons[:4],'bench_adjusted_next_gw_gain':round(nextg,2),'three_gw_gain':round(three,2),'plan_gain':round(horizon,2)}

d['transfer_necessity_model']={'version':'1.0-shadow','affects_transfer_ranking':False,'candidate_count':len(cands),'scale':['SPAR FT','LUKSUSBYTTE','FORNUFTIG','NØDVENDIG'],'purpose':'Svar på om FT faktisk bør brukes, ikke bare hvilket bytte som rangeres høyest.'}
P.write_text(json.dumps(d,ensure_ascii=False,indent=2))
print('Transfer necessity enriched',len(cands))

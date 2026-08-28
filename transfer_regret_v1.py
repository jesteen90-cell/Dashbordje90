"""Transfer Regret Protection v1.
Estimates asymmetric regret of MAKE TRANSFER vs SAVE FT.
Conservative shadow layer: explainability/safety only; never changes ranking.
"""
import json
from pathlib import Path
P=Path('data.json'); d=json.loads(P.read_text()); cands=d.get('candidates') or []

def n(v,default=0.0):
    try:return float(v)
    except:return default

def clamp(v,a=0.0,b=1.0): return max(a,min(b,v))

for c in cands:
    ba=c.get('bench_adjustment_shadow') or c.get('bench_replacement_shadow') or {}
    rob=c.get('robustness_shadow') or {}
    tim=c.get('timing_value_shadow') or {}
    nec=c.get('transfer_necessity_shadow') or {}
    opt=c.get('option_value_shadow') or {}
    nextg=n(ba.get('bench_adjusted_next_gw_gain'),n(c.get('short_gain')))
    three=n(ba.get('bench_adjusted_short_gain'),n(c.get('short_gain')))
    horizon=n(ba.get('bench_adjusted_horizon_gain'),n(c.get('horizon_gain')))
    info=n(tim.get('information_value'))
    lock=n(tim.get('lock_risk'))
    necessity=nec.get('label','LUKSUSBYTTE')
    # Regret if we transfer: high when immediate gain is weak, bench covers, evidence is fragile,
    # information value is high, and using the FT destroys option value.
    make=0.34
    make += clamp((0.75-nextg)/2.5,0,.25)
    make += .14 if ba.get('applied') and nextg<=.25 else 0
    make += .14 if rob.get('label')=='FRAGIL' else .06 if rob.get('label')=='BLANDET' else 0
    make += .13*info
    make += .10*clamp(n(opt.get('total')),.0,1.0)
    make += .12 if necessity=='SPAR FT' else .06 if necessity=='LUKSUSBYTTE' else 0
    make=clamp(make,.05,.95)
    # Regret if we save: rises with durable multi-GW gain, urgent/necessary replacement,
    # and meaningful budget lock risk.
    save=0.22
    save += clamp(three/8.0,0,.22)
    save += clamp(horizon/18.0,0,.20)
    save += .20 if necessity=='NØDVENDIG' else .11 if necessity=='FORNUFTIG' else .04 if necessity=='LUKSUSBYTTE' else 0
    save += .13*lock
    save += .08 if rob.get('label')=='ROBUST' and three>=2 else 0
    save=clamp(save,.05,.95)
    gap=save-make
    if gap>=.12: verdict='BYTT HAR LAVERE ANGERRISIKO'
    elif gap<=-.12: verdict='SPAR FT HAR LAVERE ANGERRISIKO'
    else: verdict='ANGERRISIKOEN ER NESTEN LIK'
    c['transfer_regret_shadow']={
      'version':'1.0-shadow','affects_ranking':False,
      'regret_make_transfer':round(make,2),'regret_save_ft':round(save,2),'regret_gap_save_minus_make':round(gap,2),
      'verdict':verdict,'inputs':{'bench_adjusted_next_gw_gain':round(nextg,2),'three_gw_gain':round(three,2),'plan_gain':round(horizon,2),'necessity':necessity,'information_value':round(info,2),'budget_lock_risk':round(lock,2),'robustness':rob.get('label')}
    }

d['transfer_regret_model']={'version':'1.0-shadow','affects_transfer_ranking':False,'candidate_count':len(cands),'purpose':'Sammenligner risikoen for å angre på å gjøre byttet mot risikoen for å angre på å spare FT. Brukes som konservativt sikkerhets-/forklaringslag.'}
P.write_text(json.dumps(d,ensure_ascii=False,indent=2))
print('Transfer regret enriched',len(cands))

"""Decision Confidence Breakdown v1.
Explains where pre-deadline confidence comes from. Safety/explainability layer only.
"""
import json
from pathlib import Path
P=Path('data.json'); d=json.loads(P.read_text()); cands=d.get('candidates') or []

def n(v,default=0.0):
    try:return float(v)
    except:return default

def clamp(v,a=0,b=1): return max(a,min(b,v))

for c in cands:
    ba=c.get('bench_adjustment_shadow') or {}
    rob=c.get('robustness_shadow') or {}
    tim=c.get('timing_value_shadow') or {}
    nec=c.get('transfer_necessity_shadow') or {}
    reg=c.get('transfer_regret_shadow') or {}
    ab=c.get('absence_severity_shadow') or {}
    opt=c.get('option_value_shadow') or {}
    nextg=n(ba.get('bench_adjusted_next_gw_gain'),n(c.get('short_gain')))
    three=n(ba.get('bench_adjusted_short_gain'),n(c.get('short_gain')))
    horizon=n(ba.get('bench_adjusted_horizon_gain'),n(c.get('horizon_gain')))
    sports=clamp(.50 + nextg*.10 + three*.035)
    long_term=clamp(.48 + three*.05 + horizon*.018)
    minutes=clamp(n(ab.get('availability_used'),100)/100*.60 + clamp(n(ab.get('expected_minutes_used'),75)/90)*.40)
    bench_cover=clamp(.72 - (.22 if ba.get('applied') and nextg<=.25 else 0) + clamp(nextg/5)*.18)
    robustness={'ROBUST':.90,'BLANDET':.62,'FRAGIL':.28}.get(rob.get('label'),.55)
    budget=clamp(.78 - .28*n(tim.get('lock_risk')) + .12*clamp(n(opt.get('total'))))
    ft_flex={'SPAR FT':.30,'LUKSUSBYTTE':.48,'FORNUFTIG':.72,'NØDVENDIG':.88}.get(nec.get('label'),.55)
    info=clamp(1-n(tim.get('information_value'))*.58)
    regret=clamp(1-n(reg.get('regret_make_transfer'),.5)*.55 + n(reg.get('regret_save_ft'),.5)*.20)
    iq=n((d.get('decision_layer') or {}).get('input_quality',{}).get('score'),.65)
    data_quality=clamp(iq)
    comps={'kortsiktig_sportslig':sports,'langsiktig_verdi':long_term,'spilletid_og_fravaer':minutes,'benkedekning':bench_cover,'robusthet':robustness,'budsjett_og_pris':budget,'ft_fleksibilitet':ft_flex,'informasjonsklarhet':info,'angerrisiko':regret,'datakvalitet':data_quality}
    weights={'kortsiktig_sportslig':.15,'langsiktig_verdi':.16,'spilletid_og_fravaer':.11,'benkedekning':.08,'robusthet':.12,'budsjett_og_pris':.08,'ft_fleksibilitet':.10,'informasjonsklarhet':.08,'angerrisiko':.07,'datakvalitet':.05}
    total=sum(comps[k]*weights[k] for k in weights)
    weakest=sorted(comps.items(),key=lambda kv:kv[1])[:3]
    c['decision_confidence_shadow']={'version':'1.0-shadow','affects_ranking':False,'score':round(total,2),'components':{k:round(v,2) for k,v in comps.items()},'weakest':[{'key':k,'score':round(v,2)} for k,v in weakest]}

d['decision_confidence_model']={'version':'1.0-shadow','affects_transfer_ranking':False,'candidate_count':len(cands),'purpose':'Bryter total sikkerhet ned i sportslig verdi, fravær, benk, robusthet, økonomi, FT-fleksibilitet, informasjon, angerrisiko og datakvalitet.'}
P.write_text(json.dumps(d,ensure_ascii=False,indent=2))
print('Decision confidence enriched',len(cands))

"""Classify absence severity and replacement urgency for transfer candidates.
Shadow safety layer: may inform/downgrade decisions, never promote ranking.
"""
import json
from pathlib import Path

P=Path('data.json'); d=json.loads(P.read_text())
cands=d.get('candidates') or []

for c in cands:
    out=c.get('out') or {}
    avail=float(out.get('availability') if out.get('availability') is not None else 100)
    mins=float(out.get('expected_minutes') or out.get('minutes') or 0)
    news=' '.join(str(out.get(k) or '') for k in ('news','status','chance_of_playing','return_date')).lower()
    bench=c.get('bench_adjustment_shadow') or c.get('bench_replacement_shadow') or {}
    bench_gain=bench.get('bench_adjusted_next_gw_gain')
    horizon=float(c.get('horizon_gain') or c.get('edge') or 0)

    confirmed_long=any(x in news for x in ('suspended','three matches','3 matches','long-term','long term','several weeks','months'))
    confirmed_short=any(x in news for x in ('one match','1 match','this gameweek','ruled out'))
    doubt=any(x in news for x in ('doubt','50%','75%','knock','assessment','late test'))

    if confirmed_long or (avail<=5 and mins<=1 and horizon>=1.5):
        severity='HØY'; urgency='HØY'
        reason='Fraværet ser betydelig ut over flere runder, så salg kan være viktig selv med brukbar benk.'
    elif confirmed_short or (avail<=20 and mins<=1):
        severity='MIDDELS'; urgency='MIDDELS'
        reason='Spilleren ser ut til å miste neste kamp; benkedekning og fler-GW-verdi avgjør om FT bør brukes.'
    elif doubt or avail<80 or mins<60:
        severity='USIKKER'; urgency='LAV/MIDDELS'
        reason='Det er usikkerhet rundt tilgjengelighet/minutter. Vent på ferskere lagnytt når timing tillater det.'
    else:
        severity='LAV'; urgency='LAV'
        reason='Ingen sterk fraværsgrunn til å selge; trekket må forsvares av sportslig fler-GW-gevinst.'

    if bench_gain is not None and float(bench_gain)<=0 and urgency!='HØY':
        urgency='LAV'
        reason += ' Benken dekker neste runde godt nok til at hastebehovet reduseres.'

    c['absence_severity_shadow']={
        'version':'1.0-shadow','affects_ranking':False,'severity':severity,'replacement_urgency':urgency,
        'availability_used':avail,'expected_minutes_used':mins,'bench_adjusted_next_gw_gain':bench_gain,
        'reason':reason
    }

d['absence_severity_model']={'version':'1.0-shadow','affects_transfer_ranking':False,'candidate_count':len(cands),
 'purpose':'Skiller bekreftet/langvarig fravær fra én kamp ute, tvil og vanlig minuttrisiko; brukes som sikkerhetsinformasjon.'}
P.write_text(json.dumps(d,ensure_ascii=False,indent=2))
print('Absence severity enriched',len(cands),'candidates')

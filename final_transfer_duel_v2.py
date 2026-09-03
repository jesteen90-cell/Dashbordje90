"""Bench- and necessity-aware final pre-deadline duel.
Compares candidate #1, candidate #2 and BANK on one conservative decision surface.
"""
import json
from pathlib import Path
P=Path('data.json'); d=json.loads(P.read_text()); cands=d.get('candidates') or []
prod=d.get('decision_layer') or {}; fg=d.get('final_transfer_gate') or {}

def n(v,default=0.0):
    try:return float(v)
    except:return default

def pair_label(c):
    ps=c.get('pairs') or []
    if not ps:return 'Ukjent kandidat'
    return ' + '.join(f"{(x.get('out') or {}).get('name','?')} → {(x.get('in') or {}).get('name','?')}" for x in ps)

def row(c,rank):
    bench=c.get('bench_adjustment_shadow') or {}; nec=c.get('transfer_necessity_shadow') or {}
    raw1=n((c.get('robustness_shadow') or {}).get('weighted_gain',{}).get('gw1'))
    adj1=n(bench.get('bench_adjusted_next_gw_gain'),raw1)
    short=n(bench.get('bench_adjusted_short_gain'),c.get('short_gain'))
    horizon=n(bench.get('bench_adjusted_horizon_gain'),c.get('horizon_gain'))
    option=c.get('option_value_shadow') or {}; timing=c.get('timing_value_shadow') or {}; robust=c.get('robustness_shadow') or {}
    return {'kind':'transfer','rank':rank,'label':pair_label(c),'production_edge':round(n(c.get('edge')),2),
        'next_gw_gain_raw':round(raw1,2),'next_gw_gain_after_bench':round(adj1,2),
        'three_gw_gain_after_bench':round(short,2),'plan_gain_after_bench':round(horizon,2),
        'bank_after':c.get('bank_after'),'bench_cover':bench.get('bench_cover_player'),'bench_cover_expected':bench.get('bench_cover_expected'),
        'bench_adjustment_applied':bool(bench.get('applied')),'robustness':robust.get('label'),
        'timing':timing.get('label') or timing.get('recommendation'),'option_value':option.get('total'),
        'necessity':nec.get('label'),'necessity_score':nec.get('score'),'necessity_reasons':nec.get('reasons') or [],
        'status':c.get('status'),'gate_misses':c.get('gate_misses') or []}

selection=d.get('candidate_selection') or {}; ranked_selection=selection.get('rows') or []
selected_candidates=[]
for item in ranked_selection[:2]:
    idx=item.get('candidate_index')
    if idx is not None and 0<=int(idx)<len(cands):selected_candidates.append(cands[int(idx)])
if not selected_candidates:selected_candidates=cands[:2]
rows=[row(c,i+1) for i,c in enumerate(selected_candidates)]
bank={'kind':'bank','rank':0,'label':'SPAR GRATISBYTTET','production_edge':0.0,'next_gw_gain_raw':0.0,'next_gw_gain_after_bench':0.0,
      'three_gw_gain_after_bench':0.0,'plan_gain_after_bench':0.0,'bank_after':(d.get('budget') or {}).get('bank'),
      'bench_cover':None,'bench_cover_expected':None,'bench_adjustment_applied':False,'robustness':'BASELINE',
      'timing':'VENT / BEHOLD INFOFORDEL','option_value':0.45,'necessity':'BASELINE','necessity_score':0.0,
      'necessity_reasons':['Beholder gratisbyttet og maksimal fleksibilitet til neste runde.'],'status':'BASELINE','gate_misses':[]}
rows.append(bank)
best=rows[0] if rows and rows[0]['kind']=='transfer' else None; second=rows[1] if len(rows)>1 and rows[1]['kind']=='transfer' else None
approved=bool(prod.get('approved_first_move')); warnings=[]; blockers=[]
if not approved:blockers.append('Produksjonsmodellen godkjenner ikke et bytte nå.')
if best:
    if best['necessity']=='SPAR FT': blockers.append('Kandidat #1 er klassifisert SPAR FT av nødvendighetsmodellen.')
    elif best['necessity']=='LUKSUSBYTTE': warnings.append('Kandidat #1 er et luksusbytte og må slå SPAR FT med tydelig margin.')
    if best['next_gw_gain_after_bench'] < 0: warnings.append('Benkedekningen er så god at kandidat #1 taper forventet lagscore i neste runde.')
    elif best['next_gw_gain_after_bench'] < .5: warnings.append('Benkedekningen spiser opp nesten hele gevinsten i neste runde.')
    if best['three_gw_gain_after_bench'] < 1.0: warnings.append('Benkekorrigert gevinst over tre runder er liten.')
    if best['robustness']=='FRAGIL': blockers.append('Kandidat #1 er fragil på tvers av tidshorisonter.')
    if best['timing'] and 'VENT' in str(best['timing']).upper(): warnings.append('Timinglaget anbefaler å vente på mer informasjon.')
if second and best:
    gap=best['plan_gain_after_bench']-second['plan_gain_after_bench']
    if abs(gap)<.35:warnings.append('Kandidat #1 og #2 er nesten like etter benkekorreksjon.')
else:gap=None
base_verdict=fg.get('verdict') or ('GO' if approved else 'NO-GO')
if blockers or base_verdict=='NO-GO': verdict='NO-GO'
elif warnings or base_verdict=='WAIT / RECHECK': verdict='WAIT / RECHECK'
elif base_verdict=='GO' and approved: verdict='GO'
else: verdict='NO-GO'
if not approved: verdict='NO-GO'
confidence=n(fg.get('confidence'),.5)
if warnings:confidence=min(confidence,.72)
if blockers:confidence=min(confidence,.40)
d['final_transfer_duel']={'version':'2.1-necessity-aware','affects_transfer_ranking':False,'production_approved':approved,
    'verdict':verdict,'confidence':round(confidence,2),'rows':rows,'candidate_1_vs_2_bench_adjusted_plan_gap':round(gap,2) if gap is not None else None,
    'warnings':warnings,'blockers':blockers,'explanation':'Sammenligner de to beste byttene mot å spare FT med benkedekning og byttenødvendighet inkludert.',
    'rule':'Kan bare gjøre produksjonsbeslutningen mer konservativ; kan aldri promotere et avvist bytte.'}
P.write_text(json.dumps(d,ensure_ascii=False,indent=2)); print('Final transfer duel v2.1',d['final_transfer_duel'])

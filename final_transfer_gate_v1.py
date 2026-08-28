"""Final pre-deadline transfer safety gate.

Combines production decision with conservative shadow evidence. Shadow layers may
only downgrade a transfer. The final gate is authoritative for dashboard headline.
"""
import json
from pathlib import Path

P=Path('data.json'); d=json.loads(P.read_text())
cands=d.get('candidates') or []
prod=d.get('decision_layer') or {}
approved=bool(prod.get('approved_first_move'))
threshold=float(prod.get('threshold') or 0)
weighted=float((d.get('decision_explanation') or {}).get('weighted_gain') or 0)
margin=weighted-threshold
best=cands[0] if cands else {}
second=cands[1] if len(cands)>1 else {}
rob=(best.get('robustness_shadow') or {})
timing=(best.get('timing_value_shadow') or {})
option=(best.get('option_value_shadow') or {})
bench=(best.get('bench_replacement_shadow') or {})

gw=int(d.get('gw') or 0)
source_gw=int(d.get('source_snapshot_gw') or 0)
early_season=source_gw <= 3
# Early season: require more evidence before spending a FT. This does not alter xP;
# it raises the decision hurdle while roles/minutes/team strength are less certain.
early_penalty=0.30 if source_gw <= 1 else 0.20 if source_gw == 2 else 0.10 if source_gw == 3 else 0.0
adjusted_margin=margin-early_penalty

best_edge=float(best.get('edge') or 0); second_edge=float(second.get('edge') or -99)
separation=best_edge-second_edge if second else 99
blockers=[]; warnings=[]
if not approved: blockers.append('Produksjonsmodellen godkjenner ikke første trekk.')
if rob.get('label')=='FRAGIL': blockers.append('Beste kandidat er negativ i minst én tidshorisont.')
elif rob.get('label')=='BLANDET': warnings.append('Tidshorisontene er ikke helt enige.')
if adjusted_margin < .20: warnings.append('Fordelen over å spare byttet er for liten etter usikkerhetsmargin.')
if second and separation < .20: warnings.append('Kandidat #1 og #2 ligger svært tett.')
if float(timing.get('information_value') or 0) >= .65: warnings.append('Det er høy verdi i å vente på mer lag-/skadeinformasjon.')
if float(timing.get('lock_risk') or 0) >= .70: warnings.append('Pris/budsjett kan låse trekket dersom du venter.')
# If bench correction says the immediate gain disappears, explicitly surface it.
bench_gain=bench.get('bench_adjusted_next_gw_gain')
if bench_gain is not None and float(bench_gain) <= 0:
    warnings.append('Benkedekning fjerner den kortsiktige gevinsten ved trekket.')
if early_season:
    warnings.append(f'Tidlig sesong: bare GW{source_gw} er tilgjengelig som ferskt resultatsnapshot, så beviskravet er høyere.')

if blockers: verdict='NO-GO'
elif warnings: verdict='WAIT / RECHECK'
else: verdict='GO'
if not approved: verdict='NO-GO'

confidence=max(0,min(1,.55 + max(-.2,min(.25,adjusted_margin*.12)) + (.12 if rob.get('label')=='ROBUST' else -.08 if rob.get('label')=='FRAGIL' else 0) + (.08 if separation>=.35 else -.06 if separation<.20 else 0)))
if early_season: confidence=min(confidence,.72)
if warnings: confidence=min(confidence,.74)
if blockers: confidence=min(confidence,.45)

headline={'GO':'GJØR BYTTET','WAIT / RECHECK':'VENT – SJEKK IGJEN','NO-GO':'IKKE GJØR BYTTET'}[verdict]
d['headline']=headline
d['final_transfer_gate']={
 'version':'2.0-authoritative-early-season','production_approved':approved,'verdict':verdict,
 'authoritative_headline':headline,'confidence':round(confidence,2),
 'production_margin_vs_bank':round(margin,2),'early_season_uncertainty_penalty':early_penalty,
 'adjusted_margin_vs_bank':round(adjusted_margin,2),
 'candidate_1_vs_2_edge_gap':round(separation,2) if second else None,
 'robustness':rob.get('label'),'timing_recommendation':timing.get('recommendation'),
 'option_value_total':option.get('total'),'bench_adjusted_next_gw_gain':bench_gain,
 'blockers':blockers,'warnings':warnings,
 'rule':'Final Gate controls the headline. Shadow layers may downgrade GO to WAIT/NO-GO, never promote a production-rejected transfer.'
}
P.write_text(json.dumps(d,ensure_ascii=False,indent=2))
print('Final transfer gate',d['final_transfer_gate'])

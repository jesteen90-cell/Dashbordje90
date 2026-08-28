"""Final pre-deadline transfer safety gate.

Combines the validated production decision with shadow evidence from cross-horizon
robustness, option value and timing. Shadow layers may downgrade confidence / advise
waiting, but may not invent or promote a transfer that production rejected.
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

# Candidate separation is deliberately based on the production edge, not shadow scores.
best_edge=float(best.get('edge') or 0); second_edge=float(second.get('edge') or -99)
separation=best_edge-second_edge if second else 99
blockers=[]; warnings=[]
if not approved: blockers.append('Produksjonsmodellen godkjenner ikke første trekk.')
if rob.get('label')=='FRAGIL': blockers.append('Beste kandidat er negativ i minst én tidshorisont.')
elif rob.get('label')=='BLANDET': warnings.append('Tidshorisontene er ikke helt enige.')
if margin < .20: warnings.append('Fordelen over BANK-terskelen er liten.')
if second and separation < .20: warnings.append('Kandidat #1 og #2 ligger svært tett.')
if float(timing.get('information_value') or 0) >= .65: warnings.append('Det er høy verdi i å vente på mer lag-/skadeinformasjon.')
if float(timing.get('lock_risk') or 0) >= .70: warnings.append('Pris/budsjett kan låse trekket dersom du venter.')

if blockers: verdict='NO-GO'
elif warnings: verdict='WAIT / RECHECK'
else: verdict='GO'

# Shadow safety layers can only make the instruction more conservative.
if not approved: verdict='NO-GO'
confidence=max(0,min(1,.55 + max(-.2,min(.25,margin*.12)) + (.12 if rob.get('label')=='ROBUST' else -.08 if rob.get('label')=='FRAGIL' else 0) + (.08 if separation>=.35 else -.06 if separation<.20 else 0)))
if warnings: confidence=min(confidence,.74)
if blockers: confidence=min(confidence,.45)

d['final_transfer_gate']={
 'version':'1.0-predeadline','production_approved':approved,'verdict':verdict,
 'confidence':round(confidence,2),'production_margin_vs_bank':round(margin,2),
 'candidate_1_vs_2_edge_gap':round(separation,2) if second else None,
 'robustness':rob.get('label'),'timing_recommendation':timing.get('recommendation'),
 'option_value_total':option.get('total'),'blockers':blockers,'warnings':warnings,
 'rule':'Shadow layers may downgrade GO to WAIT/NO-GO, never promote a production-rejected transfer.'
}
P.write_text(json.dumps(d,ensure_ascii=False,indent=2))
print('Final transfer gate',d['final_transfer_gate'])

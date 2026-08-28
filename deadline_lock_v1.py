"""Deadline Lock v1.
Final conservative lock on top of Final Gate using confidence, necessity and regret.
May only downgrade a decision; never promotes a production-rejected transfer.
"""
import json
from pathlib import Path
P=Path('data.json'); d=json.loads(P.read_text()); cands=d.get('candidates') or []
fg=d.get('final_transfer_gate') or {}; prod=d.get('decision_layer') or {}
best=cands[0] if cands else {}
conf=best.get('decision_confidence_shadow') or {}
nec=best.get('transfer_necessity_shadow') or {}
reg=best.get('transfer_regret_shadow') or {}
tim=best.get('timing_value_shadow') or {}
approved=bool(prod.get('approved_first_move'))
base=fg.get('verdict') or ('GO' if approved else 'NO-GO')
score=float(conf.get('score') or 0)
make=float(reg.get('regret_make_transfer') or .5); save=float(reg.get('regret_save_ft') or .5)
label=nec.get('label')
info=float(tim.get('information_value') or 0)
lock=float(tim.get('lock_risk') or 0)
blockers=[]; warnings=[]
if not approved: blockers.append('Produksjonsmodellen avviser trekket.')
if base=='NO-GO': blockers.append('Final Gate har allerede satt NO-GO.')
if label=='SPAR FT': blockers.append('Byttenødvendighet sier SPAR FT.')
if make-save >= .12: blockers.append('Angrerisikoen ved å gjøre byttet er klart høyere enn ved å spare.')
if score < .58: blockers.append('Samlet beslutningssikkerhet er for lav for deadline-lock.')
elif score < .68: warnings.append('Beslutningssikkerheten er middels og krever ny kontroll før bekreftelse.')
if make-save >= .05: warnings.append('Angrerisikoen ved å gjøre byttet er høyere enn ved å spare.')
if label=='LUKSUSBYTTE': warnings.append('Dette er fortsatt et luksusbytte.')
if info>=.65 and lock<.70: warnings.append('Mer informasjon har høy verdi og prisrisikoen forsvarer ikke tidlig handling.')
if base=='WAIT / RECHECK': warnings.append('Final Gate ber fortsatt om ny kontroll.')
if blockers: verdict='LOCKED / NO-GO'
elif warnings: verdict='UNLOCKED ONLY AFTER RECHECK'
elif base=='GO' and score>=.68 and save-make>=-.04: verdict='UNLOCKED / GO'
else: verdict='UNLOCKED ONLY AFTER RECHECK'
headline={'LOCKED / NO-GO':'IKKE GJØR BYTTET','UNLOCKED ONLY AFTER RECHECK':'VENT – SJEKK IGJEN','UNLOCKED / GO':'GJØR BYTTET'}[verdict]
# Deadline Lock becomes final display authority, but never upgrades a rejected production decision.
if not approved:
    verdict='LOCKED / NO-GO'; headline='IKKE GJØR BYTTET'
d['headline']=headline
d['deadline_lock']={'version':'1.0-predeadline','affects_transfer_ranking':False,'production_approved':approved,'verdict':verdict,'headline':headline,'confidence_score':round(score,2),'necessity':label,'regret_make_transfer':round(make,2),'regret_save_ft':round(save,2),'information_value':round(info,2),'budget_lock_risk':round(lock,2),'blockers':blockers,'warnings':warnings,'rule':'Deadline Lock may downgrade Final Gate but can never promote a production-rejected transfer.'}
P.write_text(json.dumps(d,ensure_ascii=False,indent=2))
print('Deadline lock',d['deadline_lock'])

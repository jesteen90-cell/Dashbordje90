"""Final pre-deadline transfer safety gate.
Combines production decision with conservative shadow evidence. Shadow layers may
only downgrade a transfer. Final Gate controls the dashboard headline.
"""
import json
from pathlib import Path
P=Path('data.json'); d=json.loads(P.read_text()); cands=d.get('candidates') or []
prod=d.get('decision_layer') or {}; approved=bool(prod.get('approved_first_move'))
threshold=float(prod.get('threshold') or 0); weighted=float((d.get('decision_explanation') or {}).get('weighted_gain') or 0); margin=weighted-threshold
best=cands[0] if cands else {}; second=cands[1] if len(cands)>1 else {}
rob=best.get('robustness_shadow') or {}; timing=best.get('timing_value_shadow') or {}; option=best.get('option_value_shadow') or {}; bench=best.get('bench_adjustment_shadow') or {}; necessity=best.get('transfer_necessity_shadow') or {}; regret=best.get('transfer_regret_shadow') or {}
source_gw=int(d.get('source_snapshot_gw') or 0); early_season=source_gw<=3; early_penalty=.30 if source_gw<=1 else .20 if source_gw==2 else .10 if source_gw==3 else 0
adjusted_margin=margin-early_penalty
best_edge=float(best.get('edge') or 0); second_edge=float(second.get('edge') or -99); separation=best_edge-second_edge if second else 99
blockers=[]; warnings=[]; go_triggers=[]; recheck=[]
if not approved: blockers.append('Produksjonsmodellen godkjenner ikke første trekk.')
if rob.get('label')=='FRAGIL': blockers.append('Beste kandidat er negativ i minst én tidshorisont.')
elif rob.get('label')=='BLANDET': warnings.append('Tidshorisontene er ikke helt enige.')
necessity_label=necessity.get('label'); necessity_score=necessity.get('score')
if necessity_label=='SPAR FT': blockers.append('Nødvendighetsmodellen vurderer at gratisbyttet har større strategisk verdi enn dette trekket.'); go_triggers.append('GO krever at byttenødvendigheten løftes over SPAR FT.')
elif necessity_label=='LUKSUSBYTTE': warnings.append('Trekket er et luksusbytte, ikke en nødvendig reparasjon.'); go_triggers.append('Et luksusbytte krever tydelig merverdi mot SPAR FT før GO.')
elif necessity_label=='FORNUFTIG': warnings.append('Trekket er fornuftig, men ikke så nødvendig at andre varselsignaler kan ignoreres.')
if adjusted_margin<.20: warnings.append('Fordelen over å spare byttet er for liten etter usikkerhetsmargin.'); go_triggers.append('GO krever justert fordel mot SPAR FT på minst +0,20 p.')
if second and separation<.20: warnings.append('Kandidat #1 og #2 ligger svært tett.'); go_triggers.append('GO blir sterkere når kandidat #1 skiller minst +0,20 p fra #2.')
info=float(timing.get('information_value') or 0); lock=float(timing.get('lock_risk') or 0)
if info>=.65: warnings.append('Det er høy verdi i å vente på mer lag-/skadeinformasjon.'); recheck.append('Kjør ny vurdering etter siste skade-/lagnytt før deadline.')
if lock>=.70: warnings.append('Pris/budsjett kan låse trekket dersom du venter.'); recheck.append('Kontroller prispress og bankmargin før du venter videre.')
bench_gain=bench.get('bench_adjusted_next_gw_gain')
if bench_gain is not None and float(bench_gain)<=0: warnings.append('Benkedekning fjerner den kortsiktige gevinsten ved trekket.'); go_triggers.append('GO krever tydelig fler-GW-gevinst som forsvarer FT-en.')
# Regret protection is authoritative only as a brake. It can never create GO.
rmake=regret.get('regret_make_transfer'); rsave=regret.get('regret_save_ft'); rverdict=regret.get('verdict')
if rmake is not None and rsave is not None:
    rgap=float(rmake)-float(rsave)
    if rgap>=.12:
        blockers.append(f'Angrerisikoen er klart høyere ved å gjøre byttet ({float(rmake)*100:.0f} %) enn ved å spare FT ({float(rsave)*100:.0f} %).')
        go_triggers.append('GO krever at angrerisikoen ved BYTT ikke lenger er klart høyere enn ved SPAR FT.')
    elif rgap>=.05:
        warnings.append(f'Angrerisikoen heller mot SPAR FT ({float(rmake)*100:.0f} % ved bytt mot {float(rsave)*100:.0f} % ved spar).')
        recheck.append('Revurder angrerisiko etter fersk laginfo og oppdaterte fler-GW-prognoser.')
    elif float(rsave)-float(rmake)>=.12:
        # supportive evidence only; never removes other warnings/blockers
        pass
if early_season: warnings.append(f'Tidlig sesong: bare GW{source_gw} er tilgjengelig som ferskt resultatsnapshot, så beviskravet er høyere.'); recheck.append('Oppdater etter ny bekreftet informasjon om minutter, roller og skader.')
if blockers: verdict='NO-GO'
elif warnings: verdict='WAIT / RECHECK'
else: verdict='GO'
if not approved: verdict='NO-GO'
confidence=max(0,min(1,.55+max(-.2,min(.25,adjusted_margin*.12))+(.12 if rob.get('label')=='ROBUST' else -.08 if rob.get('label')=='FRAGIL' else 0)+(.08 if separation>=.35 else -.06 if separation<.20 else 0)))
if necessity_label=='NØDVENDIG': confidence=min(1,confidence+.05)
elif necessity_label=='LUKSUSBYTTE': confidence=min(confidence,.68)
elif necessity_label=='SPAR FT': confidence=min(confidence,.45)
if rmake is not None and rsave is not None and float(rmake)>float(rsave): confidence=min(confidence,.66)
if early_season: confidence=min(confidence,.72)
if warnings: confidence=min(confidence,.74)
if blockers: confidence=min(confidence,.45)
headline={'GO':'GJØR BYTTET','WAIT / RECHECK':'VENT – SJEKK IGJEN','NO-GO':'IKKE GJØR BYTTET'}[verdict]
next_action='Byttet har passert siste sikkerhetskontroll. Kontroller bare at ingen ny lagnyhet har kommet før bekreftelse.' if verdict=='GO' else ('Ikke bruk gratisbyttet på dette trekket nå. Behold FT med mindre nye data endrer beslutningen.' if verdict=='NO-GO' else 'Vent med å bekrefte. Kjør ny vurdering når recheck-punktene er oppdatert.')
d['headline']=headline; d['final_transfer_gate']={'version':'2.3-regret-aware','production_approved':approved,'verdict':verdict,'authoritative_headline':headline,'confidence':round(confidence,2),'production_margin_vs_bank':round(margin,2),'early_season_uncertainty_penalty':early_penalty,'adjusted_margin_vs_bank':round(adjusted_margin,2),'candidate_1_vs_2_edge_gap':round(separation,2) if second else None,'robustness':rob.get('label'),'timing_recommendation':timing.get('recommendation'),'option_value_total':option.get('total'),'bench_adjusted_next_gw_gain':bench_gain,'transfer_necessity':necessity_label,'transfer_necessity_score':necessity_score,'regret_make_transfer':rmake,'regret_save_ft':rsave,'regret_verdict':rverdict,'blockers':blockers,'warnings':warnings,'go_triggers':go_triggers[:7],'recheck_conditions':recheck[:6],'next_action':next_action,'rule':'Final Gate controls headline. Necessity, regret and other shadow layers may downgrade GO to WAIT/NO-GO, never promote a production-rejected transfer.'}
P.write_text(json.dumps(d,ensure_ascii=False,indent=2)); print('Final transfer gate',d['final_transfer_gate'])

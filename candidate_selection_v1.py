"""Select the most decision-ready transfer candidate on one common surface."""
import json
from pathlib import Path

P=Path('data.json'); d=json.loads(P.read_text()); candidates=d.get('candidates') or []
def n(v,default=0.0):
    try:return float(v)
    except (TypeError,ValueError):return default
def clamp(v,a=0.0,b=1.0):return max(a,min(b,v))
def signature(c):return '|'.join(sorted(f"{int((p.get('out') or {}).get('id') or 0)}>{int((p.get('in') or {}).get('id') or 0)}" for p in c.get('pairs') or []))
def label(c):return ' + '.join(f"{(p.get('out') or {}).get('name','?')} → {(p.get('in') or {}).get('name','?')}" for p in c.get('pairs') or []) or 'Ingen kandidat'

rows=[]
for idx,c in enumerate(candidates):
    bench=c.get('bench_adjustment_shadow') or {}; robust=c.get('robustness_shadow') or {}; timing=c.get('timing_value_shadow') or {}; option=c.get('option_value_shadow') or {}; regret=c.get('transfer_regret_shadow') or {}; confidence=c.get('decision_confidence_shadow') or {}
    incoming=[p.get('in') or {} for p in c.get('pairs') or []]
    availability=min((n(p.get('availability'),1) for p in incoming),default=1); minutes=min((n(p.get('expected_minutes'),90) for p in incoming),default=90)
    next_gain=n(bench.get('bench_adjusted_next_gw_gain'),n(c.get('short_gain'))); three_gain=n(bench.get('bench_adjusted_short_gain'),n(c.get('short_gain'))); plan_gain=n(bench.get('bench_adjusted_horizon_gain'),n(c.get('horizon_gain')))
    reliability=clamp(n(confidence.get('score'),.5))*(.62+.38*availability)*(.72+.28*clamp(minutes/75))
    if robust.get('label')=='FRAGIL':reliability*=.72
    elif robust.get('label')=='BLANDET':reliability*=.88
    info_penalty=.55*n(timing.get('information_value')); option_delta=n(option.get('vs_bank')); regret_delta=n(regret.get('regret_save_ft'))-n(regret.get('regret_make_transfer'))
    score=(.22*next_gain+.34*three_gain+.18*plan_gain)*(.55+.45*reliability)+.45*option_delta+.70*regret_delta-info_penalty
    rows.append({'candidate_index':idx,'signature':signature(c),'label':label(c),'decision_score':round(score,3),'reliability':round(reliability,3),'availability_floor':round(availability,3),'minutes_floor':round(minutes,1),'next_gw_gain_after_bench':round(next_gain,2),'three_gw_gain_after_bench':round(three_gain,2),'plan_gain_after_bench':round(plan_gain,2),'information_penalty':round(info_penalty,3),'option_value_vs_bank':round(option_delta,3),'regret_advantage_vs_bank':round(regret_delta,3)})
rows.sort(key=lambda x:(x['decision_score'],x['reliability']),reverse=True); selected=rows[0] if rows else None
plan0=((d.get('optimizer') or {}).get('plan') or [{}])[0]; plan_sig='|'.join(sorted(f"{int((p.get('out') or {}).get('id') or 0)}>{int((p.get('in') or {}).get('id') or 0)}" for p in plan0.get('pairs') or []))
d['candidate_selection']={'version':'1.0-decision-ready','method':'bench + horizons + reliability + option value + timing + regret','selected_candidate_index':selected['candidate_index'] if selected else None,'selected_signature':selected['signature'] if selected else '','selected_label':selected['label'] if selected else 'Ingen kandidat','agrees_with_optimizer_first_move':bool(selected and selected['signature'] and selected['signature']==plan_sig),'automatic_go_requires_optimizer_agreement':True,'rows':rows}
P.write_text(json.dumps(d,ensure_ascii=False,indent=2)); print('Candidate selection',d['candidate_selection'])

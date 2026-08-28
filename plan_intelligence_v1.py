import json
from pathlib import Path

P=Path('data.json')
d=json.loads(P.read_text())
future=d.get('future') or []
start_ft=max(1,min(5,int(d.get('free_transfers_assumed') or 1)))
ft=start_ft
prev_bank=float((d.get('budget') or {}).get('bank') or 0)

# Index candidate/player context for explanatory labels.
cands=d.get('candidates') or []
by_id={}
for c in cands:
    for pair in c.get('pairs') or []:
        for side in ('out','in'):
            p=pair.get(side) or {}
            if p.get('id') is not None: by_id[int(p['id'])]=p

for row in future:
    action=row.get('action') or {}
    transfers=int(action.get('transfers') or 0)
    hit=int(action.get('hit') or 0)
    ft_before=ft
    if transfers:
        used_free=min(ft,transfers)
        ft_after=max(0,ft-transfers)+1
    else:
        used_free=0
        ft_after=min(5,ft+1)
    bank_after=float(row.get('bank') if row.get('bank') is not None else prev_bank)
    bank_delta=round(bank_after-prev_bank,1)
    reasons=[]; triggers=[]
    if action.get('action')=='bank':
        reasons.append('Sparer gratisbyttet for å få mer handlingsrom i senere runder.')
        triggers.append('Ny skade, suspensjon eller tydelig rolleendring kan gjøre et tidligere bytte riktig.')
    else:
        pairs=action.get('pairs') or []
        for pair in pairs:
            o,i=pair.get('out') or {},pair.get('in') or {}
            reasons.append(f"Planlagt {o.get('name','?')} → {i.get('name','?')} for å forbedre fler-runders forventet verdi.")
        if hit:
            reasons.append(f'Trekket koster {hit} poeng og må derfor gi ekstra stor fler-runders gevinst.')
        if bank_delta>0: reasons.append(f'Trekket frigjør omtrent £{bank_delta:.1f}m til senere oppgraderinger.')
        if bank_delta<0: reasons.append(f'Trekket bruker omtrent £{abs(bank_delta):.1f}m av bankreserven.')
        triggers.append('Planen revurderes hvis forventede minutter, skadebildet eller priser endrer seg før den aktuelle fristen.')
    score=float(row.get('xi_xp') or 0)
    conf='MIDDELS'
    if action.get('action')=='bank': conf='HØY'
    if hit: conf='LAVERE'
    row['plan_intelligence']={
        'version':'1.0',
        'free_transfers_before':ft_before,
        'free_transfers_used':used_free,
        'free_transfers_after':min(5,ft_after),
        'bank_before':round(prev_bank,1),
        'bank_after':round(bank_after,1),
        'bank_change':bank_delta,
        'expected_team_score':round(score,1),
        'confidence':conf,
        'why':reasons[:4],
        'change_triggers':triggers[:3],
        'note':'Dette er en rullerende plan, ikke et løfte. Den bygges på nytt når ferske data kommer.'
    }
    ft=min(5,ft_after); prev_bank=bank_after

d['plan_intelligence']={
    'version':'1.0',
    'horizon_gws':[int(x.get('gw')) for x in future if x.get('gw') is not None],
    'purpose':'Forklare den beste fler-GW-ruten, budsjett, FT og hva som kan endre planen.',
    'rolling_plan':True,
    'start_free_transfers':start_ft
}
P.write_text(json.dumps(d,ensure_ascii=False,indent=2))
print('Plan intelligence enriched',len(future),'gameweeks')
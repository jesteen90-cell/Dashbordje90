import json
from pathlib import Path

P=Path('data.json')
d=json.loads(P.read_text())
current=((d.get('comparison') or {}).get('current_xi') or [])
bench=(d.get('confirmed_fpl') or {}).get('bench') or d.get('bench') or []
xi_ids={int(p.get('id')) for p in current if p.get('id') is not None}

def n(v,default=0.0):
    try:return float(v)
    except:return default

def legal_replacement(outp,b):
    # Conservative formation proxy: GK only replaces GK; outfield replacement must itself be outfield.
    if outp.get('position')=='GK': return b.get('position')=='GK'
    return b.get('position')!='GK'

def bench_cover(outp):
    if int(outp.get('id') or -1) not in xi_ids:return 0.0,None
    if n(outp.get('availability'),1)>=0.5 and n(outp.get('expected_minutes'),90)>=25:return 0.0,None
    opts=[]
    for b in bench:
        if not legal_replacement(outp,b):continue
        avail=n(b.get('availability'),1); mins=n(b.get('expected_minutes'),90); xp=n(b.get('xp'))
        if avail<=0 or mins<=0:continue
        # Expected contribution if autosub is needed; cap at player xP.
        contribution=xp*min(1.0,avail)*min(1.0,mins/70 if mins>0 else 0)
        opts.append((contribution,b))
    if not opts:return 0.0,None
    opts.sort(key=lambda x:x[0],reverse=True)
    return opts[0]

for c in d.get('candidates') or []:
    pairs=c.get('pairs') or []
    if len(pairs)!=1:
        c['bench_adjustment_shadow']={'version':'1.0','applied':False,'reason':'multi-transfer candidate','affects_ranking':False}
        continue
    pair=pairs[0]; outp=pair.get('out') or {}; inp=pair.get('in') or {}
    cover,coverp=bench_cover(outp)
    raw_next=n(inp.get('xp'))-n(outp.get('xp'))
    adjusted_next=n(inp.get('xp'))-max(n(outp.get('xp')),cover)
    short=n(c.get('short_gain')); horizon=n(c.get('horizon_gain'))
    # Only correct the immediate GW component. Later GWs keep the recovery-aware model values.
    delta=adjusted_next-raw_next
    c['bench_adjustment_shadow']={
        'version':'1.0','applied':cover>0,'affects_ranking':False,
        'bench_cover_player':coverp.get('name') if coverp else None,
        'bench_cover_expected':round(cover,2),
        'raw_next_gw_gain':round(raw_next,2),
        'bench_adjusted_next_gw_gain':round(adjusted_next,2),
        'adjustment':round(delta,2),
        'bench_adjusted_short_gain':round(short+delta,2),
        'bench_adjusted_horizon_gain':round(horizon+delta,2),
        'note':'Skadebytter sammenlignes mot forventet autosub-verdi når utgående spiller sannsynligvis ikke spiller.'
    }

d['bench_replacement_model']={'version':'1.0-shadow','affects_transfer_ranking':False,'current_xi_players':len(current),'bench_players':len(bench),'purpose':'Unngå at skadebytter overvurderes ved å sammenligne mot mulig benkeinnhopp.'}
P.write_text(json.dumps(d,ensure_ascii=False,indent=2))
print('Bench replacement audit enriched')
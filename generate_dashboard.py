from __future__ import annotations
import itertools, json, math, os
from datetime import datetime, timezone
from pathlib import Path
import requests

BASE='https://fantasy.premierleague.com/api'
TEAM_ID=int(os.environ['FPL_TEAM_ID'])
OUT=Path('data.json')
HORIZON=6
WEIGHTS=[1.00,.90,.80,.70,.62,.55]
POS={1:'GK',2:'DEF',3:'MID',4:'FWD'}

def get(path, optional=False):
    try:
        r=requests.get(f"{BASE}/{path.lstrip('/')}",headers={'Accept':'application/json','User-Agent':'fpl-dashboard-public/2.0'},timeout=30)
        r.raise_for_status(); return r.json()
    except Exception:
        if optional:return None
        raise

def num(v,d=0.0):
    try:return float(v)
    except:return d

def clamp(v,lo=0,hi=1):return max(lo,min(hi,v))
def avail(p):
    if p.get('status') in ('u','s'):return 0.0
    c=p.get('chance_of_playing_next_round')
    if c is not None:return clamp(num(c)/100)
    if p.get('status') in ('i','d'):return .55
    return 1.0

def conf(p):
    starts=num(p.get('starts')); mins=num(p.get('minutes')); own=num(p.get('selected_by_percent'))
    m=clamp(mins/max(starts*90,270)) if mins else .55
    o=clamp(math.log1p(own)/math.log(31))
    return clamp(.45+.25*m+.15*o+.15*avail(p),.35,.95)

boot=get('bootstrap-static/'); fixtures=get('fixtures/')
players=boot.get('elements') or []; events=boot.get('events') or []; teamrows=boot.get('teams') or []
byid={int(p['id']):p for p in players}; teams={int(t['id']):t.get('name') for t in teamrows}
next_event=next((e for e in events if e.get('is_next')),None)
if not next_event:
    now=datetime.now(timezone.utc); upcoming=[]
    for e in events:
        try:
            d=datetime.fromisoformat(str(e.get('deadline_time')).replace('Z','+00:00'))
            if d>now:upcoming.append((d,e))
        except:pass
    next_event=min(upcoming,key=lambda x:x[0])[1] if upcoming else events[-1]
TARGET=int(next_event.get('id') or 1); deadline=next_event.get('deadline_time')
GWS=list(range(TARGET,min(38,TARGET+HORIZON-1)+1)); weights={g:WEIGHTS[i] for i,g in enumerate(GWS)}
fm={g:{} for g in GWS}
for f in fixtures:
    g=f.get('event')
    if g not in fm:continue
    fm[g].setdefault(int(f['team_h']),[]).append({'home':True,'opp':int(f['team_a']),'fdr':int(f.get('team_h_difficulty') or 3)})
    fm[g].setdefault(int(f['team_a']),[]).append({'home':False,'opp':int(f['team_h']),'fdr':int(f.get('team_a_difficulty') or 3)})
finished=sorted((int(e.get('id') or 0) for e in events if e.get('finished')),reverse=True)
tries=finished+[g for g in range(TARGET-1,0,-1) if g not in finished]
snapshot=snapshot_gw=None
for g in tries:
    s=get(f'entry/{TEAM_ID}/event/{g}/picks/',True)
    if s and len(s.get('picks') or [])==15:snapshot,snapshot_gw=s,g;break
if not snapshot:raise RuntimeError('No public squad snapshot available')
squad=[byid[int(x['element'])] for x in snapshot['picks'] if int(x['element']) in byid]
bank=int((snapshot.get('entry_history') or {}).get('bank') or 0)

def basexp(p):
    ep=num(p.get('ep_next')); form=num(p.get('form')); ppg=num(p.get('points_per_game')); price=num(p.get('now_cost'))/10; pos=int(p.get('element_type') or 0)
    floor={1:4,2:4,3:4.5,4:4.5}.get(pos,4); prior=3+max(price-floor,0)**.55*{1:.55,2:.70,3:.95,4:1}.get(pos,.7)
    cs=[(prior,.35)]+([(ep,.35)] if ep>0 else [])+([(form,.18)] if form>0 else [])+([(ppg,.12)] if ppg>0 else [])
    raw=sum(v*w for v,w in cs)/sum(w for _,w in cs); raw+=.28 if p.get('penalties_order')==1 else 0; raw+=.08 if p.get('corners_and_indirect_freekicks_order')==1 else 0
    return clamp(raw,1.5,9)

def project(p,g):
    fs=fm.get(g,{}).get(int(p['team']),[])
    total=0
    for f in fs:
        mult={1:1.2,2:1.1,3:1,4:.9,5:.8}.get(f['fdr'],1)*(1.035 if f['home'] else 1)
        total+=basexp(p)*mult*(.78+.22*conf(p))*avail(p)
    return clamp(total,0,14)
for p in players:
    p['_c']=conf(p); p['_x']={g:project(p,g) for g in GWS}; p['_h']=sum(p['_x'][g]*weights[g] for g in GWS)

def lineup(sq,g):
    bp={x:[p for p in sq if int(p['element_type'])==x] for x in (1,2,3,4)}; best=None
    for gk in itertools.combinations(bp[1],1):
      for nd in range(3,6):
       for nm in range(2,6):
        nf=10-nd-nm
        if not 1<=nf<=3 or nd>len(bp[2]) or nm>len(bp[3]) or nf>len(bp[4]):continue
        for ds in itertools.combinations(bp[2],nd):
         for ms in itertools.combinations(bp[3],nm):
          for fs in itertools.combinations(bp[4],nf):
           xi=list(gk+ds+ms+fs); score=sum(p['_x'][g] for p in xi)
           if best is None or score>best[0]:best=(score,xi)
    ordered=sorted(best[1],key=lambda p:(p['_x'][g],p['_c']),reverse=True)
    return {'raw':best[0],'xi':best[1],'captain':ordered[0],'vice':ordered[1]}

def score(sq,n=None):
    gs=GWS[:n] if n else GWS; total=0
    for g in gs:
        o=lineup(sq,g); total+=(o['raw']+o['captain']['_x'][g])*weights[g]
    return total

def legal(sq):
    if len(sq)!=15 or len({p['id'] for p in sq})!=15:return False
    if {x:sum(int(p['element_type'])==x for p in sq) for x in (1,2,3,4)}!={1:2,2:5,3:5,4:3}:return False
    c={}
    for p in sq:c[int(p['team'])]=c.get(int(p['team']),0)+1
    return max(c.values())<=3

def row(p,g):
    fs=fm.get(g,{}).get(int(p['team']),[]); fixture='BLANK' if not fs else ' + '.join(f"{teams.get(f['opp'],'?')} ({'H' if f['home'] else 'A'})" for f in fs)
    return {'name':p.get('web_name'),'position':POS[int(p['element_type'])],'xp':round(p['_x'][g],2),'fixture':fixture}

baseh=score(squad); base3=score(squad,3); ids={int(p['id']) for p in squad}; pools={}
for pos in (1,2,3,4):
    c=[p for p in players if int(p['element_type'])==pos and int(p['id']) not in ids and avail(p)>=.45]
    c.sort(key=lambda p:(p['_h'],p['_c'],-int(p['now_cost'])),reverse=True); pools[pos]=c[:30]
plans=[]
for out in squad:
    budget=bank+int(out['now_cost'])
    for inn in pools[int(out['element_type'])]:
        if int(inn['now_cost'])>budget:continue
        ns=[p for p in squad if int(p['id'])!=int(out['id'])]+[inn]
        if not legal(ns):continue
        h=score(ns); s3=score(ns,3); edge=h-baseh; short=s3-base3; cur=inn['_x'][TARGET]-out['_x'][TARGET]
        if edge<-.5:continue
        robust=(inn['_c']-out['_c'])*3+(avail(inn)-avail(out))*2
        plans.append({'out':out,'in':inn,'edge':edge,'short':short,'current':cur,'robust':robust})
plans.sort(key=lambda x:(x['edge']+.35*x['short']+.2*x['robust'],x['current']),reverse=True); plans=plans[:8]
cands=[]
for p in plans:
    if p['edge']>=4 and p['short']>=1.5 and p['current']>=-.25:status='GJØR DET'; misses=[]
    elif p['edge']>=1.5:
        status='VURDERES'; misses=[]
        if p['edge']<4:misses.append('Horisontfordel under +4.00')
        if p['short']<1.5:misses.append('3-GW fordel under +1.50')
    else:status='SVAK'; misses=['Fordelen er foreløpig for liten']
    cands.append({'status':status,'edge':round(p['edge'],2),'short_gain':round(p['short'],2),'horizon_gain':round(p['edge'],2),'gate_misses':misses,'pairs':[{'out':row(p['out'],TARGET),'in':row(p['in'],TARGET)}]})
best=plans[0] if plans else None; go=bool(best and best['edge']>=4 and best['short']>=1.5 and best['current']>=-.25)
rec_squad=squad
if go:rec_squad=[p for p in squad if int(p['id'])!=int(best['out']['id'])]+[best['in']]
cur=lineup(rec_squad,TARGET); xi={int(p['id']) for p in cur['xi']}; bench=[p for p in rec_squad if int(p['id']) not in xi]
future=[]
for g in GWS:
    o=lineup(rec_squad,g); future.append({'gw':g,'captain':o['captain'].get('web_name'),'captain_xp':round(o['captain']['_x'][g],2),'xi_xp':round(o['raw'],2)})
data={'generated_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'gw':TARGET,'deadline_time':deadline,'headline':'GJØR BYTTET' if go else 'VENT / BANK','summary':'Toppforslaget passerer modellens terskler og gir positiv forventet gevinst.' if go else 'Ingen kandidat har høy nok robust fordel akkurat nå.','source_snapshot_gw':snapshot_gw,'recommendation':{'edge':round(best['edge'],2) if best else 0,'transfers':[{'out':row(best['out'],TARGET),'in':row(best['in'],TARGET)}] if go else []},'lineup':[row(p,TARGET)|{'captain':int(p['id'])==int(cur['captain']['id']),'vice':int(p['id'])==int(cur['vice']['id'])} for p in cur['xi']],'bench':[row(p,TARGET) for p in bench],'candidates':cands,'future':future}
OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'Updated sanitized dashboard: GW{snapshot_gw} -> GW{TARGET}')
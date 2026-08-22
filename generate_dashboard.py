from __future__ import annotations
import itertools,json,math,os
from datetime import datetime,timezone
from pathlib import Path
import requests
from model_v2_core import project as core_project
from transfer_optimizer_v2 import optimize as optimize_transfers

BASE='https://fantasy.premierleague.com/api'; TEAM_ID=int(os.environ['FPL_TEAM_ID']); OUT=Path('data.json')
HORIZON=6; WEIGHTS=[1,.9,.8,.7,.62,.55]; POS={1:'GK',2:'DEF',3:'MID',4:'FWD'}

def get(path,optional=False):
 try:
  r=requests.get(f"{BASE}/{path.lstrip('/')}",headers={'Accept':'application/json','User-Agent':'fpl-autopilot-model-v2'},timeout=30);r.raise_for_status();return r.json()
 except Exception:
  if optional:return None
  raise

def n(v,d=0):
 try:return float(v)
 except:return d

def clamp(x,a=0,b=1):return max(a,min(b,x))
def parse_deadline(v):
 if not v:return None
 return datetime.fromisoformat(v.replace('Z','+00:00'))

boot=get('bootstrap-static/'); fixtures=get('fixtures/'); players=boot['elements']; events=boot['events']; teamrows=boot['teams']; byid={int(p['id']):p for p in players}; teams={int(t['id']):t['name'] for t in teamrows}
now=datetime.now(timezone.utc)
future_events=[e for e in events if parse_deadline(e.get('deadline_time')) and parse_deadline(e.get('deadline_time'))>now and not e.get('finished')]
next_event=min(future_events,key=lambda e:parse_deadline(e['deadline_time'])) if future_events else next((e for e in events if e.get('is_next')),None)
if not next_event:raise RuntimeError('No upcoming FPL deadline found')
TARGET=int(next_event['id']); deadline=next_event.get('deadline_time'); GWS=list(range(TARGET,min(38,TARGET+HORIZON-1)+1)); weights={g:WEIGHTS[i] for i,g in enumerate(GWS)}

fm={g:{} for g in GWS}
for f in fixtures:
 g=f.get('event')
 if g not in fm:continue
 fm[g].setdefault(int(f['team_h']),[]).append({'home':1,'opp':int(f['team_a']),'fdr':int(f.get('team_h_difficulty') or 3)})
 fm[g].setdefault(int(f['team_a']),[]).append({'home':0,'opp':int(f['team_h']),'fdr':int(f.get('team_a_difficulty') or 3)})

finished=sorted((int(e['id']) for e in events if e.get('finished')),reverse=True); snapshot=snapshot_gw=None
for g in finished+[x for x in range(TARGET-1,0,-1) if x not in finished]:
 s=get(f'entry/{TEAM_ID}/event/{g}/picks/',True)
 if s and len(s.get('picks',[]))==15:snapshot,snapshot_gw=s,g;break
if not snapshot:raise RuntimeError('No public squad snapshot')
squad=[byid[int(x['element'])] for x in snapshot['picks']]; bank=int(snapshot.get('entry_history',{}).get('bank') or 0)

def availability(p):
 if p.get('status') in ('u','s'):return 0
 c=p.get('chance_of_playing_next_round'); return clamp(n(c)/100) if c is not None else (.55 if p.get('status') in ('i','d') else 1)

def live_core_input(p,f):
 pos=int(p['element_type']); hist=n(p.get('minutes')); starts=n(p.get('starts')); rounds=max(TARGET-1,1)
 avg_start=78.0 if starts<=0 else clamp(hist/max(starts,1),55,88)
 residual=max(0,hist-starts*avg_start); sub_apps=residual/18 if residual else 0
 start_rate=clamp(starts/rounds,0,1); sub_rate=clamp(sub_apps/rounds,0,.6); scale=90/max(hist,180)
 attack={1:1.22,2:1.11,3:1,4:.89,5:.78}[f['fdr']]*(1.035 if f['home'] else .97)
 opp_lambda={1:.72,2:1.00,3:1.32,4:1.70,5:2.15}[f['fdr']]*(.93 if f['home'] else 1.07)
 return {'position':pos,'availability':availability(p),'start_rate':start_rate,'avg_start_mins':avg_start,'sub_rate':sub_rate,'avg_sub_mins':18,'minutes_history':hist,'goal90':n(p.get('goals_scored'))*scale,'assist90':n(p.get('assists'))*scale,'save90':n(p.get('saves'))*scale,'defcon90':n(p.get('defensive_contribution'))*scale,'bonus90':n(p.get('bonus'))*scale,'yellow90':n(p.get('yellow_cards'))*scale,'red90':n(p.get('red_cards'))*scale,'opponent_goal_lambda':opp_lambda,'attack_multiplier':attack}

def components(p,f):return core_project(live_core_input(p,f))
def project(p,g):
 comps=[components(p,f) for f in fm.get(g,{}).get(int(p['team']),[])]
 if not comps:return {'total':0,'xmins':0,'appearance':0,'goals':0,'assists':0,'clean_sheet':0,'saves':0,'defensive':0,'bonus':0,'conceded':0,'cards':0,'cs_probability':0}
 keys=('total','xmins','appearance','goals','assists','clean_sheet','saves','defensive','bonus','conceded','cards','cs_probability')
 return {k:sum(c.get(k,0) for c in comps) for k in keys}
for p in players:p['_proj']={g:project(p,g) for g in GWS};p['_x']={g:p['_proj'][g]['total'] for g in GWS};p['_h']=sum(p['_x'][g]*weights[g] for g in GWS)

def lineup(sq,g):
 bp={x:[p for p in sq if int(p['element_type'])==x] for x in (1,2,3,4)};best=None
 for gk in itertools.combinations(bp[1],1):
  for nd in range(3,6):
   for nm in range(2,6):
    nf=10-nd-nm
    if not 1<=nf<=3 or nd>len(bp[2]) or nm>len(bp[3]) or nf>len(bp[4]):continue
    for ds in itertools.combinations(bp[2],nd):
     for ms in itertools.combinations(bp[3],nm):
      for fs in itertools.combinations(bp[4],nf):
       xi=list(gk+ds+ms+fs);v=sum(p['_x'][g] for p in xi)
       if best is None or v>best[0]:best=(v,xi)
 ordered=sorted(best[1],key=lambda p:p['_x'][g],reverse=True);return {'raw':best[0],'xi':best[1],'captain':ordered[0],'vice':ordered[1]}

def row(p,g,change=None):
 fs=fm.get(g,{}).get(int(p['team']),[]);fixture='BLANK' if not fs else ' + '.join(f"{teams.get(f['opp'],'?')} ({'H' if f['home'] else 'A'})" for f in fs);c=p['_proj'][g]
 return {'id':int(p['id']),'name':p['web_name'],'team_id':int(p['team']),'team':teams[int(p['team'])],'position':POS[int(p['element_type'])],'price':round(n(p['now_cost'])/10,1),'xp':round(c['total'],2),'fixture':fixture,'availability':round(availability(p),3),'expected_minutes':round(c['xmins'],1),'news':p.get('news') or '','change':change,'xp_breakdown':{k:round(c.get(k,0),2) for k in ('appearance','goals','assists','clean_sheet','saves','defensive','bonus','conceded','cards')}}

# Multi-GW optimizer is now the source of the primary transfer plan.
opt_players=[p for p in players if availability(p)>=.5 or int(p['id']) in {int(x['id']) for x in squad}]
opt=optimize_transfers(opt_players,squad,bank,GWS,weights,free_transfers=1,beam_width=60,per_pos=18,save_ft_value=.55)
plan_moves=opt['moves']; first=plan_moves[0] if plan_moves else {'gw':TARGET,'action':'bank'}
first_transfer=first if first.get('gw')==TARGET and first.get('action')=='transfer' else None
outp=byid.get(int(first_transfer['out'])) if first_transfer else None; inp=byid.get(int(first_transfer['in'])) if first_transfer else None
transfer_squad=([p for p in squad if int(p['id'])!=int(outp['id'])]+[inp]) if first_transfer else squad
current_o=lineup(squad,TARGET); transfer_o=lineup(transfer_squad,TARGET)
current_gain=(inp['_x'][TARGET]-outp['_x'][TARGET]) if first_transfer else 0
plan_gain=float(opt.get('gain',0))
go=bool(first_transfer and plan_gain>1.0)

def xi_rows(o,change_id=None,change_label=None):return [row(p,TARGET,change_label if change_id is not None and p['id']==change_id else None)|{'captain':p['id']==o['captain']['id'],'vice':p['id']==o['vice']['id']} for p in o['xi']]

def move_public(m):
 if m.get('action')=='bank':return {'gw':m['gw'],'action':'bank','label':'Spar gratisbyttet'}
 o=byid[int(m['out'])];i=byid[int(m['in'])]
 return {'gw':m['gw'],'action':'transfer','out':{'id':int(o['id']),'name':o['web_name'],'team':teams[int(o['team'])]},'in':{'id':int(i['id']),'name':i['web_name'],'team':teams[int(i['team'])]},'label':f"{o['web_name']} → {i['web_name']}"}
transfer_plan=[move_public(m) for m in plan_moves]

# Keep a shortlist of simple current-GW alternatives for transparency.
cands=[];ids={int(p['id']) for p in squad}
for out in squad:
 budget=bank+int(out['now_cost'])
 choices=[p for p in players if int(p['element_type'])==int(out['element_type']) and int(p['id']) not in ids and int(p['now_cost'])<=budget and availability(p)>=.5]
 choices.sort(key=lambda p:p['_h'],reverse=True)
 for inn in choices[:8]:
  ns=[p for p in squad if p['id']!=out['id']]+[inn]
  if not __import__('transfer_optimizer_v2').legal(ns):continue
  gain=sum((inn['_x'][g]-out['_x'][g])*weights[g] for g in GWS)
  cands.append({'status':'VURDERES' if gain>.5 else 'SVAK','edge':round(gain-.55,2),'short_gain':round(sum(inn['_x'][g]-out['_x'][g] for g in GWS[:3]),2),'horizon_gain':round(gain,2),'gate_misses':[] if gain>1 else ['Fordelen er liten sammenlignet med fleksibiliteten i å spare et gratisbytte'],'pairs':[{'out':row(out,TARGET),'in':row(inn,TARGET)}]})
cands.sort(key=lambda c:c['horizon_gain'],reverse=True);cands=cands[:10]

future=[];sim_squad=list(squad)
for g in GWS:
 m=next((x for x in plan_moves if x.get('gw')==g),None)
 if m and m.get('action')=='transfer':sim_squad=[p for p in sim_squad if int(p['id'])!=int(m['out'])]+[byid[int(m['in'])]]
 o=lineup(sim_squad,g);future.append({'gw':g,'captain':o['captain']['web_name'],'captain_xp':round(o['captain']['_x'][g],2),'xi_xp':round(o['raw'],2),'action':move_public(m) if m else {'gw':g,'action':'bank','label':'Ingen planlagt handling'}})

headline='GJØR BYTTET' if go else ('SPAR BYTTET' if first.get('action')=='bank' else 'VENT / BANK')
summary=('Multi-GW-optimalisatoren anbefaler et bytte nå og vurderer samtidig de neste rundene.' if go else 'Multi-GW-optimalisatoren mener fleksibiliteten i å spare gratisbyttet er mer verdifull akkurat nå.')
data={'model_version':'2.2-multi-gw','generated_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'gw':TARGET,'deadline_time':deadline,'headline':headline,'summary':summary,'source_snapshot_gw':snapshot_gw,
 'optimizer':{'horizon_gws':GWS,'weighted_gain':round(plan_gain,2),'bank_after':round(opt['bank']/10,1),'free_transfers_after':opt['free_transfers'],'plan':transfer_plan},
 'recommendation':{'edge':round(plan_gain,2),'transfers':[{'out':row(outp,TARGET),'in':row(inp,TARGET)}] if go else []},
 'comparison':{'status':'GJØR DET' if go else 'BANK','out':row(outp,TARGET) if outp else None,'in':row(inp,TARGET) if inp else None,'current_xi':xi_rows(current_o,outp['id'] if outp else None,'out'),'transfer_xi':xi_rows(transfer_o,inp['id'] if inp else None,'in')},
 'lineup':xi_rows(transfer_o if go else current_o),'bench':[row(p,TARGET) for p in (transfer_squad if go else squad) if p['id'] not in {x['id'] for x in (transfer_o if go else current_o)['xi']}],
 'candidates':cands,'future':future}
OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');print('Model v2.2 multi-GW projection complete')
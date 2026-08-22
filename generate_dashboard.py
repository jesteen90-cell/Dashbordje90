from __future__ import annotations
import itertools,json,math,os
from datetime import datetime,timezone
from pathlib import Path
import requests
from model_v2_core import project as core_project
from transfer_optimizer_v2 import optimize as optimize_transfers, legal
BASE='https://fantasy.premierleague.com/api';TEAM_ID=int(os.environ['FPL_TEAM_ID']);OUT=Path('data.json');DEFAULT_WEIGHTS=[1,.9,.8,.7,.62,.55];POS={1:'GK',2:'DEF',3:'MID',4:'FWD'};Z80=1.2815515655446004
def get(path,optional=False):
 try:r=requests.get(f"{BASE}/{path.lstrip('/')}",headers={'Accept':'application/json','User-Agent':'fpl-autopilot-model-v2.4'},timeout=30);r.raise_for_status();return r.json()
 except Exception:
  if optional:return None
  raise
def n(v,d=0):
 try:return float(v)
 except:return d
def clamp(x,a=0,b=1):return max(a,min(b,x))
def dt(v):return datetime.fromisoformat(v.replace('Z','+00:00')) if v else None
def strategy_weights():
 p=Path('transfer_strategy_params.json')
 if p.exists():
  try:
   w=[float(v) for v in json.loads(p.read_text()).get('weights',[])];return w[:6] if len(w)>=3 else DEFAULT_WEIGHTS
  except Exception:pass
 return DEFAULT_WEIGHTS
boot=get('bootstrap-static/');fixtures=get('fixtures/');players=boot['elements'];events=boot['events'];teams={int(t['id']):t['name'] for t in boot['teams']};byid={int(p['id']):p for p in players};now=datetime.now(timezone.utc);future=[e for e in events if dt(e.get('deadline_time')) and dt(e['deadline_time'])>now and not e.get('finished')];event=min(future,key=lambda e:dt(e['deadline_time'])) if future else next((e for e in events if e.get('is_next')),None)
if not event:raise RuntimeError('No upcoming FPL deadline')
TARGET=int(event['id']);deadline=event['deadline_time'];W=strategy_weights();GWS=list(range(TARGET,min(38,TARGET+len(W)-1)+1));weights={g:W[i] for i,g in enumerate(GWS)};fm={g:{} for g in GWS}
for f in fixtures:
 g=f.get('event')
 if g not in fm:continue
 fm[g].setdefault(int(f['team_h']),[]).append({'home':1,'opp':int(f['team_a']),'fdr':int(f.get('team_h_difficulty') or 3)});fm[g].setdefault(int(f['team_a']),[]).append({'home':0,'opp':int(f['team_h']),'fdr':int(f.get('team_a_difficulty') or 3)})
finished=sorted((int(e['id']) for e in events if e.get('finished')),reverse=True);snapshot=snapshot_gw=None
for g in finished+[x for x in range(TARGET-1,0,-1) if x not in finished]:
 s=get(f'entry/{TEAM_ID}/event/{g}/picks/',True)
 if s and len(s.get('picks',[]))==15:snapshot,snapshot_gw=s,g;break
if not snapshot:raise RuntimeError('No public squad snapshot')
squad=[byid[int(x['element'])] for x in snapshot['picks']];bank=int(snapshot.get('entry_history',{}).get('bank') or 0);free_transfers=max(1,min(5,int(os.environ.get('FPL_FREE_TRANSFERS','1'))))
def availability(p):
 if p.get('status') in ('u','s'):return 0
 c=p.get('chance_of_playing_next_round');return clamp(n(c)/100) if c is not None else (.55 if p.get('status') in ('i','d') else 1)
def core_input(p,f):
 pos=int(p['element_type']);hist=n(p.get('minutes'));starts=n(p.get('starts'));rounds=max(TARGET-1,1);avg_start=78 if starts<=0 else clamp(hist/max(starts,1),55,88);res=max(0,hist-starts*avg_start);sub_apps=res/18 if res else 0;scale=90/max(hist,180);attack={1:1.22,2:1.11,3:1,4:.89,5:.78}[f['fdr']]*(1.035 if f['home'] else .97);opp_lambda={1:.72,2:1.00,3:1.32,4:1.70,5:2.15}[f['fdr']]*(.93 if f['home'] else 1.07);return {'position':pos,'availability':availability(p),'start_rate':clamp(starts/rounds),'avg_start_mins':avg_start,'sub_rate':clamp(sub_apps/rounds,0,.6),'avg_sub_mins':18,'minutes_history':hist,'goal90':n(p.get('goals_scored'))*scale,'assist90':n(p.get('assists'))*scale,'save90':n(p.get('saves'))*scale,'defcon90':n(p.get('defensive_contribution'))*scale,'bonus90':n(p.get('bonus'))*scale,'yellow90':n(p.get('yellow_cards'))*scale,'red90':n(p.get('red_cards'))*scale,'opponent_goal_lambda':opp_lambda,'attack_multiplier':attack}
def project(p,g):
 cs=[core_project(core_input(p,f)) for f in fm.get(g,{}).get(int(p['team']),[])];keys=('total','xmins','appearance','goals','assists','clean_sheet','saves','defensive','bonus','conceded','cards','cs_probability')
 if not cs:return {**{k:0 for k in keys},'variance':0,'sd':0,'p10':0,'p90':0,'volatility':0}
 out={k:sum(c.get(k,0) for c in cs) for k in keys};out['variance']=sum(c.get('variance',0) for c in cs);out['sd']=math.sqrt(max(0,out['variance']));out['p10']=max(0,out['total']-Z80*out['sd']);out['p90']=max(out['p10'],out['total']+Z80*out['sd']);out['volatility']=out['sd']/max(out['total'],1);return out
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
def risk_label(c):
 v=c.get('volatility',0)
 return 'lav' if v<.65 else ('middels' if v<1.05 else 'høy')
def row(p,g,change=None):
 fs=fm.get(g,{}).get(int(p['team']),[]);fixture='BLANK' if not fs else ' + '.join(f"{teams.get(f['opp'],'?')} ({'H' if f['home'] else 'A'})" for f in fs);c=p['_proj'][g];return {'id':int(p['id']),'name':p['web_name'],'team_id':int(p['team']),'team':teams[int(p['team'])],'position':POS[int(p['element_type'])],'price':round(n(p['now_cost'])/10,1),'xp':round(c['total'],2),'xp_low':round(c['p10'],2),'xp_high':round(c['p90'],2),'risk':risk_label(c),'volatility':round(c['volatility'],2),'fixture':fixture,'availability':round(availability(p),3),'expected_minutes':round(c['xmins'],1),'news':p.get('news') or '','change':change,'xp_breakdown':{k:round(c.get(k,0),2) for k in ('appearance','goals','assists','clean_sheet','saves','defensive','bonus','conceded','cards')}}
def apply_move(sq,m):
 if not m or m.get('action')!='transfer':return list(sq)
 out=list(sq)
 for oid,iid in m.get('pairs',[]):out=[p for p in out if int(p['id'])!=int(oid)]+[byid[int(iid)]]
 return out
def public_move(m):
 if not m or m.get('action')=='bank':return {'gw':m.get('gw') if m else None,'action':'bank','transfers':0,'hit':0,'label':'Spar gratisbyttet'}
 pairs=[]
 for oid,iid in m.get('pairs',[]):
  o,i=byid[int(oid)],byid[int(iid)];pairs.append({'out':{'id':int(o['id']),'name':o['web_name'],'team':teams[int(o['team'])]},'in':{'id':int(i['id']),'name':i['web_name'],'team':teams[int(i['team'])]}})
 return {'gw':m['gw'],'action':'transfer','transfers':len(pairs),'hit':int(m.get('hit',0)),'pairs':pairs,'label':' + '.join(f"{x['out']['name']} → {x['in']['name']}" for x in pairs)+(f" (-{int(m.get('hit',0))})" if m.get('hit') else '')}
pool=[p for p in players if availability(p)>=.5 or int(p['id']) in {int(x['id']) for x in squad}];opt=optimize_transfers(pool,squad,bank,GWS,weights,free_transfers=free_transfers,beam_width=70,per_pos=12,save_ft_value=.45,hit_cost=4,max_transfers_per_gw=2);plan=opt['moves'];first=plan[0] if plan else {'gw':TARGET,'action':'bank'};first_pairs=first.get('pairs',[]) if first.get('action')=='transfer' else [];first_out=byid[first_pairs[0][0]] if first_pairs else None;first_in=byid[first_pairs[0][1]] if first_pairs else None;after=apply_move(squad,first);cur=lineup(squad,TARGET);aft=lineup(after,TARGET);gain=float(opt.get('gain',0));go=first.get('action')=='transfer' and gain>1
def xi_rows(o,outs=set(),ins=set()):return [row(p,TARGET,'out' if int(p['id']) in outs else ('in' if int(p['id']) in ins else None))|{'captain':p['id']==o['captain']['id'],'vice':p['id']==o['vice']['id']} for p in o['xi']]
outs={int(a) for a,b in first_pairs};ins={int(b) for a,b in first_pairs};future=[];sim=list(squad)
for g in GWS:
 m=next((x for x in plan if x.get('gw')==g),None);sim=apply_move(sim,m);o=lineup(sim,g);future.append({'gw':g,'captain':o['captain']['web_name'],'captain_xp':round(o['captain']['_x'][g],2),'captain_range':[round(o['captain']['_proj'][g]['p10'],2),round(o['captain']['_proj'][g]['p90'],2)],'xi_xp':round(o['raw'],2),'action':public_move(m)})
cands=[];ids={int(p['id']) for p in squad}
for outp in squad:
 budget=bank+int(outp['now_cost']);choices=[p for p in players if int(p['element_type'])==int(outp['element_type']) and int(p['id']) not in ids and int(p['now_cost'])<=budget and availability(p)>=.5];choices.sort(key=lambda p:p['_h'],reverse=True)
 for inn in choices[:6]:
  ns=[p for p in squad if p['id']!=outp['id']]+[inn]
  if not legal(ns):continue
  hg=sum((inn['_x'][g]-outp['_x'][g])*weights[g] for g in GWS);cands.append({'status':'VURDERES' if hg>.5 else 'SVAK','edge':round(hg-.45,2),'short_gain':round(sum(inn['_x'][g]-outp['_x'][g] for g in GWS[:3]),2),'horizon_gain':round(hg,2),'gate_misses':[] if hg>1 else ['Fordelen er liten sammenlignet med fleksibiliteten i å spare et gratisbytte'],'pairs':[{'out':row(outp,TARGET),'in':row(inn,TARGET)}]})
cands.sort(key=lambda x:x['horizon_gain'],reverse=True);cands=cands[:10];headline='GJØR BYTTET' if go else ('SPAR BYTTET' if first.get('action')=='bank' else 'VENT / BANK');summary='Modell v2.4 kombinerer kalibrert xP, fler-GW-strategi og prediktive poengintervaller. Intervallene viser usikkerhet, ikke et garantert minimum eller maksimum.'
data={'model_version':'2.4-risk','generated_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'gw':TARGET,'deadline_time':deadline,'headline':headline,'summary':summary,'source_snapshot_gw':snapshot_gw,'free_transfers_assumed':free_transfers,'optimizer':{'horizon_gws':GWS,'weights':[weights[g] for g in GWS],'weighted_gain':round(gain,2),'bank_after':round(opt['bank']/10,1),'free_transfers_after':opt['free_transfers'],'hit_points':opt.get('hit_points',0),'plan':[public_move(m) for m in plan]},'recommendation':{'edge':round(gain,2),'transfers':[{'out':row(byid[o],TARGET),'in':row(byid[i],TARGET)} for o,i in first_pairs] if go else []},'comparison':{'status':'GJØR DET' if go else 'BANK','out':row(first_out,TARGET) if first_out else None,'in':row(first_in,TARGET) if first_in else None,'changes':[{'out':row(byid[o],TARGET),'in':row(byid[i],TARGET)} for o,i in first_pairs],'current_xi':xi_rows(cur,outs=outs),'transfer_xi':xi_rows(aft,ins=ins)},'lineup':xi_rows(aft if go else cur,ins=ins if go else set()),'bench':[row(p,TARGET) for p in (after if go else squad) if p['id'] not in {x['id'] for x in (aft if go else cur)['xi']}],'candidates':cands,'future':future}
OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');print('Model v2.4 risk-aware feed complete')
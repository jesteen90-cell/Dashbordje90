from __future__ import annotations
import itertools,json,math,os
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from pathlib import Path
import requests
from model_v2_core import project as core_project
from transfer_optimizer_v2 import optimize as optimize_transfers,legal
from team_strength_v2 import build_strength,fixture_factors
from market_ensemble_v1 import load_market,blend_lambda
from player_form_v2 import form_signal
from recent_form_v2 import recent_signal,blend_rates,load_tuned_params
BASE='https://fantasy.premierleague.com/api';TEAM_ID=int(os.environ['FPL_TEAM_ID']);OUT=Path('data.json');DEFAULT_WEIGHTS=[1,.9,.8,.7,.62,.55];POS={1:'GK',2:'DEF',3:'MID',4:'FWD'};Z80=1.2815515655446004

def get(path,optional=False):
 try:r=requests.get(f"{BASE}/{path.lstrip('/')}",headers={'Accept':'application/json','User-Agent':'fpl-autopilot-model-v3.0'},timeout=18);r.raise_for_status();return r.json()
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
  except:pass
 return DEFAULT_WEIGHTS

def captain_params():
 p=Path('captain_v3_status.json')
 if not p.exists():return {'promote':False,'weights':{'xp':1,'ceiling':0,'minutes':0,'attack':0,'volatility_penalty':0}}
 try:
  d=json.loads(p.read_text());return {'promote':bool(d.get('promote')),'weights':d.get('weights') or {'xp':1,'ceiling':0,'minutes':0,'attack':0,'volatility_penalty':0}}
 except:return {'promote':False,'weights':{'xp':1,'ceiling':0,'minutes':0,'attack':0,'volatility_penalty':0}}

boot=get('bootstrap-static/');fixtures=get('fixtures/');players=boot['elements'];events=boot['events'];teams={int(t['id']):t['name'] for t in boot['teams']};byid={int(p['id']):p for p in players};ratings=build_strength(fixtures,teams);recent_cfg=load_tuned_params();cap_cfg=captain_params();market,market_status=load_market()
now=datetime.now(timezone.utc);future=[e for e in events if dt(e.get('deadline_time')) and dt(e['deadline_time'])>now and not e.get('finished')];event=min(future,key=lambda e:dt(e['deadline_time'])) if future else next((e for e in events if e.get('is_next')),None)
if not event:raise RuntimeError('No upcoming FPL deadline')
TARGET=int(event['id']);deadline=event['deadline_time'];W=strategy_weights();GWS=list(range(TARGET,min(38,TARGET+len(W)-1)+1));weights={g:W[i] for i,g in enumerate(GWS)};fm={g:{} for g in GWS};market_blends=[]
for f in fixtures:
 g=f.get('event')
 if g not in fm:continue
 fid=int(f.get('id') or 0);h=int(f['team_h']);a=int(f['team_a']);hatk,alam=fixture_factors(ratings,h,a,True);aatk,hlam=fixture_factors(ratings,a,h,False)
 # Market home_xg is the away team's opponent-goal lambda; market away_xg is the home team's opponent-goal lambda.
 hlam2,wh,mh=blend_lambda(hlam,fid,True,market);alam2,wa,ma=blend_lambda(alam,fid,False,market)
 if wh or wa:market_blends.append({'fixture_id':fid,'gw':g,'home_team':h,'away_team':a,'internal_home_xg':round(hlam,3),'internal_away_xg':round(alam,3),'market_home_xg':mh,'market_away_xg':ma,'home_weight':round(wh,3),'away_weight':round(wa,3),'ensemble_home_xg':round(hlam2,3),'ensemble_away_xg':round(alam2,3)})
 fm[g].setdefault(h,[]).append({'home':1,'opp':a,'attack':hatk,'opp_lambda':alam2});fm[g].setdefault(a,[]).append({'home':0,'opp':h,'attack':aatk,'opp_lambda':hlam2})
finished=sorted((int(e['id']) for e in events if e.get('finished')),reverse=True);snapshot=snapshot_gw=None
for g in finished+[x for x in range(TARGET-1,0,-1) if x not in finished]:
 s=get(f'entry/{TEAM_ID}/event/{g}/picks/',True)
 if s and len(s.get('picks',[]))==15:snapshot,snapshot_gw=s,g;break
if not snapshot:raise RuntimeError('No public squad snapshot')
squad=[byid[int(x['element'])] for x in snapshot['picks']];bank=int(snapshot.get('entry_history',{}).get('bank') or 0);free_transfers=max(1,min(5,int(os.environ.get('FPL_FREE_TRANSFERS','1'))))
squad_ids={int(p['id']) for p in squad};ranked=sorted(players,key=lambda p:n(p.get('total_points'))+2*n(p.get('form'))+n(p.get('selected_by_percent'))*.15,reverse=True);history_ids=squad_ids|{int(p['id']) for p in ranked[:140]};recent={}

def fetch_recent(pid):
 s=get(f'element-summary/{pid}/',True)
 return pid,recent_signal((s or {}).get('history',[]),params=recent_cfg)
with ThreadPoolExecutor(max_workers=12) as ex:
 futures=[ex.submit(fetch_recent,pid) for pid in history_ids]
 for fut in as_completed(futures):
  try:pid,val=fut.result();recent[pid]=val
  except Exception:pass
print(f'Loaded recent-form history for {len(recent)}/{len(history_ids)} players')

def availability(p):
 if p.get('status') in ('u','s'):return 0
 c=p.get('chance_of_playing_next_round');return clamp(n(c)/100) if c is not None else (.55 if p.get('status') in ('i','d') else 1)

def core_input(p,f):
 pos=int(p['element_type']);hist=n(p.get('minutes'));starts=n(p.get('starts'));rounds=max(TARGET-1,1);avg_start=78 if starts<=0 else clamp(hist/max(starts,1),55,88);res=max(0,hist-starts*avg_start);sub_apps=res/18 if res else 0;scale=90/max(hist,180)
 base={'position':pos,'availability':availability(p),'start_rate':clamp(starts/rounds),'avg_start_mins':avg_start,'sub_rate':clamp(sub_apps/rounds,0,.6),'avg_sub_mins':18,'minutes_history':hist,'goal90':n(p.get('goals_scored'))*scale,'assist90':n(p.get('assists'))*scale,'save90':n(p.get('saves'))*scale,'defcon90':n(p.get('defensive_contribution'))*scale,'bonus90':n(p.get('bonus'))*scale,'yellow90':n(p.get('yellow_cards'))*scale,'red90':n(p.get('red_cards'))*scale,'opponent_goal_lambda':f['opp_lambda'],'attack_multiplier':f['attack']}
 sf=form_signal(p);rf=recent.get(int(p['id']),{'multiplier':1,'confidence':0});adjusted,_=blend_rates(base,sf,rf,attack_share=float(recent_cfg.get('attack_share',.40)),enabled=bool(recent_cfg.get('promoted')));return adjusted

def project(p,g):
 cs=[core_project(core_input(p,f)) for f in fm.get(g,{}).get(int(p['team']),[])];keys=('total','xmins','appearance','goals','assists','clean_sheet','saves','defensive','bonus','conceded','cards','cs_probability')
 if not cs:return {**{k:0 for k in keys},'variance':0,'sd':0,'p10':0,'p90':0,'volatility':0,'attack_multiplier':0}
 out={k:sum(c.get(k,0) for c in cs) for k in keys};out['variance']=sum(c.get('variance',0) for c in cs);out['sd']=math.sqrt(max(0,out['variance']));out['p10']=max(0,out['total']-Z80*out['sd']);out['p90']=max(out['p10'],out['total']+Z80*out['sd']);out['volatility']=out['sd']/max(out['total'],1);fs=fm.get(g,{}).get(int(p['team']),[]);out['attack_multiplier']=sum(f['attack'] for f in fs)/len(fs) if fs else 0;return out

for p in players:p['_form']=form_signal(p);p['_recent']=recent.get(int(p['id']),{'multiplier':1,'xgi90':0,'minutes':0,'matches':0,'confidence':0});p['_proj']={g:project(p,g) for g in GWS};p['_x']={g:p['_proj'][g]['total'] for g in GWS};p['_h']=sum(p['_x'][g]*weights[g] for g in GWS)

def captain_score(p,g):
 c=p['_proj'][g];w=cap_cfg['weights'] if cap_cfg.get('promote') else {'xp':1,'ceiling':0,'minutes':0,'attack':0,'volatility_penalty':0}
 return n(w.get('xp'))*c['total']+n(w.get('ceiling'))*c['p90']+n(w.get('minutes'))*(c['xmins']/90)+n(w.get('attack'))*c.get('attack_multiplier',1)-n(w.get('volatility_penalty'))*c['volatility']

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
 ordered=sorted(best[1],key=lambda p:captain_score(p,g),reverse=True);return {'raw':best[0],'xi':best[1],'captain':ordered[0],'vice':ordered[1]}

def risk_label(c):
 v=c.get('volatility',0);return 'lav' if v<.65 else ('middels' if v<1.05 else 'høy')
def row(p,g,change=None):
 fs=fm.get(g,{}).get(int(p['team']),[]);fixture='BLANK' if not fs else ' + '.join(f"{teams.get(f['opp'],'?')} ({'H' if f['home'] else 'A'})" for f in fs);c=p['_proj'][g];f=p['_form'];rf=p['_recent']
 return {'id':int(p['id']),'name':p['web_name'],'team_id':int(p['team']),'team':teams[int(p['team'])],'position':POS[int(p['element_type'])],'price':round(n(p['now_cost'])/10,1),'xp':round(c['total'],2),'xp_low':round(c['p10'],2),'xp_high':round(c['p90'],2),'risk':risk_label(c),'volatility':round(c['volatility'],2),'fixture':fixture,'availability':round(availability(p),3),'expected_minutes':round(c['xmins'],1),'news':p.get('news') or '','change':change,'form':{'season_multiplier':round(f['multiplier'],3),'recent_multiplier':round(rf['multiplier'],3),'recent_xgi90':round(rf['xgi90'],3),'recent_minutes':round(rf['minutes'],0),'recent_matches':rf['matches'],'recent_confidence':round(rf['confidence'],3)},'xp_breakdown':{k:round(c.get(k,0),2) for k in ('appearance','goals','assists','clean_sheet','saves','defensive','bonus','conceded','cards')}}
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
pool=[p for p in players if availability(p)>=.5 or int(p['id']) in squad_ids];opt=optimize_transfers(pool,squad,bank,GWS,weights,free_transfers=free_transfers,beam_width=70,per_pos=12,save_ft_value=.45,hit_cost=4,max_transfers_per_gw=2);plan=opt['moves'];first=plan[0] if plan else {'gw':TARGET,'action':'bank'};first_pairs=first.get('pairs',[]) if first.get('action')=='transfer' else [];after=apply_move(squad,first);cur=lineup(squad,TARGET);aft=lineup(after,TARGET);gain=float(opt.get('gain',0));go=first.get('action')=='transfer' and gain>1
def xi_rows(o,outs=set(),ins=set()):return [row(p,TARGET,'out' if int(p['id']) in outs else ('in' if int(p['id']) in ins else None))|{'captain':p['id']==o['captain']['id'],'vice':p['id']==o['vice']['id']} for p in o['xi']]
outs={int(a) for a,b in first_pairs};ins={int(b) for a,b in first_pairs};future=[];sim=list(squad)
for g in GWS:
 m=next((x for x in plan if x.get('gw')==g),None);sim=apply_move(sim,m);o=lineup(sim,g);future.append({'gw':g,'captain':o['captain']['web_name'],'captain_xp':round(o['captain']['_x'][g],2),'captain_range':[round(o['captain']['_proj'][g]['p10'],2),round(o['captain']['_proj'][g]['p90'],2)],'xi_xp':round(o['raw'],2),'action':public_move(m)})
cands=[];ids=squad_ids
for outp in squad:
 budget=bank+int(outp['now_cost']);choices=[p for p in players if int(p['element_type'])==int(outp['element_type']) and int(p['id']) not in ids and int(p['now_cost'])<=budget and availability(p)>=.5];choices.sort(key=lambda p:p['_h'],reverse=True)
 for inn in choices[:6]:
  ns=[p for p in squad if p['id']!=outp['id']]+[inn]
  if not legal(ns):continue
  hg=sum((inn['_x'][g]-outp['_x'][g])*weights[g] for g in GWS);cands.append({'status':'VURDERES' if hg>.5 else 'SVAK','edge':round(hg-.45,2),'short_gain':round(sum(inn['_x'][g]-outp['_x'][g] for g in GWS[:3]),2),'horizon_gain':round(hg,2),'gate_misses':[] if hg>1 else ['Fordelen er liten sammenlignet med fleksibiliteten i å spare et gratisbytte'],'pairs':[{'out':row(outp,TARGET),'in':row(inn,TARGET)}]})
cands.sort(key=lambda x:x['horizon_gain'],reverse=True);cands=cands[:10];headline='GJØR BYTTET' if go else ('SPAR BYTTET' if first.get('action')=='bank' else 'VENT / BANK');strength_public={str(t):{'team':teams[t],**{k:round(v,3) for k,v in r.items()}} for t,r in ratings.items()}
data={'model_version':'3.1-market-ready','generated_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'gw':TARGET,'deadline_time':deadline,'headline':headline,'summary':'Modell 3.1 kombinerer intern lagstyrke med valgfri, konservativ bookmaker-xG ensemblekalibrering, recent-xGI, Captain v3, usikkerhet og fler-GW transferplanlegging.','source_snapshot_gw':snapshot_gw,'free_transfers_assumed':free_transfers,'market_ensemble':{**market_status,'active':bool(market_blends),'blend_count':len(market_blends),'method':'internal team-strength prior + confidence-bounded market xG'},'market_fixture_blends':market_blends,'team_strength':strength_public,'lineup':xi_rows(aft if go else cur,outs,ins),'bench':[row(p,TARGET) for p in (after if go else squad) if p not in (aft if go else cur)['xi']],'comparison':{'status':'GJØR DET' if go else 'BANK','changes':[{'out':row(byid[a],TARGET,'out'),'in':row(byid[b],TARGET,'in')} for a,b in first_pairs],'current_xi':xi_rows(cur,outs,ins),'transfer_xi':xi_rows(aft,outs,ins)},'recommendation':{'transfers':[public_move(first)] if go else []},'optimizer':{'weighted_gain':round(gain,2),'plan':[public_move(m) for m in plan]},'future':future,'candidates':cands,'recent_form':{'promoted':bool(recent_cfg.get('promoted'))},'captain_model':{'promoted':bool(cap_cfg.get('promote'))}}
OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');print('Wrote',OUT,'market active=',bool(market_blends))

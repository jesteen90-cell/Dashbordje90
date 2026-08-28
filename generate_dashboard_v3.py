from __future__ import annotations
import itertools,json,math,os
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
from pathlib import Path
import requests
from model_v2_core import project as core_project
from transfer_optimizer_v2 import optimize as optimize_transfers,legal,sale_value
from team_strength_v2 import build_strength,fixture_factors
from market_ensemble_v1 import load_market,blend_lambda
from player_form_v2 import form_signal
from recent_form_v2 import recent_signal,blend_rates,load_tuned_params
from availability_v1 import availability_for_gw,next_round_availability
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
  try:w=[float(v) for v in json.loads(p.read_text()).get('weights',[])];return w[:6] if len(w)>=3 else DEFAULT_WEIGHTS
  except:pass
 return DEFAULT_WEIGHTS

def captain_params():
 p=Path('captain_v3_status.json')
 if not p.exists():return {'promote':False,'weights':{'xp':1,'ceiling':0,'minutes':0,'attack':0,'volatility_penalty':0}}
 try:d=json.loads(p.read_text());return {'promote':bool(d.get('promote')),'weights':d.get('weights') or {'xp':1,'ceiling':0,'minutes':0,'attack':0,'volatility_penalty':0}}
 except:return {'promote':False,'weights':{'xp':1,'ceiling':0,'minutes':0,'attack':0,'volatility_penalty':0}}

def set_piece_params():
 p=Path('set_piece_roles.json')
 if not p.exists():return {'version':'missing','penalties':{}}
 try:return json.loads(p.read_text())
 except:return {'version':'invalid','penalties':{}}

def player_role_key(p):return f"{p.get('first_name','')} {p.get('second_name','')}".strip()

boot=get('bootstrap-static/');fixtures=get('fixtures/');players=boot['elements'];events=boot['events'];team_meta={int(t['id']):t for t in boot['teams']};teams={tid:t['name'] for tid,t in team_meta.items()};byid={int(p['id']):p for p in players};ratings=build_strength(fixtures,team_meta);recent_cfg=load_tuned_params();cap_cfg=captain_params();set_piece_cfg=set_piece_params();penalty_roles=set_piece_cfg.get('penalties') or {};market,market_status=load_market()
now=datetime.now(timezone.utc);future=[e for e in events if dt(e.get('deadline_time')) and dt(e['deadline_time'])>now and not e.get('finished')];event=min(future,key=lambda e:dt(e['deadline_time'])) if future else next((e for e in events if e.get('is_next')),None)
if not event:raise RuntimeError('No upcoming FPL deadline')
TARGET=int(event['id']);deadline=event['deadline_time'];W=strategy_weights();GWS=list(range(TARGET,min(38,TARGET+len(W)-1)+1));weights={g:W[i] for i,g in enumerate(GWS)};fm={g:{} for g in GWS};market_blends=[]
for f in fixtures:
 g=f.get('event')
 if g not in fm:continue
 fid=int(f.get('id') or 0);h=int(f['team_h']);a=int(f['team_a']);hatk,alam=fixture_factors(ratings,h,a,True);aatk,hlam=fixture_factors(ratings,a,h,False);hlam2,wh,mh=blend_lambda(hlam,fid,True,market);alam2,wa,ma=blend_lambda(alam,fid,False,market)
 if wh or wa:market_blends.append({'fixture_id':fid,'gw':g,'home_team':h,'away_team':a,'internal_home_xg':round(hlam,3),'internal_away_xg':round(alam,3),'market_home_xg':mh,'market_away_xg':ma,'home_weight':round(wh,3),'away_weight':round(wa,3),'ensemble_home_xg':round(hlam2,3),'ensemble_away_xg':round(alam2,3)})
 fm[g].setdefault(h,[]).append({'home':1,'opp':a,'attack':hatk,'opp_lambda':alam2});fm[g].setdefault(a,[]).append({'home':0,'opp':h,'attack':aatk,'opp_lambda':hlam2})
finished=sorted((int(e['id']) for e in events if e.get('finished')),reverse=True);snapshot=snapshot_gw=None
for g in finished+[x for x in range(TARGET-1,0,-1) if x not in finished]:
 s=get(f'entry/{TEAM_ID}/event/{g}/picks/',True)
 if s and len(s.get('picks',[]))==15:snapshot,snapshot_gw=s,g;break
if not snapshot:raise RuntimeError('No public squad snapshot')
pick_by_id={int(x['element']):x for x in snapshot['picks']}
squad=[]
for x in snapshot['picks']:
 p=dict(byid[int(x['element'])])
 if x.get('selling_price') is not None:p['selling_price']=int(x['selling_price'])
 if x.get('purchase_price') is not None:p['purchase_price']=int(x['purchase_price'])
 squad.append(p)
bank=int(snapshot.get('entry_history',{}).get('bank') or 0);free_transfers=max(1,min(5,int(os.environ.get('FPL_FREE_TRANSFERS','1'))));squad_ids={int(p['id']) for p in squad};ranked=sorted(players,key=lambda p:n(p.get('total_points'))+2*n(p.get('form'))+n(p.get('selected_by_percent'))*.15,reverse=True);history_ids=squad_ids|{int(p['id']) for p in ranked[:140]};recent={};previous={}

def fetch_recent(pid):
 s=get(f'element-summary/{pid}/',True) or {};past=s.get('history_past') or [];prev=past[-1] if past else {};pm=n(prev.get('minutes'));return pid,recent_signal(s.get('history',[]),params=recent_cfg),{'minutes':pm,'goal90':n(prev.get('goals_scored'))*90/max(pm,1) if pm else 0,'assist90':n(prev.get('assists'))*90/max(pm,1) if pm else 0}
with ThreadPoolExecutor(max_workers=12) as ex:
 futures=[ex.submit(fetch_recent,pid) for pid in history_ids]
 for fut in as_completed(futures):
  try:pid,val,prev=fut.result();recent[pid]=val;previous[pid]=prev
  except Exception:pass
print(f'Loaded recent/history priors for {len(recent)}/{len(history_ids)} players')
def availability(p,g=None):return availability_for_gw(p,TARGET,TARGET if g is None else g)
def penalty_share(p):return clamp(n(penalty_roles.get(player_role_key(p),0)))
def core_input(p,f,g):
 pos=int(p['element_type']);hist=n(p.get('minutes'));starts=n(p.get('starts'));rounds=max(TARGET-1,1);avg_start=78 if starts<=0 else clamp(hist/max(starts,1),55,88);res=max(0,hist-starts*avg_start);sub_apps=res/18 if res else 0;scale=90/max(hist,180);prev=previous.get(int(p['id']),{});rf=recent.get(int(p['id']),{'multiplier':1,'confidence':0,'minutes':0});base={'position':pos,'availability':availability(p,g),'start_rate':clamp(starts/rounds),'avg_start_mins':avg_start,'sub_rate':clamp(sub_apps/rounds,0,.6),'avg_sub_mins':18,'minutes_history':hist,'goal90':n(p.get('goals_scored'))*scale,'assist90':n(p.get('assists'))*scale,'prev_minutes':n(prev.get('minutes')),'prev_goal90':n(prev.get('goal90')),'prev_assist90':n(prev.get('assist90')),'recent_minutes':n(rf.get('minutes')),'recent_confidence':n(rf.get('confidence')),'save90':n(p.get('saves'))*scale,'defcon90':n(p.get('defensive_contribution'))*scale,'bonus90':n(p.get('bonus'))*scale,'yellow90':n(p.get('yellow_cards'))*scale,'red90':n(p.get('red_cards'))*scale,'penalty_taker_share':penalty_share(p),'opponent_goal_lambda':f['opp_lambda'],'attack_multiplier':f['attack']};sf=form_signal(p);adjusted,_=blend_rates(base,sf,rf,attack_share=float(recent_cfg.get('attack_share',.40)),enabled=bool(recent_cfg.get('promoted')));return adjusted
def project(p,g):
 cs=[core_project(core_input(p,f,g)) for f in fm.get(g,{}).get(int(p['team']),[])];keys=('total','xmins','appearance','goals','assists','clean_sheet','saves','defensive','bonus','conceded','cards','penalty','penalty_save','penalty_miss','cs_probability','goal90_used','assist90_used','goal_prior_used','assist_prior_used','attack_evidence_minutes')
 if not cs:return {**{k:0 for k in keys},'variance':0,'sd':0,'p10':0,'p90':0,'volatility':0,'attack_multiplier':0}
 out={k:sum(c.get(k,0) for c in cs) for k in keys};out['variance']=sum(c.get('variance',0) for c in cs);out['sd']=math.sqrt(max(0,out['variance']));out['p10']=max(0,out['total']-Z80*out['sd']);out['p90']=max(out['p10'],out['total']+Z80*out['sd']);out['volatility']=out['sd']/max(out['total'],1);fs=fm.get(g,{}).get(int(p['team']),[]);out['attack_multiplier']=sum(f['attack'] for f in fs)/len(fs) if fs else 0;return out
for p in players:p['_form']=form_signal(p);p['_recent']=recent.get(int(p['id']),{'multiplier':1,'xgi90':0,'minutes':0,'matches':0,'confidence':0});p['_proj']={g:project(p,g) for g in GWS};p['_x']={g:p['_proj'][g]['total'] for g in GWS};p['_h']=sum(p['_x'][g]*weights[g] for g in GWS)
# Keep owned copies on exactly the same projection surface while preserving live selling prices.
for p in squad:
 src=byid[int(p['id'])];p['_form']=src['_form'];p['_recent']=src['_recent'];p['_proj']=src['_proj'];p['_x']=src['_x'];p['_h']=src['_h']
def captain_score(p,g):
 c=p['_proj'][g];w=cap_cfg['weights'] if cap_cfg.get('promote') else {'xp':1,'ceiling':0,'minutes':0,'attack':0,'volatility_penalty':0};return n(w.get('xp'))*c['total']+n(w.get('ceiling'))*c['p90']+n(w.get('minutes'))*(c['xmins']/90)+n(w.get('attack'))*c.get('attack_multiplier',1)-n(w.get('volatility_penalty'))*c['volatility']
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
def risk_label(c):v=c.get('volatility',0);return 'lav' if v<.65 else ('middels' if v<1.05 else 'høy')
def fixture_outlook(p):
 out=[];tid=int(p['team'])
 for g in GWS[:3]:
  fs=fm.get(g,{}).get(tid,[])
  if not fs:out.append({'gw':g,'label':'BLANK','difficulty':5,'xp':0});continue
  for f in fs:
   opp=ratings.get(int(f['opp']),{});res=n(opp.get('away_defence' if f['home'] else 'home_defence'),1);raw=3+(res-1)*2.2+(-.22 if f['home'] else .22);difficulty=int(round(clamp(raw,1,5)));out.append({'gw':g,'label':f"{teams.get(f['opp'],'?')[:3].upper()} {'H' if f['home'] else 'A'}",'difficulty':difficulty,'xp':round(p['_x'].get(g,0),2),'availability':round(availability(p,g),3)})
 return out
def row(p,g,change=None):
 fs=fm.get(g,{}).get(int(p['team']),[]);fixture='BLANK' if not fs else ' + '.join(f"{teams.get(f['opp'],'?')} ({'H' if f['home'] else 'A'})" for f in fs);c=p['_proj'][g];f=p['_form'];rf=p['_recent'];prev=previous.get(int(p['id']),{});return {'id':int(p['id']),'name':p['web_name'],'team_id':int(p['team']),'team':teams[int(p['team'])],'position':POS[int(p['element_type'])],'price':round(n(p['now_cost'])/10,1),'selling_price':round(sale_value(p)/10,1) if int(p['id']) in squad_ids else None,'xp':round(c['total'],2),'xp_low':round(c['p10'],2),'xp_high':round(c['p90'],2),'risk':risk_label(c),'volatility':round(c['volatility'],2),'fixture':fixture,'fixture_outlook':fixture_outlook(p),'availability':round(availability(p,g),3),'expected_minutes':round(c['xmins'],1),'news':p.get('news') or '','change':change,'set_piece_role':{'penalty_taker_share':round(penalty_share(p),3),'source_version':set_piece_cfg.get('version')},'form':{'season_multiplier':round(f['multiplier'],3),'recent_multiplier':round(rf['multiplier'],3),'recent_xgi90':round(rf['xgi90'],3),'recent_minutes':round(rf['minutes'],0),'recent_matches':rf['matches'],'recent_confidence':round(rf['confidence'],3)},'historical_prior':{'prev_minutes':round(n(prev.get('minutes')),0),'prev_goal90':round(n(prev.get('goal90')),3),'prev_assist90':round(n(prev.get('assist90')),3),'goal_prior_used':round(c.get('goal_prior_used',0),3),'assist_prior_used':round(c.get('assist_prior_used',0),3)},'xp_breakdown':{k:round(c.get(k,0),2) for k in ('appearance','goals','assists','clean_sheet','saves','defensive','bonus','penalty','conceded','cards')}}
def apply_move(sq,m):
 if not m or m.get('action')!='transfer':return list(sq)
 out=list(sq)
 for oid,iid in m.get('pairs',[]):out=[p for p in out if int(p['id'])!=int(oid)]+[byid[int(iid)]]
 return out
def public_move(m):
 if not m or m.get('action')=='bank':return {'gw':m.get('gw') if m else None,'action':'bank','transfers':0,'hit':0,'label':'Spar gratisbyttet'}
 pairs=[]
 for oid,iid in m.get('pairs',[]):
  o=next((p for p in squad if int(p['id'])==int(oid)),byid[int(oid)]);i=byid[int(iid)]
  pairs.append({'out':{'id':int(o['id']),'name':o['web_name'],'team':teams[int(o['team'])],'price':round(n(o['now_cost'])/10,1),'selling_price':round(sale_value(o)/10,1)},'in':{'id':int(i['id']),'name':i['web_name'],'team':teams[int(i['team'])],'price':round(n(i['now_cost'])/10,1)}})
 return {'gw':m['gw'],'action':'transfer','transfers':len(pairs),'hit':int(m.get('hit',0)),'pairs':pairs,'label':' + '.join(f"{x['out']['name']} → {x['in']['name']}" for x in pairs)+(f" (-{int(m.get('hit',0))})" if m.get('hit') else '')}
pool=[p for p in players if availability(p,TARGET)>=.5 or int(p['id']) in squad_ids];opt=optimize_transfers(pool,squad,bank,GWS,weights,free_transfers=free_transfers,beam_width=70,per_pos=12,save_ft_value=.45,hit_cost=4,max_transfers_per_gw=2);plan=opt['moves'];first=plan[0] if plan else {'gw':TARGET,'action':'bank'};first_pairs=first.get('pairs',[]) if first.get('action')=='transfer' else [];after=apply_move(squad,first);cur=lineup(squad,TARGET);aft=lineup(after,TARGET);gain=float(opt.get('gain',0));go=first.get('action')=='transfer' and gain>1
def xi_rows(o,outs=set(),ins=set()):return [row(p,TARGET,'out' if int(p['id']) in outs else ('in' if int(p['id']) in ins else None))|{'captain':p['id']==o['captain']['id'],'vice':p['id']==o['vice']['id']} for p in o['xi']]
outs={int(a) for a,b in first_pairs};ins={int(b) for a,b in first_pairs};future=[];sim=list(squad);sim_bank=bank
for g in GWS:
 m=next((x for x in plan if x.get('gw')==g),None)
 if m and m.get('action')=='transfer':
  for oid,iid in m.get('pairs',[]):
   sold=next((p for p in sim if int(p['id'])==int(oid)),byid[int(oid)]);sim_bank+=sale_value(sold)-int(byid[int(iid)]['now_cost'])
 sim=apply_move(sim,m);o=lineup(sim,g);future.append({'gw':g,'captain':o['captain']['web_name'],'captain_xp':round(o['captain']['_x'][g],2),'captain_range':[round(o['captain']['_proj'][g]['p10'],2),round(o['captain']['_proj'][g]['p90'],2)],'xi_xp':round(o['raw'],2),'bank':round(sim_bank/10,1),'action':public_move(m)})
cands=[];ids=squad_ids
for outp in squad:
 budget=bank+sale_value(outp);choices=[p for p in players if int(p['element_type'])==int(outp['element_type']) and int(p['id']) not in ids and int(p['now_cost'])<=budget and availability(p,TARGET)>=.5];choices.sort(key=lambda p:p['_h'],reverse=True)
 for inn in choices[:6]:
  ns=[p for p in squad if p['id']!=outp['id']]+[inn]
  if not legal(ns):continue
  hg=sum((inn['_x'][g]-outp['_x'][g])*weights[g] for g in GWS);bank_after=bank+sale_value(outp)-int(inn['now_cost']);cands.append({'status':'VURDERES' if hg>.5 else 'SVAK','edge':round(hg-.45,2),'short_gain':round(sum(inn['_x'][g]-outp['_x'][g] for g in GWS[:3]),2),'horizon_gain':round(hg,2),'bank_after':round(bank_after/10,1),'gate_misses':[] if hg>1 else ['Fordelen er liten sammenlignet med fleksibiliteten i å spare et gratisbytte'],'pairs':[{'out':row(outp,TARGET),'in':row(inn,TARGET)}]})
cands.sort(key=lambda x:x['horizon_gain'],reverse=True);cands=cands[:10];headline='GJØR BYTTET' if go else ('SPAR BYTTET' if first.get('action')=='bank' else 'VENT / BANK')
def public_strength(r):return {k:(round(v,3) if isinstance(v,(int,float)) else v) for k,v in r.items()}
strength_public={str(t):{'team':teams[t],**public_strength(r)} for t,r in ratings.items()};sources=sorted({r.get('prior_source') for r in ratings.values() if r.get('prior_source')})
squad_market=sum(int(p['now_cost']) for p in squad);squad_sale=sum(sale_value(p) for p in squad);selling_live=all('selling_price' in p for p in squad)
data={'model_version':'3.8-availability-recovery-set-piece-projection','generated_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'gw':TARGET,'deadline_time':deadline,'headline':headline,'summary':'Modell 3.8 kombinerer GW-spesifikk skade/recovery, live salgspriser når FPL leverer dem, bekreftede strafferoller, adaptiv lagstyrke, recent-xGI og fler-GW transferplanlegging.','source_snapshot_gw':snapshot_gw,'free_transfers_assumed':free_transfers,'budget':{'bank':round(bank/10,1),'squad_market_value':round(squad_market/10,1),'squad_selling_value':round(squad_sale/10,1),'market_budget_total':round((squad_market+bank)/10,1),'selling_budget_total':round((squad_sale+bank)/10,1),'selling_value_live':selling_live},'availability_model':{'version':'1.0-gw-recovery','next_round_signal':'FPL chance_of_playing_next_round','future_absence_persistence':0.70},'set_piece_model':{'version':set_piece_cfg.get('version'),'projection_integration':'active','penalty_roles':len(penalty_roles)},'market_ensemble':{**market_status,'active':bool(market_blends),'blend_count':len(market_blends),'method':'adaptive internal team strength + confidence-bounded market xG'},'market_fixture_blends':market_blends,'team_strength_model':{'version':'2.1-adaptive-early-season','prior_sources':sources,'table_fallback_active':'table-shrunk' in sources},'team_strength':strength_public,'lineup':xi_rows(aft if go else cur,outs,ins),'bench':[row(p,TARGET) for p in (after if go else squad) if p not in (aft if go else cur)['xi']],'comparison':{'status':'GJØR DET' if go else 'BANK','changes':[{'out':row(next((p for p in squad if int(p['id'])==a),byid[a]),TARGET,'out'),'in':row(byid[b],TARGET,'in')} for a,b in first_pairs],'current_xi':xi_rows(cur,outs,ins),'transfer_xi':xi_rows(aft,outs,ins)},'recommendation':{'transfers':[public_move(first)] if go else []},'optimizer':{'weighted_gain':round(gain,2),'plan':[public_move(m) for m in plan],'selling_price_aware':bool(opt.get('selling_price_aware')),'reentry_pool':bool(opt.get('reentry_pool'))},'future':future,'candidates':cands,'recent_form':{'promoted':bool(recent_cfg.get('promoted'))},'captain_model':{'promoted':bool(cap_cfg.get('promote'))},'historical_attack_prior':{'version':'1.0-prev-season-fade','coverage':len(previous),'requested':len(history_ids)}}
OUT.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');print('Wrote',OUT,'history priors=',len(previous),'market active=',bool(market_blends),'strength sources=',sources,'penalty roles=',len(penalty_roles),'selling prices live=',selling_live)

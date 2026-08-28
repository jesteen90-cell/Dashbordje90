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

boot=get('bootstrap-static/');fixtures=get('fixtures/');players=boot['elements'];events=boot['events'];team_meta={int(t['id']):t for t in boot['teams']};teams={tid:t['name'] for tid,t in team_meta.items()};byid={int(p['id']):p for p in players};ratings=build_strength(fixtures,team_meta);recent_cfg=load_tuned_params();cap_cfg=captain_params();market,market_status=load_market()
now=datetime.now(timezone.utc);future=[e for e in events if dt(e.get('deadline_time')) and dt(e['deadline_time'])>now and not e.get('finished')];event=min(future,key=lambda e:dt(e['deadline_time'])) if future else next((e for e in events if e.get('is_next')),None)
if not event:raise RuntimeError('No upcoming FPL deadline')
TARGET=int(event['id']);deadline=event['deadline_time'];W=strategy_weights();GWS=list(range(TARGET,min(38,TARGET+len(W)-1)+1));weights={g:W[i] for i,g in enumerate(GWS)};fm={g:{} for g in GWS};market_blends=[]
for f in fixtures:
 g=f.get('event')
 if g not in fm:continue
 fid=int(f.get('id') or 0);h=int(f['team_h']);a=int(f['team_a']);hatk,alam=fixture_factors(ratings,h,a,True);aatk,hlam=fixture_factors(ratings,a,h,False)
 hlam2,wh,mh=blend_lambda(hlam,fid,True,market);alam2,wa,ma=blend_lambda(alam,fid,False,market)
 if wh or wa:market_blends.append({'fixture_id':fid,'gw':g,'home_team':h,'away_team':a,'internal_home_xg':round(hlam,3),'internal_away_xg':round(alam,3),'market_home_xg':mh,'market_away_xg':ma,'home_weight':round(wh,3),'away_weight':round(wa,3),'ensemble_home_xg':round(hlam2,3),'ensemble_away_xg':round(alam2,3)})
 fm[g].setdefault(h,[]).append({'home':1,'opp':a,'attack':hatk,'opp_lambda':alam2});fm[g].setdefault(a,[]).append({'home':0,'opp':h,'attack':aatk,'opp_lambda':hlam2})
finished=sorted((int(e['id']) for e in events if e.get('finished')),reverse=True);snapshot=snapshot_gw=None
for g in finished+[x for x in range(TARGET-1,0,-1) if x not in finished]:
 s=get(f'entry/{TEAM_ID}/event/{g}/picks/',True)
 if s and len(s.get('picks',[]))==15:snapshot,snapshot_gw=s,g;break
if not snapshot:raise RuntimeError('No public squad snapshot')
squad=[byid[int(x['element'])] for x in snapshot['picks']];bank=int(snapshot.get('entry_history',{}).get('bank') or 0);free_transfers=max(1,min(5,int(os.environ.get('FPL_FREE_TRANSFERS','1'))))
squad_ids={int(p['id']) for p in squad};ranked=sorted(players,key=lambda p:n(p.get('total_points'))+2*n(p.get('form'))+n(p.get('selected_by_percent'))*.15,reverse=True);history_ids=squad_ids|{int(p['id']) for p in ranked[:140]};recent={};previous={}

def fetch_recent(pid):
 s=get(f'element-summary/{pid}/',True) or {};past=s.get('history_past') or [];prev=past[-1] if past else {};pm=n(prev.get('minutes'));previous_row={'minutes':pm,'goal90':n(prev.get('goals_scored'))*90/max(pm,1) if pm else 0,'assist90':n(prev.get('assists'))*90/max(pm,1) if pm else 0};return pid,recent_signal(s.get('history',[]),params=recent_cfg),previous_row
with ThreadPoolExecutor(max_workers=12) as ex:
 futures=[ex.submit(fetch_recent,pid) for pid in history_ids]
 for fut in as_completed(futures):
  try:pid,val,prev=fut.result();recent[pid]=val;previous[pid]=prev
  except Exception:pass
print(f'Loaded recent/history priors for {len(recent)}/{len(history_ids)} players')

def availability(p):
 if p.get('status') in ('u','s'):return 0
 c=p.get('chance_of_playing_next_round');return clamp(n(c)/100) if c is not None else (.55 if p.get('status') in ('i','d') else 1)
def core_input(p,f):
 pos=int(p['element_type']);hist=n(p.get('minutes'));starts=n(p.get('starts'));rounds=max(TARGET-1,1);avg_start=78 if starts<=0 else clamp(hist/max(starts,1),55,88);res=max(0,hist-starts*avg_start);sub_apps=res/18 if res else 0;scale=90/max(hist,180);prev=previous.get(int(p['id']),{};)

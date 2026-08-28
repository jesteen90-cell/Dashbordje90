from __future__ import annotations
"""Pre-deadline shadow projections.
A = internal team model, B = simple two-sided market ensemble,
C = market ensemble with team attack allocated by shrunk player xG/xA shares.
"""
import json
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import requests
from model_v2_core import project as core_project
from team_strength_v2 import build_strength,fixture_factors
from market_ensemble_v1 import load_market,blend_lambda
from player_attack_share_v1 import build_player_shares,allocated_rates
from player_form_v2 import form_signal
from recent_form_v2 import recent_signal,blend_rates,load_tuned_params
BASE='https://fantasy.premierleague.com/api';DATA=Path('data.json');OUT=Path('market_ab_shadow.json')
def get(path):
 r=requests.get(f"{BASE}/{path.lstrip('/')}",headers={'Accept':'application/json','User-Agent':'fpl-autopilot-market-ab-shadow'},timeout=18);r.raise_for_status();return r.json()
def n(v,d=0):
 try:return float(v)
 except:return d
def clamp(x,a=0,b=1):return max(a,min(b,x))
def availability(p):
 if p.get('status') in ('u','s'):return 0
 c=p.get('chance_of_playing_next_round');return clamp(n(c)/100) if c is not None else (.55 if p.get('status') in ('i','d') else 1)
def main():
 data=json.loads(DATA.read_text());target=int(data['gw']);boot=get('bootstrap-static/');fixtures=get('fixtures/');players=boot['elements'];teams={int(t['id']):t['name'] for t in boot['teams']};byid={int(p['id']):p for p in players};ratings=build_strength(fixtures,teams);market,market_status=load_market();recent_cfg=load_tuned_params();shares=build_player_shares(players);ids=set()
 for key in ('lineup','bench'):ids.update(int(p['id']) for p in data.get(key,[]) if p.get('id') is not None)
 cmp=data.get('comparison') or {}
 for key in ('current_xi','transfer_xi'):ids.update(int(p['id']) for p in cmp.get(key,[]) if p.get('id') is not None)
 for c in data.get('candidates') or []:
  for pair in c.get('pairs') or []:
   for side in ('out','in'):
    if (pair.get(side) or {}).get('id') is not None:ids.add(int(pair[side]['id']))
 recent={}
 def fetch(pid):
  try:return pid,recent_signal(get(f'element-summary/{pid}/').get('history',[]),params=recent_cfg)
  except:return pid,{'multiplier':1,'confidence':0,'xgi90':0,'minutes':0,'matches':0}
 with ThreadPoolExecutor(max_workers=10) as ex:
  for f in as_completed([ex.submit(fetch,pid) for pid in ids]):pid,v=f.result();recent[pid]=v
 fm={};fixture_rows=[]
 for f in fixtures:
  if int(f.get('event') or -1)!=target:continue
  fid=int(f['id']);h=int(f['team_h']);a=int(f['team_a']);hatk,a_concede=fixture_factors(ratings,h,a,True);aatk,h_concede=fixture_factors(ratings,a,h,False);h_int=h_concede;a_int=a_concede;h_ens,wh,mh=blend_lambda(h_int,fid,True,market);a_ens,wa,ma=blend_lambda(a_int,fid,False,market)
  h_attack_market=clamp(hatk*(h_ens/max(h_int,.15)),.55,1.75);a_attack_market=clamp(aatk*(a_ens/max(a_int,.15)),.55,1.75)
  fm[h]={'attack_internal':hatk,'attack_ensemble':h_attack_market,'team_xg_internal':h_int,'team_xg_ensemble':h_ens,'internal_opp_lambda':a_int,'ensemble_opp_lambda':a_ens};fm[a]={'attack_internal':aatk,'attack_ensemble':a_attack_market,'team_xg_internal':a_int,'team_xg_ensemble':a_ens,'internal_opp_lambda':h_int,'ensemble_opp_lambda':h_ens}
  fixture_rows.append({'fixture_id':fid,'home_team':h,'away_team':a,'internal_home_xg':round(h_int,3),'internal_away_xg':round(a_int,3),'market_home_xg':mh,'market_away_xg':ma,'ensemble_home_xg':round(h_ens,3),'ensemble_away_xg':round(a_ens,3),'home_weight':round(wh,3),'away_weight':round(wa,3)})
 def base_inp(p,lam,atk):
  pos=int(p['element_type']);hist=n(p.get('minutes'));starts=n(p.get('starts'));rounds=max(target-1,1);avg_start=78 if starts<=0 else clamp(hist/max(starts,1),55,88);res=max(0,hist-starts*avg_start);sub_apps=res/18 if res else 0;scale=90/max(hist,180);base={'position':pos,'availability':availability(p),'start_rate':clamp(starts/rounds),'avg_start_mins':avg_start,'sub_rate':clamp(sub_apps/rounds,0,.6),'avg_sub_mins':18,'minutes_history':hist,'goal90':n(p.get('goals_scored'))*scale,'assist90':n(p.get('assists'))*scale,'save90':n(p.get('saves'))*scale,'defcon90':n(p.get('defensive_contribution'))*scale,'bonus90':n(p.get('bonus'))*scale,'yellow90':n(p.get('yellow_cards'))*scale,'red90':n(p.get('red_cards'))*scale,'opponent_goal_lambda':lam,'attack_multiplier':atk};adjusted,_=blend_rates(base,form_signal(p),recent.get(int(p['id']),{}),attack_share=float(recent_cfg.get('attack_share',.40)),enabled=bool(recent_cfg.get('promoted')));return adjusted
 rows=[]
 for pid in sorted(ids):
  p=byid.get(pid);f=fm.get(int(p['team'])) if p else None
  if not p or not f:continue
  ia=base_inp(p,f['internal_opp_lambda'],f['attack_internal']);ib=base_inp(p,f['ensemble_opp_lambda'],f['attack_ensemble']);aa=core_project(ia);bb=core_project(ib)
  alloc=allocated_rates(p,shares,f['team_xg_ensemble'],max(bb.get('xmins',0),1));ic=dict(ib);ic['goal90']=alloc['goal90'];ic['assist90']=alloc['assist90'];ic['attack_multiplier']=1.0;cc=core_project(ic)
  rows.append({'id':pid,'name':p['web_name'],'team':teams[int(p['team'])],'position':{1:'GK',2:'DEF',3:'MID',4:'FWD'}[int(p['element_type'])],'internal_xp':round(aa['total'],3),'ensemble_xp':round(bb['total'],3),'share_ensemble_xp':round(cc['total'],3),'internal_cs_probability':round(aa['cs_probability'],4),'ensemble_cs_probability':round(bb['cs_probability'],4),'internal_attack_points':round(aa.get('goals',0)+aa.get('assists',0),3),'ensemble_attack_points':round(bb.get('goals',0)+bb.get('assists',0),3),'share_attack_points':round(cc.get('goals',0)+cc.get('assists',0),3),'goal_share':round(alloc['goal_share'],4),'assist_share':round(alloc['assist_share'],4),'expected_minutes':round(aa['xmins'],1)})
 payload={'version':'1.2-player-share','gw':target,'market_status':market_status,'market_active':any(x['home_weight'] or x['away_weight'] for x in fixture_rows),'players':rows,'fixtures':fixture_rows};OUT.write_text(json.dumps(payload,ensure_ascii=False,indent=2));print('Market A/B/C player-share shadow written',len(rows),'players','active=',payload['market_active'])
if __name__=='__main__':main()

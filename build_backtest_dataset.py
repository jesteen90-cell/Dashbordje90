"""Build leakage-safe walk-forward rows for the shared FPL Model v2 core.

Predictions for GW N only use player/team information from GWs < N.
Fixture identity is known in advance; target-GW outcomes are added only after
all predictions for that GW have been stored.
"""
from __future__ import annotations
import argparse,csv,io,json,math
from collections import defaultdict
import requests
from model_v2_core import project

RAW='https://raw.githubusercontent.com/vaastav/Fantasy-Premier-League/master/data/{season}/gws/merged_gw.csv'
POSMAP={'GK':1,'GKP':1,'DEF':2,'MID':3,'FWD':4,'1':1,'2':2,'3':3,'4':4}

def f(v,d=0.0):
 try:return float(v)
 except:return d

def clamp(x,a,b):return max(a,min(b,x))
def shrink(rate,n,prior,prior_n):return (rate*n+prior*prior_n)/(n+prior_n) if n+prior_n else prior

def pos_of(r):
 raw=str(r.get('position') or r.get('element_type') or '').upper()
 return POSMAP.get(raw,3)

def rate90(h,key):return h[key]/max(h['mins'],90)*90

def fixture_teams(rows):
 out={}
 for r in rows:
  fid=str(r.get('fixture') or '')
  if not fid:continue
  cur=list(out.get(fid,(None,None)));team=r.get('team') or '?';home=str(r.get('was_home')).lower() in ('true','1')
  cur[0 if home else 1]=team;out[fid]=tuple(cur)
 return out

def team_rates(stats,team,league_avg=1.45,prior_matches=6):
 s=stats[team];m=s['matches'];gf=(s['gf']+league_avg*prior_matches)/(m+prior_matches);ga=(s['ga']+league_avg*prior_matches)/(m+prior_matches)
 return gf,ga

def fixture_strength(stats,team,opp,is_home,league_avg):
 tgf,tga=team_rates(stats,team,league_avg);ogf,oga=team_rates(stats,opp,league_avg)
 attack=math.sqrt(max(.25,tgf/league_avg)*max(.25,oga/league_avg));opp_lambda=league_avg*math.sqrt(max(.25,ogf/league_avg)*max(.25,tga/league_avg))
 attack*=1.06 if is_home else .96;opp_lambda*=.92 if is_home else 1.08
 return clamp(attack,.62,1.55),clamp(opp_lambda,.45,2.75)

def core_input(h,gw,pos,attack_mult,opp_lambda):
 prev=max(gw-1,1);start_rate=(h['starts']+1.5)/(prev+3);sub_rate=(h['subs']+1.0)/(prev+4)
 avg_start=h['start_mins']/h['starts'] if h['starts'] else 78;avg_sub=h['sub_mins']/h['subs'] if h['subs'] else 18
 return {'position':pos,'availability':1.0,'start_rate':start_rate,'avg_start_mins':avg_start,'sub_rate':sub_rate,'avg_sub_mins':avg_sub,
         'minutes_history':h['mins'],'goal90':rate90(h,'goals'),'assist90':rate90(h,'assists'),'save90':rate90(h,'saves'),'defcon90':rate90(h,'defcon'),
         'bonus90':rate90(h,'bonus'),'yellow90':rate90(h,'yellow'),'red90':rate90(h,'red'),'opponent_goal_lambda':opp_lambda,'attack_multiplier':attack_mult}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--seasons',nargs='+',default=['2023-24','2024-25','2025-26']);ap.add_argument('--out',default='backtest_dataset.json');a=ap.parse_args();out=[]
 for season in a.seasons:
  resp=requests.get(RAW.format(season=season),timeout=60);resp.raise_for_status();rows=list(csv.DictReader(io.StringIO(resp.text)));rows.sort(key=lambda r:int(r.get('GW') or r.get('gw') or 0));fmap=fixture_teams(rows)
  hist=defaultdict(lambda:{'mins':0.,'pts':0.,'goals':0.,'assists':0.,'saves':0.,'defcon':0.,'bonus':0.,'yellow':0.,'red':0.,'starts':0.,'subs':0.,'start_mins':0.,'sub_mins':0.});pos_prior=defaultdict(lambda:[0.,0.]);team_stats=defaultdict(lambda:{'matches':0.,'gf':0.,'ga':0.});league={'matches':0.,'goals':0.};bygw=defaultdict(list)
  for r in rows:bygw[int(r.get('GW') or r.get('gw') or 0)].append(r)
  for gw in sorted(bygw):
   grows=bygw[gw]
   for r in grows:
    pid=str(r.get('element') or r.get('id') or r.get('name'));pos=pos_of(r);h=hist[pid];mins=h['mins'];n90=max(mins/90,0);pos_pts,pos_mins=pos_prior[pos];prior90=(pos_pts/max(pos_mins,90))*90 if pos_mins else 3.2;player90=(h['pts']/max(mins,90))*90 if mins else prior90;baseline=shrink(player90,n90,prior90,6)
    fid=str(r.get('fixture') or '');home=str(r.get('was_home')).lower() in ('true','1');pair=fmap.get(fid,(None,None));team=r.get('team') or '?';opp=(pair[1] if home else pair[0]) or '?';league_avg=(league['goals']/league['matches']/2) if league['matches'] else 1.45;atk,lam=fixture_strength(team_stats,team,opp,home,league_avg);v2=project(core_input(h,gw,pos,atk,lam));actual=f(r.get('total_points') or r.get('event_points'))
    if gw>=4:out.append({'season':season,'gw':gw,'player':r.get('name'),'position':pos,'team':team,'opponent':opp,'home':home,'actual':actual,'baseline':round(baseline,4),'v2':round(v2['total'],4),'expected_minutes':round(v2['xmins'],2),'attack_multiplier':round(atk,4),'opponent_goal_lambda':round(lam,4)})
   for r in grows:
    pid=str(r.get('element') or r.get('id') or r.get('name'));pos=pos_of(r);h=hist[pid];m=f(r.get('minutes'));actual=f(r.get('total_points') or r.get('event_points'));start_flag=f(r.get('starts'),-1);is_start=(start_flag>0) if start_flag>=0 else m>=60
    h['mins']+=m;h['pts']+=actual;h['goals']+=f(r.get('goals_scored'));h['assists']+=f(r.get('assists'));h['saves']+=f(r.get('saves'));h['defcon']+=f(r.get('defensive_contribution'));h['bonus']+=f(r.get('bonus'));h['yellow']+=f(r.get('yellow_cards'));h['red']+=f(r.get('red_cards'))
    if m>0:
     if is_start:h['starts']+=1;h['start_mins']+=m
     else:h['subs']+=1;h['sub_mins']+=m
    pos_prior[pos][0]+=actual;pos_prior[pos][1]+=m
   seen=set()
   for r in grows:
    fid=str(r.get('fixture') or '')
    if not fid or fid in seen:continue
    seen.add(fid);home_team,away_team=fmap.get(fid,(None,None));hs=f(r.get('team_h_score'),-1);as_=f(r.get('team_a_score'),-1)
    if not home_team or not away_team or hs<0 or as_<0:continue
    team_stats[home_team]['matches']+=1;team_stats[home_team]['gf']+=hs;team_stats[home_team]['ga']+=as_;team_stats[away_team]['matches']+=1;team_stats[away_team]['gf']+=as_;team_stats[away_team]['ga']+=hs;league['matches']+=1;league['goals']+=hs+as_
 open(a.out,'w').write(json.dumps(out,ensure_ascii=False));print(f'wrote {len(out)} rows to {a.out}')

if __name__=='__main__':main()

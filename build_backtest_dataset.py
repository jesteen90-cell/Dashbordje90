"""Build leakage-aware walk-forward rows for the shared FPL Model v2.1 core.

Only information from GWs before the target GW is used as model input. The
current target row is applied to history only after its prediction is stored.
"""
from __future__ import annotations
import argparse,csv,io,json
from collections import defaultdict
import requests
from model_v2_core import project

RAW='https://raw.githubusercontent.com/vaastav/Fantasy-Premier-League/master/data/{season}/gws/merged_gw.csv'
POSMAP={'GK':1,'GKP':1,'DEF':2,'MID':3,'FWD':4,'1':1,'2':2,'3':3,'4':4}

def f(v,d=0.0):
 try:return float(v)
 except:return d

def shrink(rate,n,prior,prior_n):return (rate*n+prior*prior_n)/(n+prior_n) if n+prior_n else prior

def pos_of(r):
 raw=str(r.get('position') or r.get('element_type') or '').upper()
 return POSMAP.get(raw,3)

def rate90(h,key):return h[key]/max(h['mins'],90)*90

def core_input(h,gw,pos):
 prev=max(gw-1,1)
 start_rate=(h['starts']+1.5)/(prev+3)
 sub_rate=(h['subs']+1.0)/(prev+4)
 avg_start=h['start_mins']/h['starts'] if h['starts'] else 78
 avg_sub=h['sub_mins']/h['subs'] if h['subs'] else 18
 return {'position':pos,'availability':1.0,'start_rate':start_rate,'avg_start_mins':avg_start,'sub_rate':sub_rate,'avg_sub_mins':avg_sub,
         'minutes_history':h['mins'],'goal90':rate90(h,'goals'),'assist90':rate90(h,'assists'),'save90':rate90(h,'saves'),'defcon90':rate90(h,'defcon'),
         'bonus90':rate90(h,'bonus'),'yellow90':rate90(h,'yellow'),'red90':rate90(h,'red'),'opponent_goal_lambda':1.35,'attack_multiplier':1.0}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--seasons',nargs='+',default=['2023-24','2024-25','2025-26']);ap.add_argument('--out',default='backtest_dataset.json');a=ap.parse_args()
 out=[]
 for season in a.seasons:
  resp=requests.get(RAW.format(season=season),timeout=60);resp.raise_for_status();rows=list(csv.DictReader(io.StringIO(resp.text)))
  rows.sort(key=lambda r:int(r.get('GW') or r.get('gw') or 0))
  hist=defaultdict(lambda:{'mins':0.,'pts':0.,'goals':0.,'assists':0.,'saves':0.,'defcon':0.,'bonus':0.,'yellow':0.,'red':0.,'starts':0.,'subs':0.,'start_mins':0.,'sub_mins':0.})
  pos_prior=defaultdict(lambda:[0.,0.])
  for r in rows:
   gw=int(r.get('GW') or r.get('gw') or 0);pid=str(r.get('element') or r.get('id') or r.get('name'));pos=pos_of(r);h=hist[pid]
   mins=h['mins'];n90=max(mins/90,0);pos_pts,pos_mins=pos_prior[pos];prior90=(pos_pts/max(pos_mins,90))*90 if pos_mins else 3.2;player90=(h['pts']/max(mins,90))*90 if mins else prior90
   baseline=shrink(player90,n90,prior90,6);v2=project(core_input(h,gw,pos));actual=f(r.get('total_points') or r.get('event_points'))
   if gw>=4:out.append({'season':season,'gw':gw,'player':r.get('name'),'position':pos,'actual':actual,'baseline':round(baseline,4),'v2':round(v2['total'],4),'expected_minutes':round(v2['xmins'],2)})
   m=f(r.get('minutes'));start_flag=f(r.get('starts'),-1)
   is_start=(start_flag>0) if start_flag>=0 else m>=60
   h['mins']+=m;h['pts']+=actual;h['goals']+=f(r.get('goals_scored'));h['assists']+=f(r.get('assists'));h['saves']+=f(r.get('saves'));h['defcon']+=f(r.get('defensive_contribution'));h['bonus']+=f(r.get('bonus'));h['yellow']+=f(r.get('yellow_cards'));h['red']+=f(r.get('red_cards'))
   if m>0:
    if is_start:h['starts']+=1;h['start_mins']+=m
    else:h['subs']+=1;h['sub_mins']+=m
   pos_prior[pos][0]+=actual;pos_prior[pos][1]+=m
 open(a.out,'w').write(json.dumps(out,ensure_ascii=False));print(f'wrote {len(out)} rows to {a.out}')

if __name__=='__main__':main()

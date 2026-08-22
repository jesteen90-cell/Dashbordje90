"""Build a leakage-aware rolling FPL backtest dataset from Vaastav historical GW files.

IMPORTANT: xP/ep_this from post-GW merged files is intentionally NOT used as a feature.
For each target GW, features use only rows from earlier GWs in that season.
"""
from __future__ import annotations
import argparse, io, json, math
from collections import defaultdict
import requests

RAW='https://raw.githubusercontent.com/vaastav/Fantasy-Premier-League/master/data/{season}/gws/merged_gw.csv'

def f(v,d=0.0):
    try:return float(v)
    except:return d

def shrink(rate,n,prior,prior_n): return (rate*n+prior*prior_n)/(n+prior_n) if n+prior_n else prior

def main():
    import csv
    ap=argparse.ArgumentParser(); ap.add_argument('--seasons',nargs='+',default=['2023-24','2024-25','2025-26']); ap.add_argument('--out',default='backtest_dataset.json'); a=ap.parse_args()
    out=[]
    for season in a.seasons:
        text=requests.get(RAW.format(season=season),timeout=60).text; text and requests.models.Response
        rows=list(csv.DictReader(io.StringIO(text)))
        rows.sort(key=lambda r:int(r.get('GW') or r.get('gw') or 0))
        hist=defaultdict(lambda:{'mins':0.,'pts':0.,'xg':0.,'xa':0.,'gc':0.,'saves':0.,'bonus':0.,'starts':0.,'apps':0.})
        pos_prior=defaultdict(lambda:[0.,0.])
        for r in rows:
            gw=int(r.get('GW') or r.get('gw') or 0); pid=str(r.get('element') or r.get('id') or r.get('name')); pos=str(r.get('position') or r.get('element_type') or '?')
            h=hist[pid]; mins=h['mins']; n90=max(mins/90,0)
            # Conservative rolling baseline: only information accumulated before target GW.
            pos_pts,pos_mins=pos_prior[pos]; prior90=(pos_pts/max(pos_mins,90))*90 if pos_mins else 3.2
            player90=(h['pts']/max(mins,90))*90 if mins else prior90
            baseline=shrink(player90,n90,prior90,6)
            # v2 rolling estimate: minutes probability + component rates, all shrunk.
            app_p=(h['apps']+2)/(max(gw-1,0)+3)
            start_p=(h['starts']+1.5)/(max(gw-1,0)+3)
            exp_mins=min(90,90*(.35*app_p+.65*start_p))
            xg90=shrink((h['xg']/max(mins,90))*90,n90,.10,8); xa90=shrink((h['xa']/max(mins,90))*90,n90,.08,8)
            bonus90=shrink((h['bonus']/max(mins,90))*90,n90,.20,10)
            attack=(xg90*4.5+xa90*3.0)*(exp_mins/90)
            appearance=(1.0 if exp_mins<60 else 2.0)*app_p
            v2=max(0,appearance+attack+bonus90*(exp_mins/90))
            actual=f(r.get('total_points') or r.get('event_points'))
            if gw>=4: out.append({'season':season,'gw':gw,'player':r.get('name'),'position':pos,'actual':actual,'baseline':round(baseline,4),'v2':round(v2,4),'expected_minutes':round(exp_mins,2)})
            m=f(r.get('minutes')); pts=actual; h['mins']+=m; h['pts']+=pts; h['xg']+=f(r.get('expected_goals')); h['xa']+=f(r.get('expected_assists')); h['gc']+=f(r.get('goals_conceded')); h['saves']+=f(r.get('saves')); h['bonus']+=f(r.get('bonus')); h['apps']+=1 if m>0 else 0; h['starts']+=1 if m>=60 else 0
            pos_prior[pos][0]+=pts; pos_prior[pos][1]+=m
    open(a.out,'w').write(json.dumps(out,ensure_ascii=False)); print(f'wrote {len(out)} rows to {a.out}')
if __name__=='__main__':main()

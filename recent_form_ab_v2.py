#!/usr/bin/env python3
"""Leakage-safe A/B + tuning for recent xGI overlay.
Downloads each season once, tunes only on train seasons, then evaluates untouched holdout.
"""
import argparse,csv,io,json,requests
from collections import defaultdict
RAW='https://raw.githubusercontent.com/vaastav/Fantasy-Premier-League/master/data/{season}/gws/merged_gw.csv'
def n(x,d=0.):
 try:return float(x)
 except:return d
def clamp(x,a,b):return max(a,min(b,x))
def mae(xs):return sum(abs(a-b) for a,b in xs)/len(xs) if xs else 999

def load_all(seasons):
 data={}
 for season in seasons:
  r=requests.get(RAW.format(season=season),timeout=60);r.raise_for_status();rows=list(csv.DictReader(io.StringIO(r.text)));rows.sort(key=lambda x:int(x.get('GW') or x.get('gw') or 0));data[season]=rows
 return data

def signal(hist,last_n,decay,strength,prior):
 rows=hist[-last_n:][::-1]
 if not rows:return 1.,0.
 sx=smin=tot=0.
 for age,r in enumerate(rows):
  w=decay**age;m=n(r.get('minutes'));sx+=(n(r.get('expected_goals'))+n(r.get('expected_assists')))*w;smin+=m*w;tot+=m
 xgi90=sx*90/max(smin,90);conf=tot/(tot+prior);raw=1+strength*(xgi90-.35);mult=1+(clamp(raw,.72,1.35)-1)*conf
 return clamp(mult,.84,1.20),conf

def build(data,seasons,p):
 out=[]
 for season in seasons:
  hist=defaultdict(list)
  for row in data[season]:
   gw=int(row.get('GW') or row.get('gw') or 0);pid=str(row.get('element') or row.get('id') or row.get('name'));mult,conf=signal(hist[pid],p['last_n'],p['decay'],p['strength'],p['prior']);h=hist[pid];base=sum(n(x.get('total_points')) for x in h[-6:])/max(len(h[-6:]),1) if h else 2.;recent=base*(1+p['attack_share']*(mult-1));actual=n(row.get('total_points'))
   if gw>=7:out.append({'season':season,'gw':gw,'player':row.get('name'),'base':base,'recent':recent,'actual':actual,'mult':mult,'confidence':conf})
   hist[pid].append(row)
 return out

def ev(rows):
 b=[(x['base'],x['actual']) for x in rows];r=[(x['recent'],x['actual']) for x in rows];bygw=defaultdict(list)
 for x in rows:bygw[x['gw']].append(x)
 tb=tr=0
 for xs in bygw.values():
  if len(xs)>=20:tb+=max(xs,key=lambda z:z['base'])['actual'];tr+=max(xs,key=lambda z:z['recent'])['actual']
 return {'n':len(rows),'base_mae':round(mae(b),4),'recent_mae':round(mae(r),4),'mae_delta':round(mae(b)-mae(r),4),'top_pick_base':round(tb,1),'top_pick_recent':round(tr,1),'top_pick_delta':round(tr-tb,1)}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--seasons',nargs='+',default=['2023-24','2024-25','2025-26']);ap.add_argument('--out',default='recent_form_ab_status.json');a=ap.parse_args();hold=sorted(a.seasons)[-1];train=[s for s in a.seasons if s!=hold];data=load_all(a.seasons)
 grid=[{'last_n':ln,'decay':d,'strength':st,'attack_share':ash,'prior':360.} for ln in (4,6,8) for d in (.68,.78,.88) for st in (.12,.20,.30) for ash in (.25,.40,.55)]
 best=None
 for p in grid:
  m=ev(build(data,train,p));score=m['mae_delta']+.002*max(-20,min(20,m['top_pick_delta']))
  if best is None or score>best[0]:best=(score,p,m)
 _,params,tr=best;ho=ev(build(data,[hold],params));promote=ho['mae_delta']>0 and ho['top_pick_delta']>=0
 out={'holdout_season':hold,'train_seasons':train,'tested_configs':len(grid),'selected_params':params,'train':tr,'holdout':ho,'promote':promote}
 json.dump(out,open(a.out,'w'),indent=2);print(json.dumps(out,indent=2))
if __name__=='__main__':main()

#!/usr/bin/env python3
"""Leakage-safe A/B test: base v2.6 signal vs recent-form overlay.
Uses only prior-GW xG/xA/minutes to build the rolling six-match signal.
"""
import argparse,csv,io,json,math,requests
from collections import defaultdict
RAW='https://raw.githubusercontent.com/vaastav/Fantasy-Premier-League/master/data/{season}/gws/merged_gw.csv'

def n(x,d=0.):
 try:return float(x)
 except:return d

def clamp(x,a,b):return max(a,min(b,x))
def mae(xs):return sum(abs(a-b) for a,b in xs)/len(xs) if xs else 999

def signal(hist,last_n=6,decay=.78):
 rows=hist[-last_n:][::-1]
 if not rows:return 1.,0.
 sx=smin=0.;tot=0.
 for age,r in enumerate(rows):
  w=decay**age;m=n(r.get('minutes'));sx+=(n(r.get('expected_goals'))+n(r.get('expected_assists')))*w;smin+=m*w;tot+=m
 xgi90=sx*90/max(smin,90);raw=1+.30*(xgi90-.35);conf=tot/(tot+360);mult=1+(clamp(raw,.72,1.35)-1)*conf
 return clamp(mult,.84,1.20),conf

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--seasons',nargs='+',default=['2023-24','2024-25','2025-26']);ap.add_argument('--out',default='recent_form_ab_status.json');a=ap.parse_args()
 all_rows=[]
 for season in a.seasons:
  r=requests.get(RAW.format(season=season),timeout=60);r.raise_for_status();rows=list(csv.DictReader(io.StringIO(r.text)));rows.sort(key=lambda x:int(x.get('GW') or x.get('gw') or 0));hist=defaultdict(list)
  for row in rows:
   gw=int(row.get('GW') or row.get('gw') or 0);pid=str(row.get('element') or row.get('id') or row.get('name'));m,conf=signal(hist[pid]);mins=sum(n(x.get('minutes')) for x in hist[pid]);base=(sum(n(x.get('total_points')) for x in hist[pid][-6:])/max(len(hist[pid][-6:]),1)) if hist[pid] else 2.0
   # Conservative A/B proxy: recent multiplier adjusts only the attacking share
   # of a rolling player-points baseline rather than all expected points.
   attack_share=.55;pred_base=base;pred_recent=base*(1+attack_share*(m-1));actual=n(row.get('total_points'))
   if gw>=7:all_rows.append({'season':season,'gw':gw,'player':row.get('name'),'base':pred_base,'recent':pred_recent,'actual':actual,'mult':m,'confidence':conf,'history_minutes':mins})
   hist[pid].append(row)
 hold=sorted(a.seasons)[-1];train=[x for x in all_rows if x['season']!=hold];test=[x for x in all_rows if x['season']==hold]
 def ev(rows):
  b=[(x['base'],x['actual']) for x in rows];r=[(x['recent'],x['actual']) for x in rows];
  bygw=defaultdict(list)
  for x in rows:bygw[x['gw']].append(x)
  top_base=top_recent=0
  for g,xs in bygw.items():
   if len(xs)<20:continue
   top_base+=max(xs,key=lambda z:z['base'])['actual'];top_recent+=max(xs,key=lambda z:z['recent'])['actual']
  return {'n':len(rows),'base_mae':round(mae(b),4),'recent_mae':round(mae(r),4),'mae_delta':round(mae(b)-mae(r),4),'top_pick_base':round(top_base,1),'top_pick_recent':round(top_recent,1),'top_pick_delta':round(top_recent-top_base,1)}
 tr,ho=ev(train),ev(test);promote=ho['mae_delta']>=0 and ho['top_pick_delta']>=0
 out={'holdout_season':hold,'train_seasons':sorted(set(x['season'] for x in train)),'train':tr,'holdout':ho,'promote':promote}
 json.dump(out,open(a.out,'w'),indent=2);print(json.dumps(out,indent=2))
if __name__=='__main__':main()

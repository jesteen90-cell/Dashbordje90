#!/usr/bin/env python3
import argparse,json
from collections import defaultdict

def num(x,d=0.0):
 try:return float(x)
 except:return d

def xp(r):return num(r.get('v2',r.get('predicted_xp',r.get('v2_xp'))))
def actual(r):return num(r.get('actual',r.get('actual_points',r.get('total_points'))))
def attack_signal(r):return num(r.get('attack_multiplier',r.get('attack_signal',r.get('xgi_per90'))),1.0)

def score(r,w):
 mins=num(r.get('expected_minutes'),60)/90
 pos=int(num(r.get('position'),0))
 return w[0]*xp(r)+w[1]*mins+w[2]*attack_signal(r)+w[3]*(1 if pos in (3,4) else 0)

def evaluate(rows,w,seasons):
 groups=defaultdict(list)
 for r in rows:
  if r.get('season') in seasons:groups[(r.get('season'),int(num(r.get('gw'))))].append(r)
 pts=base=0.0;wins=ties=losses=0;n=0
 for _,g in groups.items():
  eligible=[r for r in g if num(r.get('expected_minutes'),0)>=45]
  if not eligible:continue
  pick=max(eligible,key=lambda r:score(r,w));bp=max(eligible,key=xp)
  a,b=actual(pick),actual(bp);pts+=a;base+=b;n+=1
  if a>b:wins+=1
  elif a==b:ties+=1
  else:losses+=1
 return {'gameweeks':n,'points':pts,'baseline_points':base,'delta':pts-base,'wins':wins,'ties':ties,'losses':losses}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('dataset');ap.add_argument('--out',default='captain_model_status.json');a=ap.parse_args()
 rows=json.load(open(a.dataset));rows=rows['rows'] if isinstance(rows,dict) and 'rows' in rows else rows
 seasons=sorted({r.get('season') for r in rows if r.get('season')});hold=seasons[-1];train=set(seasons[:-1])
 grid=[]
 for wxp in (0.8,1.0,1.2):
  for wm in (0,.15,.30,.45):
   for wa in (0,.10,.20,.30):
    for wp in (0,.05,.10,.15):grid.append((wxp,wm,wa,wp))
 ranked=[]
 for w in grid:
  e=evaluate(rows,w,train);ranked.append((e['delta'],e['wins']-e['losses'],w,e))
 ranked.sort(reverse=True,key=lambda z:(z[0],z[1]));best=ranked[0][2];tr=ranked[0][3];ho=evaluate(rows,best,{hold})
 out={'holdout_season':hold,'train_seasons':sorted(train),'weights':{'xp':best[0],'minutes':best[1],'attack_multiplier':best[2],'mid_fwd':best[3]},'train':tr,'holdout':ho,'promote':ho['delta']>0 and ho['wins']>=ho['losses']}
 json.dump(out,open(a.out,'w'),indent=2);print(json.dumps(out,indent=2))
if __name__=='__main__':main()

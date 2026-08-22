#!/usr/bin/env python3
import argparse,json,math
from collections import defaultdict

def num(x,d=0.0):
 try:return float(x)
 except:return d

def score(r,w):
 xp=num(r.get('predicted_xp',r.get('v2_xp')))
 mins=num(r.get('expected_minutes'),60)/90
 pos=int(num(r.get('position'),0))
 attack=num(r.get('attack_signal'),num(r.get('xgi_per90'),0))
 return w[0]*xp+w[1]*mins+w[2]*attack+w[3]*(1 if pos in (3,4) else 0)

def evaluate(rows,w,seasons):
 groups=defaultdict(list)
 for r in rows:
  if r.get('season') in seasons:groups[(r.get('season'),int(num(r.get('gw'))))].append(r)
 pts=base=0; wins=ties=losses=0;n=0
 for _,g in groups.items():
  eligible=[r for r in g if num(r.get('minutes'),0)>0 or num(r.get('expected_minutes'),0)>0]
  if not eligible:continue
  pick=max(eligible,key=lambda r:score(r,w)); bp=max(eligible,key=lambda r:num(r.get('predicted_xp',r.get('v2_xp'))))
  a=num(pick.get('actual_points',pick.get('total_points')));b=num(bp.get('actual_points',bp.get('total_points')))
  pts+=a;base+=b;n+=1
  if a>b:wins+=1
  elif a==b:ties+=1
  else:losses+=1
 return {'gameweeks':n,'points':pts,'baseline_points':base,'delta':pts-base,'wins':wins,'ties':ties,'losses':losses}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('dataset');ap.add_argument('--out',default='captain_model_status.json');a=ap.parse_args()
 rows=json.load(open(a.dataset)); rows=rows['rows'] if isinstance(rows,dict) and 'rows' in rows else rows
 seasons=sorted({r.get('season') for r in rows if r.get('season')}); hold=seasons[-1];train=set(seasons[:-1])
 grid=[]
 for wxp in (0.8,1.0,1.2):
  for wm in (0,.15,.3):
   for wa in (0,.1,.2):
    for wp in (0,.05,.1):grid.append((wxp,wm,wa,wp))
 best=max(grid,key=lambda w:evaluate(rows,w,train)['delta']);tr=evaluate(rows,best,train);ho=evaluate(rows,best,{hold})
 out={'holdout_season':hold,'train_seasons':sorted(train),'weights':{'xp':best[0],'minutes':best[1],'attack':best[2],'mid_fwd':best[3]},'train':tr,'holdout':ho,'promote':ho['delta']>0 and ho['wins']>=ho['losses']}
 json.dump(out,open(a.out,'w'),indent=2);print(json.dumps(out,indent=2))
if __name__=='__main__':main()

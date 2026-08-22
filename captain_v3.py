#!/usr/bin/env python3
import argparse,json,itertools
from collections import defaultdict

def n(x,d=0.0):
 try:return float(x)
 except:return d

def score(r,w):
 xp=n(r.get('v2',r.get('predicted_xp')));p90=n(r.get('p90'),xp);mins=n(r.get('expected_minutes'),60)/90;atk=n(r.get('attack_multiplier'),1);vol=n(r.get('volatility'),0)
 return w['xp']*xp+w['ceiling']*p90+w['minutes']*mins+w['attack']*atk-w['volatility_penalty']*vol

def evaluate(rows,seasons,w):
 groups=defaultdict(list)
 for r in rows:
  if r.get('season') in seasons:groups[(r.get('season'),int(n(r.get('gw'))))].append(r)
 pts=base=0.;wins=ties=losses=0;gws=0
 for _,g in groups.items():
  if len(g)<20:continue
  pick=max(g,key=lambda r:score(r,w));bp=max(g,key=lambda r:n(r.get('v2',r.get('predicted_xp'))));a=n(pick.get('actual'));b=n(bp.get('actual'));pts+=a;base+=b;gws+=1
  if a>b:wins+=1
  elif a<b:losses+=1
  else:ties+=1
 return {'gameweeks':gws,'points':pts,'baseline_points':base,'delta':pts-base,'wins':wins,'ties':ties,'losses':losses}

def main():
 ap=argparse.ArgumentParser();ap.add_argument('dataset');ap.add_argument('--out',default='captain_v3_status.json');a=ap.parse_args();data=json.load(open(a.dataset));rows=data.get('rows',data) if isinstance(data,dict) else data
 seasons=sorted({r.get('season') for r in rows if r.get('season')});hold=seasons[-1];train=set(seasons[:-1]);grid=[]
 for xp,ceiling,mins,atk,vol in itertools.product((.7,1.0,1.3),(0,.1,.2,.3),(0,.1,.2),(0,.05,.1),(0,.05,.1,.2)):
  grid.append({'xp':xp,'ceiling':ceiling,'minutes':mins,'attack':atk,'volatility_penalty':vol})
 scored=[(evaluate(rows,train,w)['delta'],w,evaluate(rows,train,w)) for w in grid];_,best,tr=max(scored,key=lambda x:(x[0],x[2]['wins']-x[2]['losses']));ho=evaluate(rows,{hold},best)
 out={'holdout_season':hold,'train_seasons':sorted(train),'tested_configs':len(grid),'weights':best,'train':tr,'holdout':ho,'promote':bool(ho['delta']>0 and ho['wins']>=ho['losses'])}
 json.dump(out,open(a.out,'w'),indent=2);print(json.dumps(out,indent=2))
if __name__=='__main__':main()

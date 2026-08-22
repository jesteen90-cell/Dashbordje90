"""Walk-forward evaluation harness for FPL Model v2.

Measures raw accuracy, within-GW ranking quality, captain selection and
position-level diagnostics. Season/GW are always treated as a compound key.
"""
from __future__ import annotations
import argparse,json,math
from pathlib import Path
from statistics import mean


def mae(pred,actual):return mean(abs(p-a) for p,a in zip(pred,actual)) if pred else math.nan
def rmse(pred,actual):return math.sqrt(mean((p-a)**2 for p,a in zip(pred,actual))) if pred else math.nan

def spearman(xs,ys):
 if len(xs)<2:return math.nan
 def ranks(a):
  order=sorted(range(len(a)),key=lambda i:a[i]);r=[0.0]*len(a);i=0
  while i<len(order):
   j=i
   while j+1<len(order) and a[order[j+1]]==a[order[i]]:j+=1
   rank=(i+j+2)/2
   for k in range(i,j+1):r[order[k]]=rank
   i=j+1
  return r
 x,y=ranks(xs),ranks(ys);mx,my=mean(x),mean(y);num=sum((a-mx)*(b-my) for a,b in zip(x,y));den=math.sqrt(sum((a-mx)**2 for a in x)*sum((b-my)**2 for b in y));return num/den if den else math.nan

def metrics(rows,key):
 p=[float(r[key]) for r in rows];a=[float(r['actual']) for r in rows]
 return {'n':len(rows),'mae':mae(p,a),'rmse':rmse(p,a),'bias':mean(p)-mean(a) if rows else math.nan,'rank_corr':spearman(p,a)}

def evaluate(rows,pred_key='v2',baseline_key='baseline'):
 rows=[r for r in rows if r.get('actual') is not None and r.get(pred_key) is not None];out=metrics(rows,pred_key)
 b=[r for r in rows if r.get(baseline_key) is not None]
 if b:
  bm=metrics(b,baseline_key);out['baseline_mae']=bm['mae'];out['baseline_rmse']=bm['rmse'];out['baseline_rank_corr']=bm['rank_corr'];out['mae_improvement_pct']=100*(bm['mae']-out['mae'])/bm['mae'] if bm['mae'] else 0
 # Position diagnostics catch models that win overall by sacrificing one role.
 out['by_position']={}
 for pos in sorted({str(r.get('position')) for r in rows}):
  pr=[r for r in rows if str(r.get('position'))==pos];pm=metrics(pr,pred_key)
  br=[r for r in pr if r.get(baseline_key) is not None]
  if br:
   bm=metrics(br,baseline_key);pm['baseline_mae']=bm['mae'];pm['mae_improvement_pct']=100*(bm['mae']-pm['mae'])/bm['mae'] if bm['mae'] else 0
  out['by_position'][pos]=pm
 # Evaluate ranking per actual season/GW, not by GW number pooled across seasons.
 byg= {}
 for r in rows:byg.setdefault((str(r.get('season','?')),int(r['gw'])),[]).append(r)
 cap_v2=cap_base=oracle=0;corrs=[];wins=0
 for _,g in sorted(byg.items()):
  elig=[r for r in g if float(r.get('expected_minutes',90))>=45]
  if not elig:continue
  c=spearman([float(r[pred_key]) for r in elig],[float(r['actual']) for r in elig])
  if not math.isnan(c):corrs.append(c)
  v=max(elig,key=lambda r:float(r[pred_key]));cap_v2+=float(v['actual'])
  if all(r.get(baseline_key) is not None for r in elig):
   bv=max(elig,key=lambda r:float(r[baseline_key]));cap_base+=float(bv['actual']);wins+=float(v['actual'])>float(bv['actual'])
  oracle+=float(max(elig,key=lambda r:float(r['actual']))['actual'])
 out['within_gw_rank_corr']=mean(corrs) if corrs else math.nan
 out|={'captain_actual_total':cap_v2,'baseline_captain_total':cap_base,'captain_oracle_total':oracle,'captain_vs_baseline_wins':wins,'gameweeks':len(byg)}
 # Calibration buckets: predicted xP should track actual averages monotonically.
 buckets=[]
 ordered=sorted(rows,key=lambda r:float(r[pred_key]));n=len(ordered)
 for i in range(5):
  chunk=ordered[i*n//5:(i+1)*n//5]
  if chunk:buckets.append({'bucket':i+1,'n':len(chunk),'predicted':round(mean(float(r[pred_key]) for r in chunk),3),'actual':round(mean(float(r['actual']) for r in chunk),3)})
 out['calibration_quintiles']=buckets
 return out

def main():
 ap=argparse.ArgumentParser();ap.add_argument('input');ap.add_argument('--out',default='backtest_results.json');args=ap.parse_args();path=Path(args.input);rows=json.loads(path.read_text()) if path.suffix=='.json' else list(__import__('csv').DictReader(path.open()));result=evaluate(list(rows));Path(args.out).write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()

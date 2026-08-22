"""Walk-forward evaluation harness for FPL Model v2.

Measures raw accuracy, within-GW ranking, captaincy, season/position stability,
top-pick decision quality, and emits a deterministic dataset fingerprint.
"""
from __future__ import annotations
import argparse,hashlib,json,math
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

def enrich_vs_baseline(rows,pred_key,baseline_key):
 out=metrics(rows,pred_key);br=[r for r in rows if r.get(baseline_key) is not None]
 if br:
  bm=metrics(br,baseline_key);out['baseline_mae']=bm['mae'];out['baseline_rmse']=bm['rmse'];out['baseline_rank_corr']=bm['rank_corr'];out['mae_improvement_pct']=100*(bm['mae']-out['mae'])/bm['mae'] if bm['mae'] else 0
 return out

def evaluate(rows,pred_key='v2',baseline_key='baseline'):
 rows=[r for r in rows if r.get('actual') is not None and r.get(pred_key) is not None];out=enrich_vs_baseline(rows,pred_key,baseline_key)
 out['by_position']={}
 for pos in sorted({str(r.get('position')) for r in rows}):out['by_position'][pos]=enrich_vs_baseline([r for r in rows if str(r.get('position'))==pos],pred_key,baseline_key)
 out['by_season']={}
 for season in sorted({str(r.get('season','?')) for r in rows}):out['by_season'][season]=enrich_vs_baseline([r for r in rows if str(r.get('season','?'))==season],pred_key,baseline_key)
 byg={}
 for r in rows:byg.setdefault((str(r.get('season','?')),int(r['gw'])),[]).append(r)
 cap_v2=cap_base=oracle=0;corrs=[];wins=ties=losses=0;top5_v2=top5_base=0;rounds=0
 for _,g in sorted(byg.items()):
  elig=[r for r in g if float(r.get('expected_minutes',90))>=45]
  if not elig:continue
  rounds+=1;c=spearman([float(r[pred_key]) for r in elig],[float(r['actual']) for r in elig])
  if not math.isnan(c):corrs.append(c)
  v=max(elig,key=lambda r:float(r[pred_key]));cap_v2+=float(v['actual'])
  vtop=sorted(elig,key=lambda r:float(r[pred_key]),reverse=True)[:5];top5_v2+=mean(float(r['actual']) for r in vtop)
  if all(r.get(baseline_key) is not None for r in elig):
   bv=max(elig,key=lambda r:float(r[baseline_key]));cap_base+=float(bv['actual']);va,ba=float(v['actual']),float(bv['actual']);wins+=va>ba;ties+=va==ba;losses+=va<ba
   btop=sorted(elig,key=lambda r:float(r[baseline_key]),reverse=True)[:5];top5_base+=mean(float(r['actual']) for r in btop)
  oracle+=float(max(elig,key=lambda r:float(r['actual']))['actual'])
 out['within_gw_rank_corr']=mean(corrs) if corrs else math.nan
 out|={'captain_actual_total':cap_v2,'baseline_captain_total':cap_base,'captain_oracle_total':oracle,'captain_vs_baseline_wins':wins,'captain_vs_baseline_ties':ties,'captain_vs_baseline_losses':losses,'captain_delta':cap_v2-cap_base,'top5_actual_avg_sum':top5_v2,'baseline_top5_actual_avg_sum':top5_base,'top5_delta':top5_v2-top5_base,'gameweeks':len(byg),'evaluated_gameweeks':rounds}
 buckets=[];ordered=sorted(rows,key=lambda r:float(r[pred_key]));n=len(ordered)
 for i in range(5):
  chunk=ordered[i*n//5:(i+1)*n//5]
  if chunk:buckets.append({'bucket':i+1,'n':len(chunk),'predicted':round(mean(float(r[pred_key]) for r in chunk),3),'actual':round(mean(float(r['actual']) for r in chunk),3)})
 out['calibration_quintiles']=buckets
 return out

def main():
 ap=argparse.ArgumentParser();ap.add_argument('input');ap.add_argument('--out',default='backtest_results.json');args=ap.parse_args();path=Path(args.input);raw=path.read_bytes();rows=json.loads(raw) if path.suffix=='.json' else list(__import__('csv').DictReader(raw.decode().splitlines()));result=evaluate(list(rows));result['dataset_sha256']=hashlib.sha256(raw).hexdigest();Path(args.out).write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()

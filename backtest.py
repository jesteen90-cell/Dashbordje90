"""Walk-forward evaluation harness for FPL Model v2.

Design goals:
- Never use information from or after the GW being predicted.
- Compare v2 against simple, hard-to-beat baselines.
- Score prediction accuracy AND decision quality (ranking/captaincy).

Historical snapshots are expected as JSON/CSV exported before each deadline.
The evaluator deliberately separates model fitting from evaluation so future
features cannot accidentally leak into the target gameweek.
"""
from __future__ import annotations
import argparse, json, math
from pathlib import Path
from statistics import mean


def mae(pred, actual):
    return mean(abs(p-a) for p,a in zip(pred,actual)) if pred else math.nan

def rmse(pred, actual):
    return math.sqrt(mean((p-a)**2 for p,a in zip(pred,actual))) if pred else math.nan

def spearman(xs, ys):
    if len(xs)<2:return math.nan
    def ranks(a):
        order=sorted(range(len(a)),key=lambda i:a[i]); r=[0.0]*len(a); i=0
        while i<len(order):
            j=i
            while j+1<len(order) and a[order[j+1]]==a[order[i]]:j+=1
            rank=(i+j+2)/2
            for k in range(i,j+1):r[order[k]]=rank
            i=j+1
        return r
    x,y=ranks(xs),ranks(ys); mx,my=mean(x),mean(y)
    num=sum((a-mx)*(b-my) for a,b in zip(x,y)); den=math.sqrt(sum((a-mx)**2 for a in x)*sum((b-my)**2 for b in y))
    return num/den if den else math.nan

def evaluate(rows, pred_key='v2', baseline_key='baseline'):
    rows=[r for r in rows if r.get('actual') is not None and r.get(pred_key) is not None]
    p=[float(r[pred_key]) for r in rows]; a=[float(r['actual']) for r in rows]
    out={'n':len(rows),'mae':mae(p,a),'rmse':rmse(p,a),'rank_corr':spearman(p,a)}
    b=[r for r in rows if r.get(baseline_key) is not None]
    if b:
        bp=[float(r[baseline_key]) for r in b]; ba=[float(r['actual']) for r in b]
        out['baseline_mae']=mae(bp,ba); out['mae_improvement_pct']=100*(out['baseline_mae']-out['mae'])/out['baseline_mae'] if out['baseline_mae'] else 0
    bygw={}
    for r in rows:bygw.setdefault(int(r['gw']),[]).append(r)
    cap_v2=cap_base=oracle=0
    for _,g in sorted(bygw.items()):
        elig=[r for r in g if float(r.get('expected_minutes',90))>=45]
        if not elig:continue
        cap_v2+=float(max(elig,key=lambda r:float(r[pred_key]))['actual'])
        if all(r.get(baseline_key) is not None for r in elig):cap_base+=float(max(elig,key=lambda r:float(r[baseline_key]))['actual'])
        oracle+=float(max(elig,key=lambda r:float(r['actual']))['actual'])
    out|={'captain_actual_total':cap_v2,'baseline_captain_total':cap_base,'captain_oracle_total':oracle,'gameweeks':len(bygw)}
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('input'); ap.add_argument('--out',default='backtest_results.json'); args=ap.parse_args()
    path=Path(args.input)
    rows=json.loads(path.read_text()) if path.suffix=='.json' else __import__('csv').DictReader(path.open())
    result=evaluate(list(rows)); Path(args.out).write_text(json.dumps(result,indent=2)); print(json.dumps(result,indent=2))
if __name__=='__main__':main()

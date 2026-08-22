"""Leakage-safe calibration for Model v2 predictions.

Fits a conservative affine calibration per position using seasons strictly
before the latest (holdout) season, then applies it to every row. Holdout
results never influence fitted coefficients.
"""
from __future__ import annotations
import argparse,json
from collections import defaultdict
from pathlib import Path


def clamp(x,a,b): return max(a,min(b,x))

def fit_affine(rows):
    xs=[float(r['v2']) for r in rows]; ys=[float(r['actual']) for r in rows]
    if len(xs)<100:return 1.0,0.0
    mx=sum(xs)/len(xs); my=sum(ys)/len(ys)
    var=sum((x-mx)**2 for x in xs)
    cov=sum((x-mx)*(y-my) for x,y in zip(xs,ys))
    slope=cov/var if var>1e-9 else 1.0
    # Conservative clipping protects against unstable seasonal fits.
    slope=clamp(slope,.65,1.25)
    intercept=clamp(my-slope*mx,-1.0,1.0)
    return slope,intercept

def main():
    ap=argparse.ArgumentParser();ap.add_argument('input');ap.add_argument('--out',default='backtest_dataset_calibrated.json');ap.add_argument('--params',default='calibration_params.json');a=ap.parse_args()
    rows=json.loads(Path(a.input).read_text())
    seasons=sorted({str(r['season']) for r in rows});holdout=seasons[-1];train=[r for r in rows if str(r['season'])!=holdout]
    bypos=defaultdict(list)
    for r in train:bypos[str(r.get('position'))].append(r)
    params={}
    for pos,rr in sorted(bypos.items()):
        slope,intercept=fit_affine(rr);params[pos]={'slope':round(slope,6),'intercept':round(intercept,6),'n':len(rr)}
    out=[]
    for r in rows:
        p=params.get(str(r.get('position')),{'slope':1.0,'intercept':0.0});z=dict(r);z['v2_raw']=float(r['v2']);z['v2']=round(clamp(p['slope']*float(r['v2'])+p['intercept'],0,16),4);out.append(z)
    meta={'holdout_season':holdout,'train_seasons':[s for s in seasons if s!=holdout],'by_position':params}
    Path(a.out).write_text(json.dumps(out,ensure_ascii=False));Path(a.params).write_text(json.dumps(meta,indent=2));print(json.dumps(meta,indent=2))
if __name__=='__main__':main()

#!/usr/bin/env python3
import argparse,json,math
from collections import defaultdict

def n(x,d=0.0):
 try:return float(x)
 except:return d

def main():
 ap=argparse.ArgumentParser();ap.add_argument('dataset');ap.add_argument('--out',default='uncertainty_status.json');a=ap.parse_args();rows=json.load(open(a.dataset));seasons=sorted({r['season'] for r in rows});hold=seasons[-1];rs=[r for r in rows if r['season']==hold and r.get('p10') is not None and r.get('p90') is not None]
 inside=sum(n(r['p10'])<=n(r['actual'])<=n(r['p90']) for r in rs);coverage=inside/len(rs) if rs else 0
 widths=[n(r['p90'])-n(r['p10']) for r in rs];mean_width=sum(widths)/len(widths) if widths else 0
 # Coverage by position catches badly calibrated uncertainty for one role.
 bypos={}
 for pos in sorted({str(r['position']) for r in rs}):
  g=[r for r in rs if str(r['position'])==pos];c=sum(n(r['p10'])<=n(r['actual'])<=n(r['p90']) for r in g)/len(g);bypos[pos]={'n':len(g),'coverage':round(c,4),'mean_width':round(sum(n(r['p90'])-n(r['p10']) for r in g)/len(g),3)}
 # An 80% interval is acceptable if empirical coverage is not grossly under-dispersed.
 valid=len(rs)>=1500 and .68<=coverage<=.96 and all(.62<=v['coverage']<=.98 for v in bypos.values())
 out={'holdout_season':hold,'n':len(rs),'target_coverage':0.8,'coverage':round(coverage,4),'mean_interval_width':round(mean_width,3),'by_position':bypos,'valid':valid}
 json.dump(out,open(a.out,'w'),indent=2);print(json.dumps(out,indent=2))
 if not valid:raise SystemExit('Predictive intervals fail calibration gate')
if __name__=='__main__':main()

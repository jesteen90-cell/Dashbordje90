"""Train-only captain ranking experiment for Model v2.

Searches a deliberately small coefficient grid on pre-holdout seasons only,
then evaluates the frozen captain score on the latest holdout season.
"""
from __future__ import annotations
import argparse,itertools,json
from collections import defaultdict
from pathlib import Path


def groups(rows):
    g=defaultdict(list)
    for r in rows:g[(str(r['season']),int(r['gw']))].append(r)
    return g

def score(r,a,b,c):
    # Main signal stays xP. Small modifiers test fixture upside, minutes security,
    # and attacking-position captain preference without replacing xP.
    pos=int(r.get('position',3))
    attacking=1.0 if pos in (3,4) else 0.0
    return float(r['v2']) + a*(float(r.get('attack_multiplier',1))-1) + b*(float(r.get('expected_minutes',0))/90-.75) + c*attacking

def captain_total(rows,a,b,c):
    total=0;count=0
    for _,rr in sorted(groups(rows).items()):
        elig=[r for r in rr if float(r.get('expected_minutes',0))>=45]
        if not elig:continue
        pick=max(elig,key=lambda r:score(r,a,b,c));total+=float(pick['actual']);count+=1
    return total,count

def base_total(rows):return captain_total(rows,0,0,0)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('input');ap.add_argument('--out',default='captain_v2_status.json');a=ap.parse_args();rows=json.loads(Path(a.input).read_text());seasons=sorted({str(r['season']) for r in rows});holdout=seasons[-1];train=[r for r in rows if str(r['season'])!=holdout];test=[r for r in rows if str(r['season'])==holdout]
    grid={'fixture':[-.5,0,.5,1.0],'minutes':[0,.25,.5,1.0],'attacking':[0,.10,.20,.35]}
    best=None
    for aa,bb,cc in itertools.product(grid['fixture'],grid['minutes'],grid['attacking']):
        total,n=captain_total(train,aa,bb,cc)
        # Tiny regularization: prefer simpler coefficients when totals tie.
        objective=total-.02*(abs(aa)+abs(bb)+abs(cc))
        if best is None or objective>best[0]:best=(objective,total,n,aa,bb,cc)
    _,train_total,train_n,aa,bb,cc=best
    test_total,test_n=captain_total(test,aa,bb,cc);base_train,_=base_total(train);base_test,_=base_total(test)
    out={'holdout_season':holdout,'train_seasons':[s for s in seasons if s!=holdout],'params':{'fixture':aa,'minutes':bb,'attacking':cc},'train':{'gameweeks':train_n,'optimized_total':train_total,'plain_xp_total':base_train,'delta':train_total-base_train},'holdout':{'gameweeks':test_n,'optimized_total':test_total,'plain_xp_total':base_test,'delta':test_total-base_test},'promote':bool(test_total>=base_test)}
    Path(a.out).write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
if __name__=='__main__':main()

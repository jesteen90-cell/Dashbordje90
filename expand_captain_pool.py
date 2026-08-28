from __future__ import annotations
"""Expand captain candidate pool to all 11 starters before v4/v4.1 scoring.

The dashboard may still display only a shortlist later, but no starting player is
allowed to be excluded from the captain model merely because Captain v3 ranked
him outside an arbitrary top-five cutoff.
"""
import json
from pathlib import Path

PATH=Path('data.json')

def n(v,d=0.0):
 try:return float(v)
 except:return d

def main():
 d=json.loads(PATH.read_text(encoding='utf-8'))
 lineup=d.get('lineup') or []
 rows=[]
 for p in lineup:
  xp=n(p.get('xp'));mins=n(p.get('expected_minutes'),90);avail=n(p.get('availability'),1)
  ceiling=max(xp,n(p.get('xp_high'),xp))
  score=xp*.70+ceiling*.20+(mins/90)*.06+avail*.04
  rows.append({'id':p.get('id'),'name':p.get('name'),'team':p.get('team'),'position':p.get('position'),'xp':round(xp,2),'ceiling':round(ceiling,2),'expected_minutes':round(mins,0),'availability':round(avail,2),'score':round(score,3),'captain':bool(p.get('captain')),'vice':bool(p.get('vice'))})
 rows.sort(key=lambda x:x['score'],reverse=True)
 d['captain_comparison']=rows
 d['captain_pool']={'version':'1.0-all-xi','candidate_count':len(rows),'policy':'all starting XI evaluated; display shortlist applied after model selection'}
 PATH.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
 print('Expanded captain pool to',len(rows),'starters:',', '.join(x.get('name') or '?' for x in rows))
if __name__=='__main__':main()

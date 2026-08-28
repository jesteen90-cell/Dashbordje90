"""Optional bookmaker-market ensemble for fixture goal expectations.

Reads market_odds.json when present. Internal team-strength remains the prior.
A/B-tuned weights are consumed only after frozen evaluation has promoted them.
Missing, stale, invalid or unpromoted market data safely falls back to the
conservative default blend or 100% internal ratings.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

PATH=Path('market_odds.json');PARAMS=Path('market_ab/params.json')
MAX_AGE_HOURS=30;DEFAULT_MAX=.65;DEFAULT_MIN=.20

def clamp(x,a,b): return max(a,min(b,x))
def _dt(v):
 try:return datetime.fromisoformat(str(v).replace('Z','+00:00'))
 except:return None

def weight_params():
 cap,low,promoted=DEFAULT_MAX,DEFAULT_MIN,False
 if PARAMS.exists():
  try:
   d=json.loads(PARAMS.read_text(encoding='utf-8'))
   if d.get('promoted'):
    cap=clamp(float(d.get('market_weight_cap',cap)),.20,.75);low=clamp(float(d.get('min_market_weight',low)),.08,min(.40,cap));promoted=True
  except:pass
 return low,cap,promoted

def load_market(now=None):
 now=now or datetime.now(timezone.utc);low,cap,promoted=weight_params()
 meta={'weight_cap':round(cap,2),'weight_floor':round(low,2),'ab_promoted':promoted}
 if not PATH.exists(): return {},{**meta,'available':False,'reason':'market_odds.json missing'}
 try:d=json.loads(PATH.read_text(encoding='utf-8'))
 except Exception:return {},{**meta,'available':False,'reason':'invalid market_odds.json'}
 stamp=_dt(d.get('generated_at'));age=(now-stamp).total_seconds()/3600 if stamp else 1e9
 if age>MAX_AGE_HOURS:return {},{**meta,'available':False,'reason':f'market data stale ({age:.1f}h)'}
 rows={str(k):v for k,v in (d.get('fixtures') or {}).items()}
 return rows,{**meta,'available':bool(rows),'reason':'ok' if rows else 'no fixture rows','age_hours':round(age,2),'fixture_count':len(rows)}

def blend_lambda(internal_lambda,fixture_id,team_is_home,market):
 row=market.get(str(fixture_id)) or {};key='home_xg' if team_is_home else 'away_xg';low,cap,_=weight_params()
 try:m=float(row[key]);conf=clamp(float(row.get('confidence',1)),0,1)
 except:return float(internal_lambda),0.0,None
 if not .15<=m<=4.5:return float(internal_lambda),0.0,None
 w=clamp(low+(cap-low)*conf,low,cap);val=(1-w)*float(internal_lambda)+w*m
 return val,w,m

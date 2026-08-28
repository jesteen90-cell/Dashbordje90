"""Optional bookmaker-market ensemble for fixture goal expectations.

Reads market_odds.json when present. Internal team-strength remains the prior.
Market input is never required: stale/low-confidence/missing data falls back to
100% internal ratings. This lets us validate market blending before promoting it.

Expected schema:
{
  "generated_at": "2026-08-28T06:00:00Z",
  "fixtures": {
    "123": {"home_xg": 1.72, "away_xg": 1.03, "confidence": 0.9}
  }
}
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

PATH=Path('market_odds.json')
MAX_AGE_HOURS=30
MAX_MARKET_WEIGHT=.65
MIN_MARKET_WEIGHT=.20

def clamp(x,a,b): return max(a,min(b,x))
def _dt(v):
 try:return datetime.fromisoformat(str(v).replace('Z','+00:00'))
 except:return None

def load_market(now=None):
 now=now or datetime.now(timezone.utc)
 if not PATH.exists(): return {},{'available':False,'reason':'market_odds.json missing','weight_cap':MAX_MARKET_WEIGHT}
 try:d=json.loads(PATH.read_text(encoding='utf-8'))
 except Exception:return {},{'available':False,'reason':'invalid market_odds.json','weight_cap':MAX_MARKET_WEIGHT}
 stamp=_dt(d.get('generated_at'));age=(now-stamp).total_seconds()/3600 if stamp else 1e9
 if age>MAX_AGE_HOURS:return {},{'available':False,'reason':f'market data stale ({age:.1f}h)','weight_cap':MAX_MARKET_WEIGHT}
 rows={str(k):v for k,v in (d.get('fixtures') or {}).items()}
 return rows,{'available':bool(rows),'reason':'ok' if rows else 'no fixture rows','age_hours':round(age,2),'fixture_count':len(rows),'weight_cap':MAX_MARKET_WEIGHT}

def blend_lambda(internal_lambda,fixture_id,team_is_home,market):
 row=market.get(str(fixture_id)) or {}
 key='home_xg' if team_is_home else 'away_xg'
 try:m=float(row[key]);conf=clamp(float(row.get('confidence',1)),0,1)
 except:return float(internal_lambda),0.0,None
 if not .15<=m<=4.5:return float(internal_lambda),0.0,None
 # Confidence controls market weight. Internal model always retains >=35%.
 w=clamp(MIN_MARKET_WEIGHT+(MAX_MARKET_WEIGHT-MIN_MARKET_WEIGHT)*conf,MIN_MARKET_WEIGHT,MAX_MARKET_WEIGHT)
 val=(1-w)*float(internal_lambda)+w*m
 return val,w,m

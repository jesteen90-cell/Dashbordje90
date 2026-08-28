"""Allocate team attacking expectation to individual players.

Uses pre-deadline FPL xG/xA and minutes with position priors. The output is a
shrunk per-90 attacking share, designed for shadow validation before production.
"""
from __future__ import annotations
from collections import defaultdict

POS_GOAL_PRIOR={1:.01,2:.045,3:.18,4:.28}
POS_ASSIST_PRIOR={1:.01,2:.07,3:.17,4:.14}

def n(v,d=0.0):
 try:return float(v)
 except:return d

def clamp(x,a,b):return max(a,min(b,x))

def build_player_shares(players):
 by_team=defaultdict(list)
 for p in players:by_team[int(p['team'])].append(p)
 out={}
 for tid,ps in by_team.items():
  raw=[]
  for p in ps:
   mins=max(0.0,n(p.get('minutes')));pos=int(p.get('element_type') or 3)
   xg=n(p.get('expected_goals'));xa=n(p.get('expected_assists'))
   # season xG/xA per 90, strongly shrunk when minutes are sparse
   g90=(xg*90/max(mins,90)) if mins>0 else 0.0;a90=(xa*90/max(mins,90)) if mins>0 else 0.0
   w=mins/(mins+540.0)
   sg=(1-w)*POS_GOAL_PRIOR.get(pos,.15)+w*g90
   sa=(1-w)*POS_ASSIST_PRIOR.get(pos,.14)+w*a90
   raw.append((int(p['id']),max(.001,sg),max(.001,sa),mins))
  gden=sum(x[1] for x in raw);aden=sum(x[2] for x in raw)
  for pid,g,a,mins in raw:
   out[pid]={'goal_share_rate':g/gden if gden else 0,'assist_share_rate':a/aden if aden else 0,'evidence_minutes':mins}
 return out

def allocated_rates(player,shares,team_xg,expected_minutes):
 """Convert team xG into individual goal/assist per-90 rates.

 Shares are normalized rate shares, then re-expanded to the player's expected
 playing time. Caps avoid extreme early-season allocations.
 """
 s=shares.get(int(player['id'])) or {};mins=max(1.0,float(expected_minutes));team_xg=max(.15,float(team_xg))
 gshare=clamp(float(s.get('goal_share_rate',0)),0,.45);ashare=clamp(float(s.get('assist_share_rate',0)),0,.45)
 # Team attacking events are distributed among likely contributors. Multiplying
 # by 90/xMins returns the rate consumed by the core projection's minute fraction.
 g90=team_xg*gshare*90/mins
 a90=team_xg*ashare*.78*90/mins
 return {'goal90':clamp(g90,0,1.25),'assist90':clamp(a90,0,1.10),'goal_share':gshare,'assist_share':ashare}

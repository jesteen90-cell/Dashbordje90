"""Captain persistent-elite prior with previous-season stabilization.

Current-GW xP remains dominant. Previous-season production only stabilizes early
season estimates and fades automatically as current-season minutes accumulate.
"""
from __future__ import annotations

def clamp(x,a,b): return max(a,min(b,x))
def n(v,d=0.0):
 try:return float(v)
 except:return d

def rate90(value,minutes):
 return n(value)*90/max(n(minutes),1.0)

def blended_rate(current_value,current_minutes,prev_value,prev_minutes,prior_scale=900.0):
 cm=max(n(current_minutes),0.0);pm=max(n(prev_minutes),0.0)
 cur=rate90(current_value,cm) if cm>0 else None
 prev=rate90(prev_value,pm) if pm>0 else None
 if prev is None:return cur or 0.0
 if cur is None:return prev
 # Previous season carries at most prior_scale equivalent minutes, then fades.
 prior_mins=min(pm,prior_scale);w=cm/(cm+prior_mins) if cm+prior_mins>0 else 1.0
 return w*cur+(1-w)*prev

def elite_prior(player, proj):
 mins=max(n(player.get('minutes')),0.0);prev_mins=max(n(player.get('prev_minutes')),0.0)
 pts90=blended_rate(player.get('total_points'),mins,player.get('prev_points'),prev_mins,1050)
 goals90=blended_rate(player.get('goals_scored'),mins,player.get('prev_goals'),prev_mins,1050)
 assists90=blended_rate(player.get('assists'),mins,player.get('prev_assists'),prev_mins,900)
 # xGI is available for current season; when samples are tiny, historical goal/assist production prevents collapse.
 current_xgi90=(n(player.get('expected_goals'))+n(player.get('expected_assists')))*90/max(mins,1.0) if mins>0 else 0.0
 historical_return90=goals90+assists90
 sample_weight=mins/(mins+720.0)
 xgi90=sample_weight*current_xgi90+(1-sample_weight)*historical_return90*.78
 reliability=clamp(n(proj.get('xmins'))/90,0,1);ceiling=n(proj.get('p90'))
 raw=(.30*clamp(pts90/7.5,0,1.35)+.27*clamp(xgi90/.75,0,1.35)+.18*clamp(goals90/.65,0,1.35)+.15*reliability+.10*clamp(ceiling/12,0,1.35))
 return clamp(raw,0,1.25)

def score(player, proj, v3_score):
 prior=elite_prior(player,proj)
 return float(v3_score)+0.65*prior,prior

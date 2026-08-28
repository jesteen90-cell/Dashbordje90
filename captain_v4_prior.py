"""Captain v4 shadow: persistent elite prior without hard-coding a weekly captain.

The prior rewards repeatable captain traits (long-run FPL production, xGI,
penalties/goal threat, minutes reliability and ceiling) but is deliberately
bounded so current fixture xP remains dominant. Designed for frozen backtest
against Captain v3 before promotion.
"""
from __future__ import annotations

def clamp(x,a,b): return max(a,min(b,x))
def n(v,d=0.0):
 try:return float(v)
 except:return d

def elite_prior(player, proj):
 mins=max(n(player.get('minutes')),1.0)
 pts90=n(player.get('total_points'))*90/mins
 xgi90=(n(player.get('expected_goals'))+n(player.get('expected_assists')))*90/mins
 goals90=n(player.get('goals_scored'))*90/mins
 # Reliability is especially important for captaincy because a cameo destroys upside.
 reliability=clamp(n(proj.get('xmins'))/90,0,1)
 ceiling=n(proj.get('p90'))
 # Shrunk/bounded persistent signal. No player-name or team-specific bonus.
 raw=(.30*clamp(pts90/7.5,0,1.35)+.27*clamp(xgi90/.75,0,1.35)+.18*clamp(goals90/.65,0,1.35)+.15*reliability+.10*clamp(ceiling/12,0,1.35))
 return clamp(raw,0,1.25)

def score(player, proj, v3_score):
 prior=elite_prior(player,proj)
 # v3/current-GW signal remains dominant; persistent prior can move close calls,
 # not overturn a clearly superior fixture projection.
 return float(v3_score)+0.65*prior,prior

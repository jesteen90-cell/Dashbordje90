from __future__ import annotations
"""Captain v4.1 haul-probability layer.
Player-agnostic. Converts current projection + long-run attacking rate into
bounded probabilities of 10+/15+ point hauls and multi-return outcomes.
Designed as a shadow tie-breaker on top of Captain v4.
"""
import math

def clamp(x,a,b): return max(a,min(b,x))
def n(v,d=0.0):
 try:return float(v)
 except:return d

def poisson_tail(lam,k):
 lam=max(0.0,lam)
 cdf=sum(math.exp(-lam)*(lam**i)/math.factorial(i) for i in range(k))
 return clamp(1-cdf,0,1)

def haul_features(player,proj):
 mins=max(n(player.get('minutes')),1.0); xmins=clamp(n(proj.get('xmins'),90),0,90)
 season_xg=n(player.get('expected_goals')); season_xa=n(player.get('expected_assists')); goals=n(player.get('goals_scored')); assists=n(player.get('assists'))
 # Shrink one-season attacking rates toward conservative position-agnostic priors.
 prior_mins=720.0
 xg90=(season_xg*90 + .38*prior_mins)/(mins+prior_mins)
 xa90=(season_xa*90 + .22*prior_mins)/(mins+prior_mins)
 goal90=(goals*90 + .28*prior_mins)/(mins+prior_mins)
 assist90=(assists*90 + .16*prior_mins)/(mins+prior_mins)
 # Blend xG/xA with realised rates, then scale by projected minutes and current fixture attack signal.
 g90=.68*xg90+.32*goal90; a90=.72*xa90+.28*assist90
 attack_mult=clamp(n(proj.get('attack_multiplier'),1.0),.55,1.75)
 goal_lambda=max(.01,g90*(xmins/90)*attack_mult); assist_lambda=max(.01,a90*(xmins/90)*attack_mult)
 p_goal_1=poisson_tail(goal_lambda,1); p_goal_2=poisson_tail(goal_lambda,2); p_goal_3=poisson_tail(goal_lambda,3)
 p_assist_1=poisson_tail(assist_lambda,1)
 # Approximate multiple attacking returns from independent goal/assist Poisson rates.
 return_lambda=goal_lambda+assist_lambda
 p_multi_return=poisson_tail(return_lambda,2)
 # Use projection ceiling and multi-return probabilities for FPL haul tails.
 xp=n(proj.get('xp')); ceiling=max(xp,n(proj.get('p90'),xp))
 p10=clamp(.48*p_multi_return+.22*p_goal_2+.18*max(0,(ceiling-8)/8)+.12*max(0,(xp-5)/6),0,.90)
 p15=clamp(.42*p_goal_2+.18*p_goal_3+.25*max(0,(ceiling-12)/10)+.15*max(0,(xp-7)/7),0,.65)
 return {'goal_lambda':goal_lambda,'assist_lambda':assist_lambda,'p_goal_1':p_goal_1,'p_goal_2':p_goal_2,'p_goal_3':p_goal_3,'p_multi_return':p_multi_return,'p10':p10,'p15':p15}

def haul_bonus(player,proj):
 f=haul_features(player,proj)
 # Max roughly +0.9 score. Enough to resolve close captain calls, not overwrite a clear xP edge.
 bonus=clamp(.55*f['p10']+.70*f['p15']+.25*f['p_multi_return']+.12*f['p_goal_2'],0,.90)
 return bonus,f

from __future__ import annotations
"""Captain haul-probability layer with early-season historical stabilization."""
import math

def clamp(x,a,b): return max(a,min(b,x))
def n(v,d=0.0):
 try:return float(v)
 except:return d

def poisson_tail(lam,k):
 lam=max(0.0,lam);cdf=sum(math.exp(-lam)*(lam**i)/math.factorial(i) for i in range(k));return clamp(1-cdf,0,1)

def r90(value,minutes):return n(value)*90/max(n(minutes),1.0)
def blend_rate(cur_v,cur_m,prev_v,prev_m,prior_mins=900.0):
 cm=max(n(cur_m),0);pm=max(n(prev_m),0);cur=r90(cur_v,cm) if cm>0 else None;prev=r90(prev_v,pm) if pm>0 else None
 if prev is None:return cur or 0.0
 if cur is None:return prev
 pm=min(pm,prior_mins);w=cm/(cm+pm) if cm+pm else 1;return w*cur+(1-w)*prev

def haul_features(player,proj):
 mins=max(n(player.get('minutes')),0.0);prev_mins=max(n(player.get('prev_minutes')),0.0);xmins=clamp(n(proj.get('xmins'),90),0,90)
 season_xg=n(player.get('expected_goals'));season_xa=n(player.get('expected_assists'))
 hist_goal90=blend_rate(player.get('goals_scored'),mins,player.get('prev_goals'),prev_mins,1050)
 hist_assist90=blend_rate(player.get('assists'),mins,player.get('prev_assists'),prev_mins,900)
 # Current xG/xA gains weight as current-season minutes accumulate; historical production stabilizes the opening weeks.
 w=mins/(mins+720.0)
 current_xg90=season_xg*90/max(mins,1.0) if mins>0 else 0.0;current_xa90=season_xa*90/max(mins,1.0) if mins>0 else 0.0
 xg90=w*current_xg90+(1-w)*hist_goal90*.90;xa90=w*current_xa90+(1-w)*hist_assist90*.90
 g90=.68*xg90+.32*hist_goal90;a90=.72*xa90+.28*hist_assist90
 attack_mult=clamp(n(proj.get('attack_multiplier'),1.0),.55,1.75)
 goal_lambda=max(.01,g90*(xmins/90)*attack_mult);assist_lambda=max(.01,a90*(xmins/90)*attack_mult)
 p_goal_1=poisson_tail(goal_lambda,1);p_goal_2=poisson_tail(goal_lambda,2);p_goal_3=poisson_tail(goal_lambda,3);return_lambda=goal_lambda+assist_lambda;p_multi_return=poisson_tail(return_lambda,2)
 xp=n(proj.get('xp'));ceiling=max(xp,n(proj.get('p90'),xp))
 p10=clamp(.48*p_multi_return+.22*p_goal_2+.18*max(0,(ceiling-8)/8)+.12*max(0,(xp-5)/6),0,.90)
 p15=clamp(.42*p_goal_2+.18*p_goal_3+.25*max(0,(ceiling-12)/10)+.15*max(0,(xp-7)/7),0,.65)
 return {'goal_lambda':goal_lambda,'assist_lambda':assist_lambda,'p_goal_1':p_goal_1,'p_goal_2':p_goal_2,'p_goal_3':p_goal_3,'p_multi_return':p_multi_return,'p10':p10,'p15':p15,'history_weight':round(1-w,4)}

def haul_bonus(player,proj):
 f=haul_features(player,proj);bonus=clamp(.55*f['p10']+.70*f['p15']+.25*f['p_multi_return']+.12*f['p_goal_2'],0,.90);return bonus,f

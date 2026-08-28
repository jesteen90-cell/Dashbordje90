"""FPL Model shared core.

Component expected-points engine for live projection and walk-forward tests.
Inputs must be pre-deadline features only. Model 4.2 adds explicit, bounded
penalty-save and penalty-miss expectation using the official +5/-2 scoring.
"""
from __future__ import annotations
import math
GOAL_PTS={1:6,2:6,3:5,4:4};CS_PTS={1:4,2:4,3:1,4:0};Z80=1.2815515655446004

def clamp(x,a=0.0,b=1.0):return max(a,min(b,x))
def poisson_pmf(k,lam):return math.exp(-lam)*(lam**k)/math.factorial(k)
def p_ge(k,lam):return 1-sum(poisson_pmf(i,lam) for i in range(k))
def negbin_pmf(k,mean,dispersion):
 mean=max(.0001,float(mean));r=max(.25,float(dispersion));p=r/(r+mean);return math.exp(math.lgamma(k+r)-math.lgamma(r)-math.lgamma(k+1)+r*math.log(p)+k*math.log1p(-p))
def defcon_threshold_probability(mean,threshold,position):
 r={2:8.0,3:6.0,4:5.0}.get(int(position),6.0);m=max(.0001,float(mean));t=max(1,int(threshold));return clamp(1-sum(negbin_pmf(k,m,r) for k in range(t)))
def expected_save_points(mean_saves):
 lam=max(0.0,float(mean_saves or 0));
 if lam<=0:return 0.0
 return sum((k//3)*poisson_pmf(k,lam) for k in range(1,31))
def goalkeeper_save_multiplier(opponent_goal_lambda,baseline=1.35):
 lam=max(.05,float(opponent_goal_lambda or baseline));ratio=lam/max(.05,float(baseline));return clamp(ratio**.38,.78,1.28)
def penalty_components(inp,pos,frac,availability):
 """Expected direct FPL penalty points, separate from goal expectation.

 penalty_save90 / penalty_miss90 are observed event rates per 90 when supplied.
 They are strongly shrunk because penalties are rare. penalty_taker_share can be
 supplied by richer upstream data later; absent that, no speculative miss cost
 is invented. Values are capped to stop tiny samples dominating projections.
 """
 if pos==1:
  rate=clamp(float(inp.get('penalty_save90',0) or 0),0,.35);mins=max(0,float(inp.get('minutes_history',0) or 0));used=beta_shrink(rate,mins,.018,1800);pts=5*used*frac
  return pts,0.0,used,0.0
 miss_rate=clamp(float(inp.get('penalty_miss90',0) or 0),0,.25);share=clamp(float(inp.get('penalty_taker_share',0) or 0));mins=max(0,float(inp.get('minutes_history',0) or 0));used=beta_shrink(miss_rate,mins,.012*share,1800) if (miss_rate>0 or share>0) else 0.0;miss=-2*used*frac*availability
 return 0.0,miss,0.0,used
def beta_shrink(rate,minutes,prior,prior_minutes=900):
 w=max(0.0,minutes)/(max(0.0,minutes)+prior_minutes);return w*max(0.0,rate)+(1-w)*prior

def bonus_prior_2627(position):return {1:.29,2:.26,3:.41,4:.43}.get(int(position),.35)
def attack_evidence_minutes(current_minutes,recent_minutes=0.0,recent_confidence=0.0):
 cm=max(0.0,float(current_minutes or 0));rm=max(0.0,float(recent_minutes or 0));rc=clamp(float(recent_confidence or 0));return min(1800.0,cm+min(360.0,rm)*rc*.35)
def historical_attack_prior(position_prior,prev_rate,prev_minutes,history_strength=900.0):
 pm=max(0.0,float(prev_minutes or 0));pr=max(0.0,float(prev_rate or 0))
 if pm<=0:return position_prior
 w=pm/(pm+history_strength);return clamp(position_prior+w*(pr-position_prior),position_prior*.35,max(position_prior*3.2,position_prior+.05))
def stabilized_role(start_rate,sub_rate,minutes_history,position,prev_minutes=0.0):
 sr=clamp(float(start_rate));br=clamp(float(sub_rate));mins=max(0.0,float(minutes_history));pm=max(0.0,float(prev_minutes or 0))
 if mins<=0:return sr,br
 base_start={1:.62,2:.66,3:.64,4:.62}.get(int(position),.64);base_sub={1:.02,2:.10,3:.14,4:.16}.get(int(position),.12)
 if pm>0:
  season_share=clamp(pm/(38*90),0,.96);hist_w=clamp(pm/(pm+900.0),0,.78);prior_start=clamp(base_start*(1-hist_w)+season_share*hist_w,.18,.94);prior_sub=clamp(base_sub*(1-hist_w)+max(.02,1-prior_start)*.35*hist_w,.01,.28)
 else:prior_start,prior_sub=base_start,base_sub
 current_w=mins/(mins+180.0);out_start=(1-current_w)*prior_start+current_w*sr;out_sub=(1-current_w)*prior_sub+current_w*br
 if out_start+out_sub>1:z=out_start+out_sub;out_start/=z;out_sub/=z
 return clamp(out_start),clamp(out_sub)
def minutes_distribution(start_rate,avg_start_mins,sub_rate,avg_sub_mins,availability=1.0):
 availability=clamp(availability);ps=clamp(start_rate)*availability;psub=clamp(sub_rate)*availability
 if ps+psub>availability:scale=availability/(ps+psub);ps*=scale;psub*=scale
 p0=1-ps-psub;sm=clamp(avg_start_mins/90,0,1)*90;bm=clamp(avg_sub_mins/45,0,1)*45;p60_start=clamp((sm-48)/20);p60=ps*p60_start;xmins=ps*sm+psub*bm;p_app=ps+psub;minute_var=max(0,ps*(sm-xmins)**2+psub*(bm-xmins)**2+p0*xmins**2)
 return {'p_start':ps,'p_sub':psub,'p_zero':p0,'p_60':p60,'xmins':xmins,'avg_start_mins':sm,'avg_sub_mins':bm,'minute_variance':minute_var,'appearance_pts':p_app+p60}
def clean_sheet_probability(lam,md):return math.exp(-max(.01,lam)*clamp(md.get('avg_start_mins',90)/90,.67,1.0))
def expected_conceded_deduction(lam,md):
 papp=md.get('p_start',0)+md.get('p_sub',0)
 if papp<=0:return 0.0
 conditional_minutes=clamp(md.get('xmins',0)/papp,0,90);on_pitch_lam=max(.01,lam)*conditional_minutes/90;return -papp*sum((k//2)*poisson_pmf(k,on_pitch_lam) for k in range(2,10))
def uncertainty(mean,md,pos,g_rate,a_rate,cs_prob,frac,save90,dc_prob,bonus,penalty_variance=0):
 papp=md['p_start']+md['p_sub'];eapp=md['appearance_pts'];eapp2=max(0,papp-md['p_60'])+md['p_60']*4;v_app=max(0,eapp2-eapp*eapp);vg=(GOAL_PTS[pos]**2)*max(0,g_rate*frac);va=9*max(0,a_rate*frac);pcs=md['p_60']*cs_prob;vcs=(CS_PTS[pos]**2)*pcs*(1-pcs);vs=max(0,save90)*frac/9 if pos==1 else 0;vdc=4*dc_prob*(1-dc_prob) if pos in (2,3,4) else 0;vb=max(.10,bonus*(1.35-bonus/3)) if bonus>0 else .08;minute_cv2=md.get('minute_variance',0)/8100;v_role=min(mean*mean*.45,mean*mean*.32*minute_cv2);raw=v_app+vg+va+vcs+vs+vdc+vb+v_role+max(0,penalty_variance);variance=max(.35,raw*1.18+.12*mean*mean);sd=math.sqrt(variance);p10=max(0,mean-Z80*sd);p90=max(p10,mean+Z80*sd);return {'variance':variance,'sd':sd,'p10':p10,'p90':p90,'volatility':sd/max(mean,1.0),'role_variance':v_role,'minute_variance':md.get('minute_variance',0)}
def project(inp):
 pos=int(inp['position']);avail=clamp(float(inp.get('availability',1)));hist=float(inp.get('minutes_history',0));prev_mins=float(inp.get('prev_minutes',0) or 0);sr,sub=stabilized_role(float(inp.get('start_rate',.7)),float(inp.get('sub_rate',.15)),hist,pos,prev_mins);md=minutes_distribution(sr,float(inp.get('avg_start_mins',78)),sub,float(inp.get('avg_sub_mins',18)),avail);frac=md['xmins']/90;atk=float(inp.get('attack_multiplier',1));gp={1:.01,2:.055,3:.20,4:.31}[pos];ap={1:.01,2:.08,3:.18,4:.15}[pos];gprior=historical_attack_prior(gp,float(inp.get('prev_goal90',0) or 0),prev_mins);aprior=historical_attack_prior(ap,float(inp.get('prev_assist90',0) or 0),prev_mins);attack_mins=attack_evidence_minutes(hist,inp.get('recent_minutes',0),inp.get('recent_confidence',0));g90=beta_shrink(float(inp.get('goal90',0)),attack_mins,gprior)*atk;a90=beta_shrink(float(inp.get('assist90',0)),attack_mins,aprior)*atk;goals=g90*frac*GOAL_PTS[pos];assists=a90*frac*3;lam=max(.05,float(inp.get('opponent_goal_lambda',1.35)));cs_prob=clean_sheet_probability(lam,md);cs=md['p_60']*cs_prob*CS_PTS[pos];conceded=expected_conceded_deduction(lam,md) if pos in (1,2) else 0;save90=max(0,float(inp.get('save90',0)));save_mult=goalkeeper_save_multiplier(lam) if pos==1 else 1.0;expected_saves=save90*frac*save_mult;saves=expected_save_points(expected_saves) if pos==1 else 0;pen_save,pen_miss,pen_save_rate,pen_miss_rate=penalty_components(inp,pos,frac,avail);penalty=pen_save+pen_miss;pen_var=(25*pen_save_rate+4*pen_miss_rate)*frac;dc=0;dc_prob=0;dc90=0
 if pos in (2,3,4):
  dc90=beta_shrink(float(inp.get('defcon90',0)),hist,{2:8.,3:7.,4:3.}[pos],720);mean_dc=max(.01,dc90*frac);threshold=10 if pos==2 else 12;dc_prob=defcon_threshold_probability(mean_dc,threshold,pos)*md['p_60'];dc=2*dc_prob
 bonus_prior=bonus_prior_2627(pos);bonus90=beta_shrink(float(inp.get('bonus90',0)),hist,bonus_prior,720);bonus=min(1.8,bonus90*frac)*avail;yellow=-clamp(float(inp.get('yellow90',0))*frac,0,.5);red=-3*clamp(float(inp.get('red90',0))*frac,0,.08);total=max(0,md['appearance_pts']+goals+assists+cs+conceded+saves+penalty+dc+bonus+yellow+red);u=uncertainty(total,md,pos,g90,a90,cs_prob,frac,save90*save_mult,dc_prob,bonus,pen_var);return {'total':total,'xmins':md['xmins'],'p_start':md['p_start'],'p_60':md['p_60'],'cs_probability':cs_prob,'defensive_exposure':round(clamp(md.get('avg_start_mins',90)/90,.67,1.0),4),'appearance':md['appearance_pts'],'goals':goals,'assists':assists,'clean_sheet':cs,'conceded':conceded,'save_fixture_multiplier':save_mult,'expected_saves':expected_saves,'saves':saves,'penalty':penalty,'penalty_save':pen_save,'penalty_miss':pen_miss,'penalty_save90_used':pen_save_rate,'penalty_miss90_used':pen_miss_rate,'defensive':dc,'defcon_probability':dc_prob,'defcon90_used':dc90,'bonus':bonus,'bonus90_used':bonus90,'bonus_prior_used':bonus_prior,'cards':yellow+red,'goal90_used':g90,'assist90_used':a90,'goal_prior_used':gprior,'assist_prior_used':aprior,'attack_evidence_minutes':attack_mins,**u}

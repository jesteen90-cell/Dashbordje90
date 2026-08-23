"""FPL Model shared core.

Component expected-points engine for live projection and walk-forward tests.
Inputs must be pre-deadline features only. The engine returns mean xP and an
uncertainty estimate. Model 3.1 also stabilizes early-season minutes so one
benching or a missing `starts` field cannot collapse a proven player to 0 xP.
"""
from __future__ import annotations
import math

GOAL_PTS={1:6,2:6,3:5,4:4}
CS_PTS={1:4,2:4,3:1,4:0}
Z80=1.2815515655446004

def clamp(x,a=0.0,b=1.0): return max(a,min(b,x))
def poisson_pmf(k,lam): return math.exp(-lam)*(lam**k)/math.factorial(k)
def p_ge(k,lam): return 1-sum(poisson_pmf(i,lam) for i in range(k))

def beta_shrink(rate, minutes, prior, prior_minutes=900):
    w=max(0.0,minutes)/(max(0.0,minutes)+prior_minutes)
    return w*max(0.0,rate)+(1-w)*prior

def stabilized_role(start_rate,sub_rate,minutes_history,position):
    """Shrink noisy early-season role observations toward conservative priors.

    After only one or two GWs, raw starts/minutes can be 0 because of a benching,
    late registration, API lag or rotation. We therefore let observed role take
    over gradually rather than treating one game as certainty.
    """
    sr=clamp(float(start_rate));br=clamp(float(sub_rate));mins=max(0.0,float(minutes_history))
    # Conservative PL starter priors by FPL position. These are deliberately
    # below nailed-player levels; observed minutes dominate after ~4 matches.
    prior_start={1:.62,2:.66,3:.64,4:.62}.get(int(position),.64)
    prior_sub={1:.02,2:.10,3:.14,4:.16}.get(int(position),.12)
    w=mins/(mins+300.0)
    out_start=(1-w)*prior_start+w*sr
    out_sub=(1-w)*prior_sub+w*br
    if out_start+out_sub>1:
        z=out_start+out_sub;out_start/=z;out_sub/=z
    return clamp(out_start),clamp(out_sub)

def minutes_distribution(start_rate, avg_start_mins, sub_rate, avg_sub_mins, availability=1.0):
    availability=clamp(availability);ps=clamp(start_rate)*availability;psub=clamp(sub_rate)*availability
    if ps+psub>availability:
        scale=availability/(ps+psub);ps*=scale;psub*=scale
    p0=1-ps-psub;sm=clamp(avg_start_mins/90,0,1)*90;bm=clamp(avg_sub_mins/45,0,1)*45
    p60_start=clamp((sm-48)/20);p60=ps*p60_start;xmins=ps*sm+psub*bm;p_app=ps+psub
    return {'p_start':ps,'p_sub':psub,'p_zero':p0,'p_60':p60,'xmins':xmins,'appearance_pts':p_app+p60}

def expected_conceded_deduction(lam,p60):
    return -p60*sum((k//2)*poisson_pmf(k,lam) for k in range(2,10))

def uncertainty(mean,md,pos,g_rate,a_rate,lam,frac,save90,dc_prob,bonus):
    papp=md['p_start']+md['p_sub'];eapp=md['appearance_pts'];eapp2=max(0,papp-md['p_60'])*1+md['p_60']*4
    v_app=max(0,eapp2-eapp*eapp);vg=(GOAL_PTS[pos]**2)*max(0,g_rate*frac);va=9*max(0,a_rate*frac)
    pcs=md['p_60']*math.exp(-lam);vcs=(CS_PTS[pos]**2)*pcs*(1-pcs);vs=(max(0,save90)*frac)/9 if pos==1 else 0
    vdc=4*dc_prob*(1-dc_prob) if pos in (2,3,4) else 0;vb=max(.10,bonus*(1.35-bonus/3)) if bonus>0 else .08
    raw=v_app+vg+va+vcs+vs+vdc+vb;variance=max(.35,raw*1.18+.12*mean*mean)
    sd=math.sqrt(variance);p10=max(0,mean-Z80*sd);p90=max(p10,mean+Z80*sd)
    return {'variance':variance,'sd':sd,'p10':p10,'p90':p90,'volatility':sd/max(mean,1.0)}

def project(inp):
    pos=int(inp['position']);avail=clamp(float(inp.get('availability',1)));hist=float(inp.get('minutes_history',0))
    sr,sub=stabilized_role(float(inp.get('start_rate',.7)),float(inp.get('sub_rate',.15)),hist,pos)
    md=minutes_distribution(sr,float(inp.get('avg_start_mins',78)),sub,float(inp.get('avg_sub_mins',18)),avail)
    frac=md['xmins']/90;atk=float(inp.get('attack_multiplier',1))
    gp={1:.01,2:.055,3:.20,4:.31}[pos];ap={1:.01,2:.08,3:.18,4:.15}[pos]
    g90=beta_shrink(float(inp.get('goal90',0)),hist,gp)*atk;a90=beta_shrink(float(inp.get('assist90',0)),hist,ap)*atk
    goals=g90*frac*GOAL_PTS[pos];assists=a90*frac*3
    lam=max(.05,float(inp.get('opponent_goal_lambda',1.35)));cs_prob=math.exp(-lam);cs=md['p_60']*cs_prob*CS_PTS[pos]
    conceded=expected_conceded_deduction(lam,md['p_60']) if pos in (1,2) else 0
    save90=max(0,float(inp.get('save90',0)));saves=(save90*frac/3) if pos==1 else 0
    dc=0;dc_prob=0
    if pos in (2,3,4):
        dc90=beta_shrink(float(inp.get('defcon90',0)),hist,{2:8.0,3:7.0,4:3.0}[pos],720);lamdc=max(.01,dc90*frac);threshold=10 if pos==2 else 12
        dc_prob=p_ge(threshold,lamdc)*md['p_60'];dc=2*dc_prob
    bonus90=beta_shrink(float(inp.get('bonus90',0)),hist,{1:.25,2:.28,3:.38,4:.40}[pos],900);bonus=min(1.8,bonus90*frac)*avail
    yellow=-clamp(float(inp.get('yellow90',0))*frac,0,.5);red=-3*clamp(float(inp.get('red90',0))*frac,0,.08)
    total=max(0,md['appearance_pts']+goals+assists+cs+conceded+saves+dc+bonus+yellow+red)
    u=uncertainty(total,md,pos,g90,a90,lam,frac,save90,dc_prob,bonus)
    return {'total':total,'xmins':md['xmins'],'p_start':md['p_start'],'p_60':md['p_60'],'cs_probability':cs_prob,'appearance':md['appearance_pts'],'goals':goals,'assists':assists,'clean_sheet':cs,'conceded':conceded,'saves':saves,'defensive':dc,'bonus':bonus,'cards':yellow+red,**u}

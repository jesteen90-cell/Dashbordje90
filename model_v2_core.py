"""FPL Model v2.1 core.

Component expected-points engine designed for both live projection and
walk-forward backtests. Inputs must be pre-deadline features only.
"""
from __future__ import annotations
import math

GOAL_PTS={1:6,2:6,3:5,4:4}
CS_PTS={1:4,2:4,3:1,4:0}


def clamp(x,a=0.0,b=1.0): return max(a,min(b,x))
def poisson_pmf(k,lam): return math.exp(-lam)*(lam**k)/math.factorial(k)
def p_ge(k,lam): return 1-sum(poisson_pmf(i,lam) for i in range(k))

def beta_shrink(rate, minutes, prior, prior_minutes=900):
    """Shrink noisy per-90 rates toward a positional prior."""
    w=max(0.0,minutes)/(max(0.0,minutes)+prior_minutes)
    return w*max(0.0,rate)+(1-w)*prior

def minutes_distribution(start_rate, avg_start_mins, sub_rate, avg_sub_mins, availability=1.0):
    """Three-state xMins model: no appearance / sub / start.

    Probabilities are explicit so 60-minute scoring is not approximated from
    average minutes. avg_start_mins is conditional on starting.
    """
    availability=clamp(availability)
    ps=clamp(start_rate)*availability
    psub=clamp(sub_rate)*availability
    if ps+psub>availability:
        scale=availability/(ps+psub); ps*=scale; psub*=scale
    p0=1-ps-psub
    sm=clamp(avg_start_mins/90,0,1)*90
    bm=clamp(avg_sub_mins/45,0,1)*45
    # Smooth probability of crossing 60 conditional on a start.
    p60_start=clamp((sm-48)/20)
    p60=ps*p60_start
    xmins=ps*sm+psub*bm
    p_app=ps+psub
    appearance=p_app+p60
    return {'p_start':ps,'p_sub':psub,'p_zero':p0,'p_60':p60,'xmins':xmins,'appearance_pts':appearance}

def expected_conceded_deduction(lam,p60):
    # GK/DEF lose 1 per two goals conceded. Sum enough Poisson mass.
    return -p60*sum((k//2)*poisson_pmf(k,lam) for k in range(2,10))

def project(inp):
    """Return xPts and transparent component breakdown.

    Required-ish keys: position (1..4), availability, start_rate,
    avg_start_mins, sub_rate, avg_sub_mins, minutes_history, goal90, assist90,
    save90, defcon90, opponent_goal_lambda, attack_multiplier.
    """
    pos=int(inp['position']); avail=clamp(float(inp.get('availability',1)))
    md=minutes_distribution(float(inp.get('start_rate',.7)),float(inp.get('avg_start_mins',78)),float(inp.get('sub_rate',.15)),float(inp.get('avg_sub_mins',18)),avail)
    frac=md['xmins']/90
    hist=float(inp.get('minutes_history',0)); atk=float(inp.get('attack_multiplier',1))
    gp={1:.01,2:.055,3:.20,4:.31}[pos]; ap={1:.01,2:.08,3:.18,4:.15}[pos]
    g90=beta_shrink(float(inp.get('goal90',0)),hist,gp)*atk
    a90=beta_shrink(float(inp.get('assist90',0)),hist,ap)*atk
    goals=g90*frac*GOAL_PTS[pos]; assists=a90*frac*3
    lam=max(.05,float(inp.get('opponent_goal_lambda',1.35)))
    cs_prob=math.exp(-lam); cs=md['p_60']*cs_prob*CS_PTS[pos]
    conceded=expected_conceded_deduction(lam,md['p_60']) if pos in (1,2) else 0
    saves=(max(0,float(inp.get('save90',0)))*frac/3) if pos==1 else 0
    # 2026/27 DC thresholds: DEF 10 CBIT; MID/FWD 12 CBIRT. Poisson proxy.
    dc=0
    if pos in (2,3,4):
        dc90=beta_shrink(float(inp.get('defcon90',0)),hist,{2:8.0,3:7.0,4:3.0}[pos],720)
        lamdc=max(.01,dc90*frac); threshold=10 if pos==2 else 12
        dc=2*p_ge(threshold,lamdc)*md['p_60']
    # Bonus prior is intentionally conservative until a dedicated BPS model is fitted.
    bonus90=beta_shrink(float(inp.get('bonus90',0)),hist,{1:.25,2:.28,3:.38,4:.40}[pos],900)
    bonus=min(1.8,bonus90*frac)*avail
    yellow=-clamp(float(inp.get('yellow90',0))*frac,0,.5)
    red=-3*clamp(float(inp.get('red90',0))*frac,0,.08)
    total=md['appearance_pts']+goals+assists+cs+conceded+saves+dc+bonus+yellow+red
    return {'total':max(0,total),'xmins':md['xmins'],'p_start':md['p_start'],'p_60':md['p_60'],'cs_probability':cs_prob,
            'appearance':md['appearance_pts'],'goals':goals,'assists':assists,'clean_sheet':cs,'conceded':conceded,'saves':saves,'defensive':dc,'bonus':bonus,'cards':yellow+red}

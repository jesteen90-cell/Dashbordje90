from __future__ import annotations
import math
from collections import defaultdict

def clamp(x,a,b):return max(a,min(b,x))

def build_strength(fixtures,teams,decay=.88,prior_matches=5.0,league_goal_rate=1.45):
    """Dynamic attack/defence ratings from completed PL fixtures.
    Recency weighted, home/away aware and shrunk to league average.
    Uses goals because the official FPL fixtures endpoint is always available;
    callers can later replace gf/ga with xG without changing the interface.
    """
    s=defaultdict(lambda:{'gf':0.,'ga':0.,'w':0.,'home_gf':0.,'home_ga':0.,'home_w':0.,'away_gf':0.,'away_ga':0.,'away_w':0.})
    done=[f for f in fixtures if f.get('finished') and f.get('team_h_score') is not None]
    done.sort(key=lambda f:(int(f.get('event') or 0),int(f.get('id') or 0)),reverse=True)
    ages=defaultdict(int)
    for f in done:
        h,a=int(f['team_h']),int(f['team_a']);hg=float(f['team_h_score']);ag=float(f['team_a_score'])
        age=max(ages[h],ages[a]);w=decay**age;ages[h]+=1;ages[a]+=1
        for t,gf,ga,home in ((h,hg,ag,True),(a,ag,hg,False)):
            x=s[t];x['gf']+=gf*w;x['ga']+=ga*w;x['w']+=w
            k='home' if home else 'away';x[k+'_gf']+=gf*w;x[k+'_ga']+=ga*w;x[k+'_w']+=w
    out={}
    for tid in teams:
        x=s[tid];den=x['w']+prior_matches
        gf=(x['gf']+league_goal_rate*prior_matches)/den;ga=(x['ga']+league_goal_rate*prior_matches)/den
        hw=x['home_w']+prior_matches/2;aw=x['away_w']+prior_matches/2
        hgf=(x['home_gf']+league_goal_rate*1.08*prior_matches/2)/hw;hga=(x['home_ga']+league_goal_rate*.92*prior_matches/2)/hw
        agf=(x['away_gf']+league_goal_rate*.92*prior_matches/2)/aw;aga=(x['away_ga']+league_goal_rate*1.08*prior_matches/2)/aw
        out[tid]={'attack':gf/league_goal_rate,'defence':ga/league_goal_rate,'home_attack':hgf/league_goal_rate,'home_defence':hga/league_goal_rate,'away_attack':agf/league_goal_rate,'away_defence':aga/league_goal_rate,'sample_weight':x['w']}
    return out

def fixture_factors(ratings,team,opp,is_home,league_goal_rate=1.45):
    t=ratings.get(team,{});o=ratings.get(opp,{})
    ta=t.get('home_attack' if is_home else 'away_attack',t.get('attack',1));td=t.get('home_defence' if is_home else 'away_defence',t.get('defence',1))
    oa=o.get('away_attack' if is_home else 'home_attack',o.get('attack',1));od=o.get('away_defence' if is_home else 'home_defence',o.get('defence',1))
    attack=math.sqrt(max(.35,ta)*max(.35,od));opp_lambda=league_goal_rate*math.sqrt(max(.35,oa)*max(.35,td))
    return clamp(attack,.55,1.75),clamp(opp_lambda,.35,3.0)

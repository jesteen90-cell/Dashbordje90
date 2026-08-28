from __future__ import annotations
import json,math
from pathlib import Path
from collections import defaultdict
def clamp(x,a,b):return max(a,min(b,x))
def _prior_payload(path='team_strength_prior.json'):
 p=Path(path)
 if not p.exists():return {},False,'missing'
 try:
  d=json.loads(p.read_text());return (d.get('teams') or {}),bool(d.get('available')),str(d.get('version') or 'unknown')
 except:return {},False,'invalid'
def _table_prior(teams):
 """Conservative early-season fallback from FPL's current public team table.

 This is deliberately much weaker than a real strength prior. It only prevents
 every club being treated as identical when legacy attack/defence fields vanish.
 Position is shrunk heavily toward league average and fades as matches accrue.
 """
 rows=[]
 for tid,t in teams.items():
  if isinstance(t,dict):
   pos=float(t.get('position') or t.get('rank') or 0);pts=float(t.get('points') or 0)
  else: pos=pts=0
  if pos>0: rows.append((int(tid),pos,pts))
 if len(rows)<10:return {}
 nteams=len(rows);out={}
 for tid,pos,pts in rows:
  rank_signal=((nteams+1)/2-pos)/max((nteams-1)/2,1)
  # Tiny signal by design: at season start table rank is extremely noisy.
  atk=clamp(1+.075*rank_signal,.91,1.09);deff=clamp(1-.075*rank_signal,.91,1.09)
  out[str(tid)]={'home_attack':atk*1.035,'away_attack':atk*.965,'home_defence':deff*.965,'away_defence':deff*1.035}
 return out
def build_strength(fixtures,teams,decay=.88,prior_matches=5.0,league_goal_rate=1.45):
 pri,prior_available,prior_version=_prior_payload();table_pri=_table_prior(teams) if not prior_available else {};s=defaultdict(lambda:{'gf':0.,'ga':0.,'w':0.,'home_gf':0.,'home_ga':0.,'home_w':0.,'away_gf':0.,'away_ga':0.,'away_w':0.});done=[f for f in fixtures if f.get('finished') and f.get('team_h_score') is not None];done.sort(key=lambda f:(int(f.get('event') or 0),int(f.get('id') or 0)),reverse=True);ages=defaultdict(int)
 for f in done:
  h,a=int(f['team_h']),int(f['team_a']);hg=float(f['team_h_score']);ag=float(f['team_a_score']);age=max(ages[h],ages[a]);w=decay**age;ages[h]+=1;ages[a]+=1
  for t,gf,ga,home in ((h,hg,ag,True),(a,ag,hg,False)):
   x=s[t];x['gf']+=gf*w;x['ga']+=ga*w;x['w']+=w;k='home' if home else 'away';x[k+'_gf']+=gf*w;x[k+'_ga']+=ga*w;x[k+'_w']+=w
 out={}
 for tid in teams:
  x=s[tid];pr=pri.get(str(tid),{}) if prior_available else table_pri.get(str(tid),{})
  source='fpl-bootstrap' if prior_available and pr else ('table-shrunk' if pr else 'neutral-fallback')
  # Table fallback is weaker than the legacy FPL prior and fades faster.
  pm=prior_matches if source=='fpl-bootstrap' else (2.0 if source=='table-shrunk' else 1.0)
  pa=float(pr.get('home_attack',1.0)) if pr else 1.0;pda=float(pr.get('home_defence',1.0)) if pr else 1.0;paa=float(pr.get('away_attack',1.0)) if pr else 1.0;pdaa=float(pr.get('away_defence',1.0)) if pr else 1.0
  overall_attack=(pa+paa)/2;overall_defence=(pda+pdaa)/2
  den=x['w']+pm;gf=(x['gf']+league_goal_rate*overall_attack*pm)/den;ga=(x['ga']+league_goal_rate*overall_defence*pm)/den
  hw=x['home_w']+pm/2;aw=x['away_w']+pm/2
  hgf=(x['home_gf']+league_goal_rate*pa*pm/2)/hw;hga=(x['home_ga']+league_goal_rate*pda*pm/2)/hw;agf=(x['away_gf']+league_goal_rate*paa*pm/2)/aw;aga=(x['away_ga']+league_goal_rate*pdaa*pm/2)/aw
  evidence=clamp(x['w']/(x['w']+pm),0,1)
  out[tid]={'attack':gf/league_goal_rate,'defence':ga/league_goal_rate,'home_attack':hgf/league_goal_rate,'home_defence':hga/league_goal_rate,'away_attack':agf/league_goal_rate,'away_defence':aga/league_goal_rate,'sample_weight':x['w'],'prior_weight_matches':pm,'evidence_share':round(evidence,3),'prior_source':source,'prior_available':prior_available,'prior_version':prior_version}
 return out
def fixture_factors(ratings,team,opp,is_home,league_goal_rate=1.45):
 t=ratings.get(team,{});o=ratings.get(opp,{});ta=t.get('home_attack' if is_home else 'away_attack',t.get('attack',1));td=t.get('home_defence' if is_home else 'away_defence',t.get('defence',1));oa=o.get('away_attack' if is_home else 'home_attack',o.get('attack',1));od=o.get('away_defence' if is_home else 'home_defence',o.get('defence',1));attack=math.sqrt(max(.35,ta)*max(.35,od));opp_lambda=league_goal_rate*math.sqrt(max(.35,oa)*max(.35,td));return clamp(attack,.55,1.75),clamp(opp_lambda,.35,3.0)

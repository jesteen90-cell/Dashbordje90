"""Fetch conservative team-strength priors from FPL bootstrap.

Used only as an early-season stabilizer. Live match evidence in team_strength_v2
fades this prior out as the current season accumulates. If FPL omits the legacy
strength fields, write neutral priors instead of breaking the dashboard refresh.
"""
import json
from pathlib import Path
import requests
OUT=Path('team_strength_prior.json')

def n(v,d=0.0):
 try:return float(v)
 except:return d

def mean_or(values,default=1.0):
 return sum(values)/len(values) if values else default

def main():
 r=requests.get('https://fantasy.premierleague.com/api/bootstrap-static/',headers={'User-Agent':'fpl-autopilot-team-prior'},timeout=18)
 r.raise_for_status(); teams=r.json().get('teams') or []
 ah=[n(t.get('strength_attack_home')) for t in teams if n(t.get('strength_attack_home'))>0]
 aa=[n(t.get('strength_attack_away')) for t in teams if n(t.get('strength_attack_away'))>0]
 dh=[n(t.get('strength_defence_home')) for t in teams if n(t.get('strength_defence_home'))>0]
 da=[n(t.get('strength_defence_away')) for t in teams if n(t.get('strength_defence_away'))>0]
 available=bool(ah and aa and dh and da)
 means={'ah':mean_or(ah),'aa':mean_or(aa),'dh':mean_or(dh),'da':mean_or(da)}
 rows={}
 for t in teams:
  tid=str(int(t['id']))
  if available:
   raw_ah=n(t.get('strength_attack_home'),means['ah'])/means['ah']
   raw_aa=n(t.get('strength_attack_away'),means['aa'])/means['aa']
   raw_dh=means['dh']/max(1e-9,n(t.get('strength_defence_home'),means['dh']))
   raw_da=means['da']/max(1e-9,n(t.get('strength_defence_away'),means['da']))
   def shrink(x):return max(.72,min(1.32,1+.62*(x-1)))
   vals={'home_attack':round(shrink(raw_ah),4),'away_attack':round(shrink(raw_aa),4),'home_defence':round(shrink(raw_dh),4),'away_defence':round(shrink(raw_da),4)}
  else:
   vals={'home_attack':1.0,'away_attack':1.0,'home_defence':1.0,'away_defence':1.0}
  rows[tid]={'name':t.get('name'),**vals}
 OUT.write_text(json.dumps({'version':'1.1-fpl-bootstrap-safe','source':'FPL bootstrap team strengths','available':available,'teams':rows},ensure_ascii=False,indent=2))
 print('Team strength priors',len(rows),'available=',available)
if __name__=='__main__':main()

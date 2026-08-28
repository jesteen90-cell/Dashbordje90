"""Fetch conservative team-strength priors from FPL bootstrap.

Used only as an early-season stabilizer. Live match evidence in team_strength_v2
fades this prior out as the current season accumulates.
"""
import json
from pathlib import Path
import requests
OUT=Path('team_strength_prior.json')

def n(v,d=0.0):
 try:return float(v)
 except:return d

def main():
 r=requests.get('https://fantasy.premierleague.com/api/bootstrap-static/',headers={'User-Agent':'fpl-autopilot-team-prior'},timeout=18)
 r.raise_for_status(); teams=r.json().get('teams') or []
 ah=[n(t.get('strength_attack_home')) for t in teams if n(t.get('strength_attack_home'))>0]
 aa=[n(t.get('strength_attack_away')) for t in teams if n(t.get('strength_attack_away'))>0]
 dh=[n(t.get('strength_defence_home')) for t in teams if n(t.get('strength_defence_home'))>0]
 da=[n(t.get('strength_defence_away')) for t in teams if n(t.get('strength_defence_away'))>0]
 means={'ah':sum(ah)/len(ah),'aa':sum(aa)/len(aa),'dh':sum(dh)/len(dh),'da':sum(da)/len(da)}
 rows={}
 for t in teams:
  tid=str(int(t['id']))
  # Attack: higher official strength = stronger attack. Defence model is GA factor,
  # so invert official defence strength (higher official strength -> lower GA factor).
  raw_ah=n(t.get('strength_attack_home'),means['ah'])/means['ah']
  raw_aa=n(t.get('strength_attack_away'),means['aa'])/means['aa']
  raw_dh=means['dh']/max(1,n(t.get('strength_defence_home'),means['dh']))
  raw_da=means['da']/max(1,n(t.get('strength_defence_away'),means['da']))
  # Bound and shrink toward neutral. This is a stabilizer, not an oracle.
  def shrink(x):return max(.72,min(1.32,1+.62*(x-1)))
  rows[tid]={'name':t.get('name'),'home_attack':round(shrink(raw_ah),4),'away_attack':round(shrink(raw_aa),4),'home_defence':round(shrink(raw_dh),4),'away_defence':round(shrink(raw_da),4)}
 OUT.write_text(json.dumps({'version':'1.0-fpl-bootstrap','source':'FPL bootstrap team strengths','teams':rows},ensure_ascii=False,indent=2))
 print('Team strength priors',len(rows))
if __name__=='__main__':main()

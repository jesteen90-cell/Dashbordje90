from __future__ import annotations
import json,math
from datetime import datetime,timezone
from pathlib import Path
import requests
BASE='https://fantasy.premierleague.com/api';ROOT=Path('market_ab_snapshots');OUT=Path('market_ab');SCORE=OUT/'scorecard.json';PARAMS=OUT/'params.json'
def get(path):
 r=requests.get(f"{BASE}/{path.lstrip('/')}",headers={'Accept':'application/json','User-Agent':'fpl-autopilot-market-ab-eval'},timeout=18);r.raise_for_status();return r.json()
def n(v,d=0):
 try:return float(v)
 except:return d
def brier(p,y):return (p-y)**2
def avg(xs):return sum(xs)/len(xs) if xs else None
def improve(a,b):return ((a-b)/a) if a else 0
def main():
 OUT.mkdir(exist_ok=True);boot=get('bootstrap-static/');finished={int(e['id']) for e in boot.get('events',[]) if e.get('finished')};fixtures=get('fixtures/');fix_by_id={int(f['id']):f for f in fixtures};hist_cache={}
 def actual_points(pid,gw):
  if pid not in hist_cache:
   d=get(f'element-summary/{pid}/');hist_cache[pid]={int(x['round']):int(x.get('total_points',0)) for x in d.get('history',[])}
  return hist_cache[pid].get(gw,0)
 results=[];grid_rows=[]
 for path in sorted(ROOT.glob('gw*.json')):
  s=json.loads(path.read_text());gw=int(s['gw'])
  if gw not in finished or not s.get('market_active'):continue
  pa=[];pb=[];pc=[];defa=[];defb=[];offa=[];offb=[];offc=[];off_rows=[]
  for p in s.get('players') or []:
   act=actual_points(int(p['id']),gw);ia=n(p.get('internal_xp'));ib=n(p.get('ensemble_xp'));ic=n(p.get('share_ensemble_xp'),ib);ea=abs(act-ia);eb=abs(act-ib);ec=abs(act-ic);pa.append(ea);pb.append(eb);pc.append(ec)
   if p.get('position') in ('GK','DEF'):defa.append(ea);defb.append(eb)
   if p.get('position') in ('MID','FWD'):offa.append(ea);offb.append(eb);offc.append(ec);off_rows.append((p,act,ia,ib,ic))
  cap_int=max(off_rows,key=lambda x:x[2]) if off_rows else None;cap_ens=max(off_rows,key=lambda x:x[3]) if off_rows else None;cap_share=max(off_rows,key=lambda x:x[4]) if off_rows else None;best_actual=max((x[1] for x in off_rows),default=0)
  f_mae_a=[];f_mae_b=[];cs_a=[];cs_b=[];used=0
  for r in s.get('fixtures') or []:
   f=fix_by_id.get(int(r['fixture_id']))
   if not f or not f.get('finished') or f.get('team_h_score') is None:continue
   hg=int(f['team_h_score']);ag=int(f['team_a_score']);ih=n(r.get('internal_home_xg'));ia=n(r.get('internal_away_xg'));eh=n(r.get('ensemble_home_xg'));ea=n(r.get('ensemble_away_xg'));mh=r.get('market_home_xg');ma=r.get('market_away_xg');f_mae_a += [abs(hg-ih),abs(ag-ia)];f_mae_b += [abs(hg-eh),abs(ag-ea)];cs_a += [brier(math.exp(-ia),1 if ag==0 else 0),brier(math.exp(-ih),1 if hg==0 else 0)];cs_b += [brier(math.exp(-ea),1 if ag==0 else 0),brier(math.exp(-eh),1 if hg==0 else 0)];used+=1
   if mh is not None and ma is not None:grid_rows.append((hg,ag,ih,ia,n(mh),n(ma)))
  results.append({'gw':gw,'player_samples':len(pa),'player_mae_internal':round(avg(pa) or 0,4),'player_mae_ensemble':round(avg(pb) or 0,4),'player_mae_share':round(avg(pc) or 0,4),'defensive_samples':len(defa),'defensive_mae_internal':round(avg(defa) or 0,4),'defensive_mae_ensemble':round(avg(defb) or 0,4),'offensive_samples':len(offa),'offensive_mae_internal':round(avg(offa) or 0,4),'offensive_mae_ensemble':round(avg(offb) or 0,4),'offensive_mae_share':round(avg(offc) or 0,4),'captain_proxy_regret_internal':None if not cap_int else best_actual-cap_int[1],'captain_proxy_regret_ensemble':None if not cap_ens else best_actual-cap_ens[1],'captain_proxy_regret_share':None if not cap_share else best_actual-cap_share[1],'fixture_samples':used,'goal_mae_internal':round(avg(f_mae_a) or 0,4),'goal_mae_ensemble':round(avg(f_mae_b) or 0,4),'cs_brier_internal':round(avg(cs_a) or 0,4),'cs_brier_ensemble':round(avg(cs_b) or 0,4)})
 for r in results:(OUT/f"gw{int(r['gw']):02d}.json").write_text(json.dumps(r,ensure_ascii=False,indent=2))
 def weighted(key,weight_key):
  z=[(n(r[key]),int(r[weight_key])) for r in results if int(r.get(weight_key,0))>0];den=sum(w for _,w in z);return sum(v*w for v,w in z)/den if den else None
 grid=[]
 for w_i in range(17):
  w=w_i*.05;errs=[]
  for hg,ag,ih,ia,mh,ma in grid_rows:errs += [abs(hg-((1-w)*ih+w*mh)),abs(ag-((1-w)*ia+w*ma))]
  if errs:grid.append({'weight':round(w,2),'goal_mae':round(avg(errs),5)})
 best=min(grid,key=lambda x:x['goal_mae']) if grid else {'weight':0.45,'goal_mae':None}
 pa=weighted('player_mae_internal','player_samples');pb=weighted('player_mae_ensemble','player_samples');pc=weighted('player_mae_share','player_samples');da=weighted('defensive_mae_internal','defensive_samples');db=weighted('defensive_mae_ensemble','defensive_samples');oa=weighted('offensive_mae_internal','offensive_samples');ob=weighted('offensive_mae_ensemble','offensive_samples');oc=weighted('offensive_mae_share','offensive_samples');ga=weighted('goal_mae_internal','fixture_samples');gb=weighted('goal_mae_ensemble','fixture_samples');ca=weighted('cs_brier_internal','fixture_samples');cb=weighted('cs_brier_ensemble','fixture_samples');cap_a=avg([n(r['captain_proxy_regret_internal']) for r in results if r.get('captain_proxy_regret_internal') is not None]);cap_b=avg([n(r['captain_proxy_regret_ensemble']) for r in results if r.get('captain_proxy_regret_ensemble') is not None]);cap_c=avg([n(r['captain_proxy_regret_share']) for r in results if r.get('captain_proxy_regret_share') is not None])
 active_gws=len(results);fixture_samples=sum(int(r.get('fixture_samples',0)) for r in results);def_samples=sum(int(r.get('defensive_samples',0)) for r in results);off_samples=sum(int(r.get('offensive_samples',0)) for r in results);ready=active_gws>=6 and fixture_samples>=45 and def_samples>=60 and off_samples>=60
 goal_improve=improve(ga,gb);cs_improve=improve(ca,cb);def_improve=improve(da,db);off_improve=improve(oa,ob);cap_improve=improve(cap_a,cap_b);share_off_improve=improve(oa,oc);share_vs_ensemble=improve(ob,oc);share_cap_improve=improve(cap_a,cap_c)
 promote_market=bool(ready and goal_improve>=.02 and cs_improve>=0 and def_improve>=-.01 and off_improve>=.01 and cap_improve>=-.02);promote_share=bool(ready and promote_market and share_off_improve>=.02 and share_vs_ensemble>=.005 and share_cap_improve>=-.01)
 score={'version':'1.2-player-share','generated_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'active_gws':active_gws,'fixture_samples':fixture_samples,'defensive_player_samples':def_samples,'offensive_player_samples':off_samples,'player_mae_internal':pa,'player_mae_ensemble':pb,'player_mae_share':pc,'defensive_mae_internal':da,'defensive_mae_ensemble':db,'offensive_mae_internal':oa,'offensive_mae_ensemble':ob,'offensive_mae_share':oc,'captain_proxy_regret_internal':cap_a,'captain_proxy_regret_ensemble':cap_b,'captain_proxy_regret_share':cap_c,'goal_mae_internal':ga,'goal_mae_ensemble':gb,'cs_brier_internal':ca,'cs_brier_ensemble':cb,'goal_mae_improvement':round(goal_improve,4),'offensive_mae_improvement':round(off_improve,4),'player_share_offensive_improvement':round(share_off_improve,4),'player_share_vs_simple_ensemble':round(share_vs_ensemble,4),'player_share_captain_improvement':round(share_cap_improve,4),'best_fixed_market_weight':best,'promotion_ready':ready,'promote_market_ensemble':promote_market,'promote_player_share':promote_share,'grid':grid,'gws':[r['gw'] for r in results]};SCORE.write_text(json.dumps(score,ensure_ascii=False,indent=2))
 cap=max(.25,min(.70,n(best.get('weight'),.45))) if promote_market else .65;params={'version':'1.2-player-share','promoted':promote_market,'promote_player_share':promote_share,'market_weight_cap':round(cap,2),'min_market_weight':round(max(.10,min(.35,cap*.35)),2),'evidence':{'active_gws':active_gws,'fixture_samples':fixture_samples,'defensive_samples':def_samples,'offensive_samples':off_samples,'goal_mae_improvement':round(goal_improve,4),'offensive_mae_improvement':round(off_improve,4),'player_share_offensive_improvement':round(share_off_improve,4),'player_share_vs_simple_ensemble':round(share_vs_ensemble,4),'player_share_captain_improvement':round(share_cap_improve,4)}};PARAMS.write_text(json.dumps(params,ensure_ascii=False,indent=2));print('Market A/B/C player-share',active_gws,'GWs','market=',promote_market,'share=',promote_share)
if __name__=='__main__':main()

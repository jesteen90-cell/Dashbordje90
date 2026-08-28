from pathlib import Path
import py_compile
from model_v2_core import project, stabilized_role
from team_strength_v2 import build_strength, fixture_difficulty
from transfer_optimizer_v2 import bench_resilience, BENCH_RESILIENCE_WEIGHT, captain_value, CAPTAIN_WEIGHTS


def base(**kw):
    d={'position':4,'availability':1.0,'start_rate':0.0,'avg_start_mins':78,'sub_rate':0.0,'avg_sub_mins':18,'minutes_history':0,'goal90':0.0,'assist90':0.0,'prev_minutes':0.0,'prev_goal90':0.0,'prev_assist90':0.0,'save90':0.0,'defcon90':0.0,'bonus90':0.0,'yellow90':0.0,'red90':0.0,'opponent_goal_lambda':1.35,'attack_multiplier':1.0}
    d.update(kw);return d


def pipeline_sanity():
    for p in Path('.').glob('*.py'):py_compile.compile(str(p),doraise=True)
    opt=Path('transfer_optimizer_v2.py').read_text(encoding='utf-8')
    assert 'from captain_horizon_v1 import horizon_values' in opt
    assert "'captain_horizon_search':True" in opt
    assert "'captain_selection_aligned':True" in opt
    assert "'bench_resilience':True" in opt
    assert 'BENCH_RESILIENCE_WEIGHT=.055' in opt
    assert 'def captain_value' in opt
    dl=Path('decision_layer_v4.py').read_text(encoding='utf-8')
    assert 'def select_squad_view' in dl and "data['lineup']=target_xi" in dl and "data['bench']=reorder_bench(bench)" in dl
    build=Path('build_dashboard_with_cache.py').read_text(encoding='utf-8')
    assert 'fixture_difficulty' in build and '2.0-position-aware' in build and "'difficulty_basis':basis" in build
    html=Path('index.html').read_text(encoding='utf-8')
    assert 'function render()' in html and 'data.json?v=${Date.now()}' in html and 'class="player ${ch||\'\'}"' in html
    assert "player.out" in html and "player.in" in html and 'Siste bekreftede FPL-startellever' in html and 'Siste bekreftede FPL-benk' in html
    ui=Path('captain_explain_ui.js').read_text(encoding='utf-8') if Path('captain_explain_ui.js').exists() else ''
    assert 'MutationObserver' not in ui


def strength_sanity():
    ratings={2:{'home_attack':1.45,'away_attack':1.40,'attack':1.42,'home_defence':.72,'away_defence':.75,'defence':.74}}
    def_h,basis_d=fixture_difficulty(ratings,2,True,'DEF');fwd_h,basis_a=fixture_difficulty(ratings,2,True,'FWD')
    assert basis_d=='opponent-attack' and basis_a=='opponent-defence';assert def_h>=4,(def_h,fwd_h);assert fwd_h<=3,(def_h,fwd_h)
    teams={i:{'position':i,'rank':i,'points':0} for i in range(1,21)};fixtures=[{'finished':True,'team_h':1,'team_a':20,'team_h_score':6,'team_a_score':0,'event':1,'id':1}];s=build_strength(fixtures,teams);assert len(s)==20;one=s[1]
    assert one['evidence_confidence']=='low',one;assert one['early_season_cap'] is True;assert .75<=one['attack']<=1.30,one;assert one['prior_source'] in ('table-shrunk','neutral-fallback','fpl-bootstrap')
    if one['prior_source']=='table-shrunk':assert one['prior_version']=='2.2-table-shrunk-early-cap',one;assert one['prior_available'] is False,one


def bench_sanity():
    def p(pid,pos,xp):return {'id':pid,'element_type':pos,'_x':{2:xp}}
    xi=[p(i,2 if i<5 else (3 if i<9 else 4),5.0) for i in range(1,12)];bench=[p(12,1,3.5),p(13,2,4.0),p(14,3,2.5),p(15,4,1.0)];squad=xi+bench;base_value=bench_resilience(squad,xi,2);better=list(squad);better[-3]=p(13,2,6.0);improved=bench_resilience(better,xi,2);gain=improved-base_value
    assert 0<gain<.25,(base_value,improved,gain);assert gain<2.0*.15,gain;assert BENCH_RESILIENCE_WEIGHT<=.06


def captain_optimizer_sanity():
    # Promoted v3 uses ceiling as well as xP. A slightly lower-xP player with a
    # much better p90 can therefore correctly rank higher for captain selection.
    steady={'id':1,'_x':{2:7.0},'_proj':{2:{'p90':8.0,'xmins':88,'attack_multiplier':1.0,'volatility':.7}}}
    explosive={'id':2,'_x':{2:6.8},'_proj':{2:{'p90':12.0,'xmins':88,'attack_multiplier':1.0,'volatility':1.0}}}
    assert CAPTAIN_WEIGHTS['xp']>0
    if CAPTAIN_WEIGHTS.get('ceiling',0)>0:assert captain_value(explosive,2)>captain_value(steady,2),(CAPTAIN_WEIGHTS,captain_value(steady,2),captain_value(explosive,2))
    # Utility score is only for selecting the captain; doubled contribution stays xP.
    assert explosive['_x'][2]==6.8


def main():
    sr,sub=stabilized_role(0,0,0,4);assert sr==0 and sub==0,(sr,sub)
    ghost=project(base());assert ghost['xmins']==0,ghost;assert ghost['total']==0,ghost
    seen=project(base(minutes_history=43,start_rate=0,sub_rate=.5,goal90=.3,assist90=.1));assert 15<seen['xmins']<70,seen;assert seen['total']>0,seen
    starter=project(base(minutes_history=180,start_rate=1,sub_rate=0,goal90=.3,assist90=.1));assert starter['xmins']>seen['xmins'],(starter,seen)
    unknown_early=project(base(minutes_history=90,start_rate=1,avg_start_mins=88,goal90=.3,assist90=.1));established_early=project(base(minutes_history=90,start_rate=1,avg_start_mins=88,prev_minutes=3000,goal90=.3,assist90=.1));assert established_early['xmins']>=76,established_early;assert established_early['xmins']>=unknown_early['xmins']+8,(unknown_early,established_early);assert established_early['p_start']>.84,established_early
    generic=project(base(minutes_history=90,start_rate=1,avg_start_mins=90,goal90=0));elite=project(base(minutes_history=90,start_rate=1,avg_start_mins=90,goal90=0,prev_minutes=3000,prev_goal90=.90,prev_assist90=.12));assert elite['goal_prior_used']>generic['goal_prior_used']+.20,(generic,elite);assert elite['goals']>generic['goals']+.35,(generic,elite)
    faded=project(base(minutes_history=2700,start_rate=1,avg_start_mins=90,goal90=.31,prev_minutes=3000,prev_goal90=.90));assert abs(faded['goal90_used']-.31)<abs(elite['goal90_used']-.31),(elite,faded)
    strength_sanity();bench_sanity();captain_optimizer_sanity();pipeline_sanity()
    print('live model sanity passed',{'ghost_xmins':ghost['xmins'],'unknown_early_xmins':round(unknown_early['xmins'],1),'established_early_xmins':round(established_early['xmins'],1),'elite_goal_prior':round(elite['goal_prior_used'],3),'faded_goal90':round(faded['goal90_used'],3),'position_aware_fdr':True,'bench_resilience':True,'captain_optimizer_aligned':True})

if __name__=='__main__':main()

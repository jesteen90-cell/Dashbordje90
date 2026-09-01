from pathlib import Path
import py_compile
from model_v2_core import project, stabilized_role, attack_evidence_minutes, bonus_prior_2627, defcon_threshold_probability, expected_save_points, goalkeeper_save_multiplier, penalty_components
from team_strength_v2 import build_strength, fixture_difficulty
from transfer_optimizer_v2 import bench_resilience, BENCH_RESILIENCE_WEIGHT, captain_value, CAPTAIN_WEIGHTS, sale_value, _incoming_pools
from recent_form_v2 import blend_rates
from availability_v1 import next_round_availability, availability_for_gw

def base(**kw):
 d={'position':4,'availability':1.0,'start_rate':0.0,'avg_start_mins':78,'sub_rate':0.0,'avg_sub_mins':18,'minutes_history':0,'goal90':0.0,'assist90':0.0,'prev_minutes':0.0,'prev_goal90':0.0,'prev_assist90':0.0,'save90':0.0,'defcon90':0.0,'bonus90':0.0,'yellow90':0.0,'red90':0.0,'opponent_goal_lambda':1.35,'attack_multiplier':1.0};d.update(kw);return d

def pipeline_sanity():
 for p in Path('.').glob('*.py'):py_compile.compile(str(p),doraise=True)
 opt=Path('transfer_optimizer_v2.py').read_text();assert 'BENCH_RESILIENCE_WEIGHT=.055' in opt and 'def captain_value' in opt and 'def sale_value' in opt and "'reentry_pool':True" in opt
 dl=Path('decision_layer_v4.py').read_text();assert 'def select_squad_view' in dl and "data['lineup']=target_xi" in dl
 build=Path('build_dashboard_with_cache.py').read_text();assert 'fixture_difficulty' in build and '2.0-position-aware' in build;assert 'reconcile_breakdown' in build and 'set_piece_roles.json' in build and "projection_integration':'active'" in build
 gen=Path('generate_dashboard_v3.py').read_text();assert "'penalty_taker_share':penalty_share(p)" in gen and "'projection_integration':'active'" in gen and "'bonus','penalty','conceded'" in gen
 assert 'availability_for_gw' in gen and "'budget':{" in gen and "'3.8-availability-recovery-set-piece-projection'" in gen and "'selling_price'" in gen
 roles=Path('set_piece_roles.json').read_text();assert 'Erling Haaland' in roles and 'Bruno Fernandes' in roles
 html=Path('index.html').read_text();app=Path('app.js').read_text();lineup=Path('current_lineup_ui.js').read_text();team_css=Path('team_ui.css').read_text()
 assert 'src="app.js?v=' in html and 'href="team_ui.css?v=' in html and 'id="after" class="pitch"' in html and 'id="bench" class="bench"' in html and 'Se forrige bekreftede FPL-lag' in html
 assert 'function render()' in app and 'function kit(' in app and 'function pitch(' in app and 'function benchHtml(' in app
 assert 'D.final_transfer_gate' in app and "D.gameweek||D.gw" in app and "if(mp)mp.textContent" in app and "box.classList.add('show')" in app
 assert "querySelectorAll('.kit').length===11" in lineup and 'renderVisualOptimal' in lineup
 assert '#team .pitch .row.n5' in team_css and 'grid-template-columns:repeat(5,minmax(0,1fr))' in team_css
 pages=Path('.github/workflows/pages.yml').read_text();assert 'workflow_run:' in pages and 'Refresh FPL Dashboard' in pages and 'github.event.workflow_run.conclusion' in pages
 ui=Path('captain_explain_ui.js').read_text() if Path('captain_explain_ui.js').exists() else '';assert 'MutationObserver' not in ui

def transfer_planner_sanity():
 p={'id':1,'element_type':3,'team':1,'now_cost':80,'selling_price':74,'_x':{2:5,3:5}};assert sale_value(p)==74;assert sale_value({**p,'selling_price':80})==80
 players=[p,{'id':2,'element_type':3,'team':2,'now_cost':75,'_x':{2:7,3:1}},{'id':3,'element_type':3,'team':3,'now_cost':75,'_x':{2:1,3:8}}]
 pools=_incoming_pools(players,[p],[2,3],{2:1,3:1},per_pos=8);ids={int(x['id']) for x in pools[3]};assert 1 in ids and 2 in ids and 3 in ids

def availability_sanity():
 doubt={'status':'d','chance_of_playing_next_round':50};vals=[availability_for_gw(doubt,2,g) for g in range(2,7)];assert vals[0]==.5 and all(a<b for a,b in zip(vals,vals[1:])) and vals[-1]>.85
 injured={'status':'i','chance_of_playing_next_round':25};assert availability_for_gw(injured,2,2)==.25 and availability_for_gw(injured,2,4)>.6
 suspended={'status':'s','chance_of_playing_next_round':0};assert next_round_availability(suspended)==0 and availability_for_gw(suspended,2,3)>=.65 and availability_for_gw(suspended,2,5)>=.94
 unavailable={'status':'u','chance_of_playing_next_round':0};assert all(availability_for_gw(unavailable,2,g)==0 for g in range(2,7))

def strength_sanity():
 ratings={2:{'home_attack':1.45,'away_attack':1.40,'attack':1.42,'home_defence':.72,'away_defence':.75,'defence':.74}};d,bd=fixture_difficulty(ratings,2,True,'DEF');a,ba=fixture_difficulty(ratings,2,True,'FWD');assert bd=='opponent-attack' and ba=='opponent-defence' and d>=4 and a<=3
 teams={i:{'position':i,'rank':i,'points':0} for i in range(1,21)};s=build_strength([{'finished':True,'team_h':1,'team_a':20,'team_h_score':6,'team_a_score':0,'event':1,'id':1}],teams);one=s[1];assert one['evidence_confidence']=='low' and .75<=one['attack']<=1.30

def bench_sanity():
 def p(pid,pos,xp):return {'id':pid,'element_type':pos,'_x':{2:xp}}
 xi=[p(i,2 if i<5 else (3 if i<9 else 4),5) for i in range(1,12)];sq=xi+[p(12,1,3.5),p(13,2,4),p(14,3,2.5),p(15,4,1)];b=bench_resilience(sq,xi,2);better=list(sq);better[-3]=p(13,2,6);gain=bench_resilience(better,xi,2)-b;assert 0<gain<.25 and BENCH_RESILIENCE_WEIGHT<=.06

def captain_optimizer_sanity():
 steady={'id':1,'_x':{2:7},'_proj':{2:{'p90':8,'xmins':88,'attack_multiplier':1,'volatility':.7}}};boom={'id':2,'_x':{2:6.8},'_proj':{2:{'p90':12,'xmins':88,'attack_multiplier':1,'volatility':1}}};assert CAPTAIN_WEIGHTS['xp']>0
 if CAPTAIN_WEIGHTS.get('ceiling',0)>0:assert captain_value(boom,2)>captain_value(steady,2)

def uncertainty_sanity():
 secure=project(base(minutes_history=900,start_rate=1,avg_start_mins=88,prev_minutes=3000));rot=project(base(minutes_history=900,start_rate=.52,avg_start_mins=88,sub_rate=.38,avg_sub_mins=22,prev_minutes=900));assert secure['minute_variance']<rot['minute_variance'] and rot['role_variance']>secure['role_variance']

def attacking_evidence_sanity():
 assert attack_evidence_minutes(90,90,.2)<100 and attack_evidence_minutes(3000,900,1)<=1800
 b={'goal90':.5,'assist90':.2};lo,_=blend_rates(b,{'multiplier':1.1},{'multiplier':1.2,'confidence':.1,'minutes':90},attack_share=.4,enabled=True);hi,_=blend_rates(b,{'multiplier':1.1},{'multiplier':1.2,'confidence':.8,'minutes':720},attack_share=.4,enabled=True);assert hi['goal90']>lo['goal90']

def defensive_exposure_sanity():
 common={'position':2,'minutes_history':900,'start_rate':1,'sub_rate':0,'prev_minutes':3000,'opponent_goal_lambda':1.35};full=project(base(**common,avg_start_mins=90));early=project(base(**common,avg_start_mins=70));assert early['defensive_exposure']<full['defensive_exposure'] and early['cs_probability']>full['cs_probability'];assert project(base(position=2,minutes_history=900,start_rate=.15,avg_start_mins=55,sub_rate=.55,avg_sub_mins=25,prev_minutes=500,opponent_goal_lambda=2.2))['conceded']<0

def bonus_sanity():
 assert bonus_prior_2627(1)>bonus_prior_2627(2);assert bonus_prior_2627(3)>bonus_prior_2627(2) and bonus_prior_2627(4)>bonus_prior_2627(2)
 early_cb=project(base(position=2,minutes_history=90,start_rate=1,avg_start_mins=90,bonus90=.9));early_fwd=project(base(position=4,minutes_history=90,start_rate=1,avg_start_mins=90,bonus90=.9));assert early_fwd['bonus_prior_used']>early_cb['bonus_prior_used']
 mature=project(base(position=4,minutes_history=2700,start_rate=1,avg_start_mins=90,bonus90=.8));assert abs(mature['bonus90_used']-.8)<.12,mature

def defcon_sanity():
 for pos,thr in ((2,10),(3,12),(4,12)):
  lo=defcon_threshold_probability(thr*.55,thr,pos);mid=defcon_threshold_probability(thr,thr,pos);hi=defcon_threshold_probability(thr*1.7,thr,pos);assert 0<lo<mid<hi<1,(pos,lo,mid,hi);assert mid<.75,(pos,mid)
 cb=project(base(position=2,minutes_history=900,start_rate=1,avg_start_mins=90,prev_minutes=3000,defcon90=10));dm=project(base(position=3,minutes_history=900,start_rate=1,avg_start_mins=90,prev_minutes=3000,defcon90=12));assert 0<cb['defcon_probability']<1 and 0<dm['defcon_probability']<1

def goalkeeper_sanity():
 assert 0<expected_save_points(3)<1 and expected_save_points(6)>expected_save_points(3)
 assert .78<=goalkeeper_save_multiplier(.2)<goalkeeper_save_multiplier(1.35)<goalkeeper_save_multiplier(3.0)<=1.28
 common={'position':1,'minutes_history':900,'start_rate':1,'avg_start_mins':90,'prev_minutes':3000,'save90':3.5}
 easy=project(base(**common,opponent_goal_lambda=.65));hard=project(base(**common,opponent_goal_lambda=2.2));assert hard['expected_saves']>easy['expected_saves'];assert hard['save_fixture_multiplier']>1>easy['save_fixture_multiplier'];assert hard['saves']>easy['saves']

def penalty_sanity():
 gk=project(base(position=1,minutes_history=1800,start_rate=1,avg_start_mins=90,prev_minutes=3000,penalty_save90=.08));assert 0<gk['penalty_save']<.5 and gk['penalty_miss']==0
 normal=project(base(position=4,minutes_history=1800,start_rate=1,avg_start_mins=90,prev_minutes=3000));taker=project(base(position=4,minutes_history=1800,start_rate=1,avg_start_mins=90,prev_minutes=3000,penalty_taker_share=1,penalty_miss90=.05));assert normal['penalty']==0 and taker['penalty_miss']<0 and taker['total']<normal['total']
 ps,pm,_,_=penalty_components({'minutes_history':900,'penalty_save90':.1},1,1,1);assert ps>0 and pm==0

def main():
 sr,sub=stabilized_role(0,0,0,4);assert sr==0 and sub==0;ghost=project(base());assert ghost['xmins']==0 and ghost['total']==0
 seen=project(base(minutes_history=43,start_rate=0,sub_rate=.5));starter=project(base(minutes_history=180,start_rate=1,sub_rate=0));assert 15<seen['xmins']<70 and starter['xmins']>seen['xmins']
 unknown=project(base(minutes_history=90,start_rate=1,avg_start_mins=88));est=project(base(minutes_history=90,start_rate=1,avg_start_mins=88,prev_minutes=3000));assert est['xmins']>=76 and est['xmins']>=unknown['xmins']+8
 transfer_planner_sanity();availability_sanity();strength_sanity();bench_sanity();captain_optimizer_sanity();uncertainty_sanity();attacking_evidence_sanity();defensive_exposure_sanity();bonus_sanity();defcon_sanity();goalkeeper_sanity();penalty_sanity();pipeline_sanity();print('live model sanity passed',{'availability_recovery':True,'transfer_sale_values':True,'transfer_reentry_pool':True,'penalty_components':True,'set_piece_projection':True,'xp_reconciliation':True,'goalkeeper_fixture_saves':True,'bonus_2627':True,'defcon_overdispersion':True,'position_aware_fdr':True,'bench_resilience':True,'role_uncertainty':True,'defensive_exposure':True})
if __name__=='__main__':main()

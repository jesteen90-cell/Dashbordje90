from pathlib import Path
import py_compile
from model_v2_core import project, stabilized_role


def base(**kw):
    d={
        'position':4,'availability':1.0,'start_rate':0.0,'avg_start_mins':78,
        'sub_rate':0.0,'avg_sub_mins':18,'minutes_history':0,'goal90':0.0,
        'assist90':0.0,'prev_minutes':0.0,'prev_goal90':0.0,'prev_assist90':0.0,
        'save90':0.0,'defcon90':0.0,'bonus90':0.0,
        'yellow90':0.0,'red90':0.0,'opponent_goal_lambda':1.35,
        'attack_multiplier':1.0,
    }
    d.update(kw);return d


def pipeline_sanity():
    for p in Path('.').glob('*.py'):
        py_compile.compile(str(p), doraise=True)
    opt=Path('transfer_optimizer_v2.py').read_text(encoding='utf-8')
    assert 'from captain_horizon_v1 import horizon_values' in opt
    assert "'captain_horizon_search':True" in opt
    dl=Path('decision_layer_v4.py').read_text(encoding='utf-8')
    assert 'def select_squad_view' in dl
    assert "data['lineup']=target_xi" in dl
    assert "data['bench']=reorder_bench(bench)" in dl
    html=Path('index.html').read_text(encoding='utf-8')
    assert 'function render()' in html
    assert 'data.json?v=${Date.now()}' in html
    assert 'class="player ${ch||\'\'}"' in html
    assert "player.out" in html and "player.in" in html
    assert 'Siste bekreftede FPL-startellever' in html
    assert 'Siste bekreftede FPL-benk' in html
    # The optional enhancer is intentionally disabled after a Safari render-loop incident.
    ui=Path('captain_explain_ui.js').read_text(encoding='utf-8') if Path('captain_explain_ui.js').exists() else ''
    assert 'MutationObserver' not in ui


def main():
    sr,sub=stabilized_role(0,0,0,4)
    assert sr==0 and sub==0,(sr,sub)
    ghost=project(base())
    assert ghost['xmins']==0,ghost
    assert ghost['total']==0,ghost

    seen=project(base(minutes_history=43,start_rate=0,sub_rate=.5,goal90=.3,assist90=.1))
    assert 15 < seen['xmins'] < 70,seen
    assert seen['total'] > 0,seen

    starter=project(base(minutes_history=180,start_rate=1,sub_rate=0,goal90=.3,assist90=.1))
    assert starter['xmins'] > seen['xmins'],(starter,seen)

    generic=project(base(minutes_history=90,start_rate=1,avg_start_mins=90,goal90=0))
    elite=project(base(minutes_history=90,start_rate=1,avg_start_mins=90,goal90=0,prev_minutes=3000,prev_goal90=.90,prev_assist90=.12))
    assert elite['goal_prior_used'] > generic['goal_prior_used']+.20,(generic,elite)
    assert elite['goals'] > generic['goals']+.35,(generic,elite)
    faded=project(base(minutes_history=2700,start_rate=1,avg_start_mins=90,goal90=.31,prev_minutes=3000,prev_goal90=.90))
    assert abs(faded['goal90_used']-.31) < abs(elite['goal90_used']-.31),(elite,faded)

    pipeline_sanity()
    print('live model + history-prior sanity passed', {'ghost_xmins':ghost['xmins'],'elite_goal_prior':round(elite['goal_prior_used'],3),'generic_goal_prior':round(generic['goal_prior_used'],3),'faded_goal90':round(faded['goal90_used'],3)})

if __name__=='__main__':main()

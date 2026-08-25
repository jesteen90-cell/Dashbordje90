from model_v2_core import project, stabilized_role


def base(**kw):
    d={
        'position':4,'availability':1.0,'start_rate':0.0,'avg_start_mins':78,
        'sub_rate':0.0,'avg_sub_mins':18,'minutes_history':0,'goal90':0.0,
        'assist90':0.0,'save90':0.0,'defcon90':0.0,'bonus90':0.0,
        'yellow90':0.0,'red90':0.0,'opponent_goal_lambda':1.35,
        'attack_multiplier':1.0,
    }
    d.update(kw);return d


def main():
    # A player with no season minutes and no observed role must not become a
    # synthetic starter merely because the season is young.
    sr,sub=stabilized_role(0,0,0,4)
    assert sr==0 and sub==0,(sr,sub)
    ghost=project(base())
    assert ghost['xmins']==0,ghost
    assert ghost['total']==0,ghost

    # A player who has actually appeared should get a conservative stabilizer;
    # one short appearance must not collapse the next-GW expectation to zero.
    seen=project(base(minutes_history=43,start_rate=0,sub_rate=.5,goal90=.3,assist90=.1))
    assert 15 < seen['xmins'] < 70,seen
    assert seen['total'] > 0,seen

    # Fully available established starter should remain comfortably above a
    # fringe player's role expectation.
    starter=project(base(minutes_history=180,start_rate=1,sub_rate=0,goal90=.3,assist90=.1))
    assert starter['xmins'] > seen['xmins'],(starter,seen)
    print('live model sanity passed', {'ghost_xmins':ghost['xmins'],'seen_xmins':round(seen['xmins'],1),'starter_xmins':round(starter['xmins'],1)})

if __name__=='__main__':main()

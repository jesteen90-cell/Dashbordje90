from __future__ import annotations

def clamp(x,a,b):return max(a,min(b,x))
def n(x,d=0.):
 try:return float(x)
 except:return d

def form_signal(p,decay=.82):
 """Recency/underlying involvement signal from official FPL season metrics.
 Uses xG/xA when exposed by bootstrap, plus starts/minutes and ICT threat/
 creativity. Shrinkage prevents tiny early-season samples dominating.
 """
 mins=n(p.get('minutes')); starts=n(p.get('starts')); apps=max(starts,mins/75,1); shrink=mins/(mins+450)
 xg=n(p.get('expected_goals')); xa=n(p.get('expected_assists')); xgi=n(p.get('expected_goal_involvements'),xg+xa)
 threat=n(p.get('threat')); creativity=n(p.get('creativity')); influence=n(p.get('influence'))
 xgi90=xgi*90/max(mins,90); threat90=threat*90/max(mins,90); creativity90=creativity*90/max(mins,90); influence90=influence*90/max(mins,90)
 # Positional-neutral multiplier centered near 1. Underlying xGI dominates;
 # ICT terms only nudge the estimate and are strongly shrunk early season.
 raw=1 + .22*(xgi90-.35) + .0008*(threat90-35) + .0005*(creativity90-30) + .00035*(influence90-35)
 mult=1+(clamp(raw,.72,1.35)-1)*shrink
 return {'multiplier':clamp(mult,.82,1.22),'xgi90':xgi90,'threat90':threat90,'creativity90':creativity90,'influence90':influence90,'sample_minutes':mins,'confidence':shrink}

def apply_to_rates(core,p):
 f=form_signal(p);m=f['multiplier'];out=dict(core)
 out['goal90']*=m;out['assist90']*=m
 return out,f

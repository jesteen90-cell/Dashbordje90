from __future__ import annotations
def clamp(x,a,b):return max(a,min(b,x))
def n(x,d=0.):
 try:return float(x)
 except:return d
def form_signal(p,decay=.82):
 mins=n(p.get('minutes'));starts=n(p.get('starts'));shrink=mins/(mins+450);xg=n(p.get('expected_goals'));xa=n(p.get('expected_assists'));xgi=n(p.get('expected_goal_involvements'),xg+xa);threat=n(p.get('threat'));creativity=n(p.get('creativity'));influence=n(p.get('influence'));xgi90=xgi*90/max(mins,90);threat90=threat*90/max(mins,90);creativity90=creativity*90/max(mins,90);influence90=influence*90/max(mins,90);raw=1+.22*(xgi90-.35)+.0008*(threat90-35)+.0005*(creativity90-30)+.00035*(influence90-35);mult=1+(clamp(raw,.72,1.35)-1)*shrink;return {'multiplier':clamp(mult,.82,1.22),'xgi90':xgi90,'threat90':threat90,'creativity90':creativity90,'influence90':influence90,'sample_minutes':mins,'confidence':shrink}

from __future__ import annotations

def n(v,d=0.):
 try:return float(v)
 except:return d

def clamp(x,a,b):return max(a,min(b,x))

def recent_signal(history,last_n=6,decay=.78):
 """Recency-weighted underlying form from official element-summary history.
 Newest matches receive most weight. xG/xA and minutes are used, not FPL points.
 Returns a conservative multiplier with sample-size shrinkage.
 """
 rows=sorted(history,key=lambda r:int(r.get('round') or 0),reverse=True)[:last_n]
 if not rows:return {'multiplier':1.,'xgi90':0.,'minutes':0.,'matches':0,'confidence':0.}
 sxgi=smin=sw=0.
 for age,r in enumerate(rows):
  w=decay**age;mins=n(r.get('minutes'));xg=n(r.get('expected_goals'));xa=n(r.get('expected_assists'));sxgi+=(xg+xa)*w;smin+=mins*w;sw+=w
 xgi90=sxgi*90/max(smin,90);raw=1+.30*(xgi90-.35);total_minutes=sum(n(r.get('minutes')) for r in rows);conf=total_minutes/(total_minutes+360);mult=1+(clamp(raw,.72,1.35)-1)*conf
 return {'multiplier':clamp(mult,.84,1.20),'xgi90':xgi90,'minutes':total_minutes,'matches':len(rows),'confidence':conf}

def blend_rates(base,season_form,recent_form):
 """Recent form is a controlled overlay; season form remains the anchor."""
 out=dict(base);sm=n(season_form.get('multiplier'),1);rm=n(recent_form.get('multiplier'),1);rc=n(recent_form.get('confidence'))
 combined=sm*(1+(rm-1)*(.35+.35*rc));combined=clamp(combined,.80,1.24);out['goal90']*=combined;out['assist90']*=combined
 return out,combined

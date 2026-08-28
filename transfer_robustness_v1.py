"""Pre-deadline transfer robustness audit.

Tests each displayed candidate across immediate, short and planning horizons.
This is deliberately a shadow safety layer: it exposes fragile recommendations
without silently changing the validated production ranking before evidence exists.
"""
import json
from pathlib import Path

p=Path('data.json'); d=json.loads(p.read_text())
gws=[int(x) for x in ((d.get('transfer_option_pool') or {}).get('gws') or [])]
weights={int(k):float(v) for k,v in ((d.get('transfer_option_pool') or {}).get('weights') or {}).items()}
pool={int(x['id']):x for x in ((d.get('transfer_option_pool') or {}).get('players') or [])}

def xp(pid,gw): return float((pool.get(int(pid),{}).get('xp') or {}).get(str(gw),0))
def horizon(pair,n):
    outp,inp=pair.get('out') or {},pair.get('in') or {}; oid=int(outp.get('id') or 0); iid=int(inp.get('id') or 0)
    use=gws[:n]; return sum((xp(iid,g)-xp(oid,g))*weights.get(g,1) for g in use)

def audit(c):
    pairs=c.get('pairs') or []
    vals={}
    for n,label in ((1,'gw1'),(3,'gw3'),(5,'plan')):
        vals[label]=round(sum(horizon(x,n) for x in pairs),3)
    signs=sum(v>0.05 for v in vals.values()); negatives=sum(v<-.05 for v in vals.values())
    spread=round(max(vals.values())-min(vals.values()),3) if vals else 0
    if negatives: label='FRAGIL'; score=max(0,0.45-.08*spread)
    elif signs==3: label='ROBUST'; score=max(.55,min(1,.82-.04*spread))
    else: label='BLANDET'; score=max(.35,min(.7,.58-.04*spread))
    return {'version':'1.0-shadow','affects_ranking':False,'label':label,'score':round(score,3),'weighted_gain':vals,'spread':spread,'rule':'Must not replace validated ranking; pre-deadline disagreement warning only.'}

for c in d.get('candidates') or []: c['robustness_shadow']=audit(c)
rows=[c.get('robustness_shadow') for c in d.get('candidates') or []]
d['transfer_robustness']={'version':'1.0-shadow','affects_transfer_ranking':False,'candidate_count':len(rows),'robust_count':sum((r or {}).get('label')=='ROBUST' for r in rows),'purpose':'Cross-horizon agreement check before committing a transfer.'}
p.write_text(json.dumps(d,ensure_ascii=False,indent=2))
print('Transfer robustness audit',d['transfer_robustness'])
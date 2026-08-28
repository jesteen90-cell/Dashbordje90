from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
import requests

BASE='https://fantasy.premierleague.com/api';SNAPS=Path('timing_snapshots');OUT=Path('timing_backtest');SCORE=OUT/'scorecard.json'

def get(path):
    r=requests.get(f"{BASE}/{path.lstrip('/')}",headers={'Accept':'application/json','User-Agent':'fpl-autopilot-timing-backtest'},timeout=18);r.raise_for_status();return r.json()

def value_at(pid,gw,cache):
    pid=int(pid)
    if pid not in cache:
        hist=get(f'element-summary/{pid}/').get('history') or []
        cache[pid]={int(x['round']):int(x.get('value',0)) for x in hist}
    return cache[pid].get(int(gw))

def evaluate(snapshot,cache):
    gw=int(snapshot['gw']);rows=[]
    for c in snapshot.get('candidates') or []:
        out=c.get('out') or {};inn=c.get('in') or {};op=out.get('price_raw');ip=inn.get('price_raw')
        if op is None or ip is None or out.get('id') is None or inn.get('id') is None:continue
        od=value_at(out['id'],gw,cache);idv=value_at(inn['id'],gw,cache)
        if od is None or idv is None:continue
        bank_raw=int(round(float(c.get('bank_after') or 0)*10));budget_shift=(od-int(op))-(idv-int(ip));deadline_bank=bank_raw+budget_shift
        adverse=budget_shift<0;locked=deadline_bank<0
        label=str((c.get('timing') or {}).get('label') or '')
        early=('TIDLIG' in label or 'FØLG TETT' in label)
        actual_need=locked or budget_shift<=-1
        rows.append({'candidate_index':c.get('candidate_index'),'label':label,'early_signal':early,'actual_early_need':actual_need,'snapshot_bank_raw':bank_raw,'deadline_bank_raw':deadline_bank,'budget_shift_raw':budget_shift,'adverse_price_move':adverse,'would_lock':locked,'out_price_snapshot':op,'out_price_deadline':od,'in_price_snapshot':ip,'in_price_deadline':idv})
    return {'version':'1.0','gw':gw,'evaluated_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'candidates':rows}

def aggregate(results):
    rows=[x for r in results for x in r.get('candidates') or []];n=len(rows)
    tp=sum(x['early_signal'] and x['actual_early_need'] for x in rows);fp=sum(x['early_signal'] and not x['actual_early_need'] for x in rows);fn=sum((not x['early_signal']) and x['actual_early_need'] for x in rows);tn=sum((not x['early_signal']) and (not x['actual_early_need']) for x in rows)
    precision=tp/(tp+fp) if tp+fp else None;recall=tp/(tp+fn) if tp+fn else None;accuracy=(tp+tn)/n if n else None
    ready=n>=20;promote=bool(ready and precision is not None and precision>=.65 and (recall or 0)>=.55)
    return {'version':'1.0','generated_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),'evaluated_gws':len(results),'candidate_samples':n,'true_positive':tp,'false_positive':fp,'false_negative':fn,'true_negative':tn,'precision':round(precision,3) if precision is not None else None,'recall':round(recall,3) if recall is not None else None,'accuracy':round(accuracy,3) if accuracy is not None else None,'calibration_ready':ready,'promote_timing_thresholds':promote,'note':'Måler om tidlig-/følg-tett-signalet faktisk fanget prisbevegelser som reduserte eller låste budsjettet. Ingen prisprognose og ingen automatisk gjennomføring.'}

def main():
    OUT.mkdir(exist_ok=True);boot=get('bootstrap-static/');finished={int(e['id']) for e in boot.get('events',[]) if e.get('finished')};cache={};results=[]
    for p in sorted(SNAPS.glob('gw*.json')):
        s=json.loads(p.read_text(encoding='utf-8'));gw=int(s['gw'])
        if gw not in finished:continue
        r=evaluate(s,cache);(OUT/f'gw{gw:02d}.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');results.append(r)
    score=aggregate(results);SCORE.write_text(json.dumps(score,ensure_ascii=False,indent=2),encoding='utf-8');print('Timing backtest updated',score)

if __name__=='__main__':main()

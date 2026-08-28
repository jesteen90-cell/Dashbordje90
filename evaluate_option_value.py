from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
import requests

BASE = 'https://fantasy.premierleague.com/api'
SNAPS = Path('option_value_snapshots')
OUT = Path('option_value_backtest')
SCORE = OUT / 'scorecard.json'


def get(path):
    r = requests.get(f"{BASE}/{path.lstrip('/')}", headers={'Accept':'application/json','User-Agent':'fpl-autopilot-option-backtest'}, timeout=18)
    r.raise_for_status()
    return r.json()


def actual(pid, gw, cache):
    pid = int(pid)
    if pid not in cache:
        hist = get(f'element-summary/{pid}/').get('history') or []
        cache[pid] = {int(x['round']): int(x.get('total_points', 0)) for x in hist}
    return int(cache[pid].get(int(gw), 0))


def three_gw_gain(candidate, gw, cache):
    out_id = (candidate.get('out') or {}).get('id')
    in_id = (candidate.get('in') or {}).get('id')
    if out_id is None or in_id is None:
        return None
    return sum(actual(in_id, g, cache) - actual(out_id, g, cache) for g in range(gw, gw + 3))


def evaluate(snapshot, finished_gws, cache):
    gw = int(snapshot['gw'])
    if any(g not in finished_gws for g in range(gw, gw + 3)):
        return None
    rows = []
    for c in snapshot.get('candidates') or []:
        row = dict(c)
        row['actual_three_gw_pair_gain'] = three_gw_gain(c, gw, cache)
        if row['actual_three_gw_pair_gain'] is not None:
            rows.append(row)
    if not rows:
        return None
    production = min(rows, key=lambda x: int(x.get('rank') or 999))
    shadow = max(rows, key=lambda x: float(x.get('shadow_score') or -999))
    best = max(rows, key=lambda x: int(x.get('actual_three_gw_pair_gain') or -999))
    prod_gain = int(production['actual_three_gw_pair_gain'])
    shadow_gain = int(shadow['actual_three_gw_pair_gain'])
    best_gain = int(best['actual_three_gw_pair_gain'])
    return {
        'evaluation_version': '1.0',
        'gw': gw,
        'frozen_at': snapshot.get('frozen_at'),
        'evaluated_at': datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        'production_rank': production.get('rank'),
        'shadow_rank': shadow.get('rank'),
        'production_actual_gain': prod_gain,
        'shadow_actual_gain': shadow_gain,
        'shadow_minus_production': shadow_gain - prod_gain,
        'shadow_won': shadow_gain > prod_gain,
        'shadow_tied': shadow_gain == prod_gain,
        'best_candidate_actual_gain': best_gain,
        'production_regret': best_gain - prod_gain,
        'shadow_regret': best_gain - shadow_gain,
        'production_choice': production,
        'shadow_choice': shadow,
        'candidates': rows,
    }


def aggregate(results):
    if not results:
        return {'version':'1.0','evaluated_gws':0,'gws':[],'promotion_ready':False,'promote':False,'reason':'Need completed three-GW samples'}
    n_rows = len(results)
    diffs = [int(r['shadow_minus_production']) for r in results]
    wins = sum(bool(r['shadow_won']) for r in results)
    ties = sum(bool(r['shadow_tied']) for r in results)
    losses = n_rows - wins - ties
    mean_lift = sum(diffs) / n_rows
    non_loss = (wins + ties) / n_rows
    ready = n_rows >= 8
    promote = ready and mean_lift >= 0.35 and non_loss >= 0.75 and wins >= 2
    return {
        'version':'1.0',
        'generated_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        'evaluated_gws':n_rows,
        'gws':[int(r['gw']) for r in results],
        'shadow_wins':wins,
        'ties':ties,
        'shadow_losses':losses,
        'shadow_non_loss_rate':round(non_loss,3),
        'mean_shadow_minus_production':round(mean_lift,3),
        'mean_production_regret':round(sum(float(r['production_regret']) for r in results)/n_rows,3),
        'mean_shadow_regret':round(sum(float(r['shadow_regret']) for r in results)/n_rows,3),
        'promotion_ready':ready,
        'promote':promote,
        'promotion_rule':'8+ samples, mean 3GW lift >=0.35, non-loss >=75%, at least 2 wins',
        'reason':'Evidence threshold passed' if promote else 'Shadow remains isolated until evidence threshold passes',
    }


def main():
    OUT.mkdir(exist_ok=True)
    boot = get('bootstrap-static/')
    finished = {int(e['id']) for e in boot.get('events',[]) if e.get('finished')}
    cache = {}
    results = []
    for path in sorted(SNAPS.glob('gw*.json')):
        snapshot = json.loads(path.read_text(encoding='utf-8'))
        result = evaluate(snapshot, finished, cache)
        if result is None:
            continue
        (OUT / f"gw{int(result['gw']):02d}.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        results.append(result)
    results.sort(key=lambda x:int(x['gw']))
    score = aggregate(results)
    SCORE.write_text(json.dumps(score,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Option value scorecard updated', score)


if __name__ == '__main__':
    main()

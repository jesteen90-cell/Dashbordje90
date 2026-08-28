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

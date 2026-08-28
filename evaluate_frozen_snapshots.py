from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import requests

BASE = "https://fantasy.premierleague.com/api"
SNAP_DIR = Path("snapshots")
OUT_DIR = Path("backtest")
SCORECARD = OUT_DIR / "scorecard.json"
TIMEOUT = 18


def get(path):
    r = requests.get(
        f"{BASE}/{path.lstrip('/')}",
        headers={"Accept": "application/json", "User-Agent": "fpl-autopilot-backtest-v1"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()


def n(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def player_ids(snapshot):
    ids = set()
    for key in ("lineup", "bench", "captain_comparison"):
        for p in snapshot.get(key) or []:
            if p.get("id") is not None:
                ids.add(int(p["id"]))
    cmp = snapshot.get("comparison") or {}
    for key in ("current_xi", "transfer_xi"):
        for p in cmp.get(key) or []:
            if p.get("id") is not None:
                ids.add(int(p["id"]))
    for c in snapshot.get("candidates") or []:
        for pair in c.get("pairs") or []:
            for side in ("out", "in"):
                p = pair.get(side) or {}
                if p.get("id") is not None:
                    ids.add(int(p["id"]))
    return sorted(ids)


def history_points(pid, cache):
    if pid not in cache:
        data = get(f"element-summary/{pid}/")
        cache[pid] = {int(x["round"]): int(x.get("total_points", 0)) for x in data.get("history", [])}
    return cache[pid]


def actual(pid, gw, cache):
    return int(history_points(pid, cache).get(int(gw), 0))


def xi_actual(rows, gw, cache):
    total = sum(actual(int(p["id"]), gw, cache) for p in rows if p.get("id") is not None)
    cap = next((p for p in rows if p.get("captain")), None)
    if cap and cap.get("id") is not None:
        total += actual(int(cap["id"]), gw, cache)
    return total


def player_accuracy(rows, gw, cache):
    samples = []
    seen = set()
    for p in rows:
        pid = p.get("id")
        if pid is None or int(pid) in seen:
            continue
        seen.add(int(pid))
        pred = n(p.get("xp"))
        act = actual(int(pid), gw, cache)
        samples.append({
            "id": int(pid), "name": p.get("name"), "predicted": round(pred, 2),
            "actual": act, "error": round(act - pred, 2), "abs_error": round(abs(act - pred), 2),
            "inside_p10_p90": n(p.get("xp_low"), -1e9) <= act <= n(p.get("xp_high"), 1e9),
        })
    return samples


def pair_three_gw(snapshot, gw, finished_gws, cache):
    cmp = snapshot.get("comparison") or {}
    changes = cmp.get("changes") or []
    end = gw + 2
    if not changes or any(g not in finished_gws for g in range(gw, end + 1)):
        return None
    rows = []
    net = 0
    for change in changes:
        outp, inp = change.get("out") or {}, change.get("in") or {}
        if outp.get("id") is None or inp.get("id") is None:
            continue
        out_pts = sum(actual(int(outp["id"]), g, cache) for g in range(gw, end + 1))
        in_pts = sum(actual(int(inp["id"]), g, cache) for g in range(gw, end + 1))
        delta = in_pts - out_pts
        net += delta
        rows.append({"out": outp.get("name"), "in": inp.get("name"), "out_points": out_pts, "in_points": in_pts, "delta": delta})
    return {"actual_pair_gain": net, "pairs": rows} if rows else None


def evaluate(snapshot, finished_gws, cache):
    gw = int(snapshot["gw"])
    cmp = snapshot.get("comparison") or {}
    current = cmp.get("current_xi") or snapshot.get("lineup") or []
    transfer = cmp.get("transfer_xi") or current
    chosen = transfer if (snapshot.get("decision_explanation") or {}).get("decision") == "BYTT" else current

    samples = player_accuracy(chosen, gw, cache)
    mae = sum(x["abs_error"] for x in samples) / len(samples) if samples else 0
    bias = sum(x["error"] for x in samples) / len(samples) if samples else 0
    coverage = sum(bool(x["inside_p10_p90"]) for x in samples) / len(samples) if samples else 0

    cur_actual = xi_actual(current, gw, cache)
    tr_actual = xi_actual(transfer, gw, cache)
    decision = (snapshot.get("decision_explanation") or {}).get("decision", "BANK")
    decision_actual = tr_actual if decision == "BYTT" else cur_actual
    alternative_actual = cur_actual if decision == "BYTT" else tr_actual

    cap_rows = snapshot.get("captain_comparison") or []
    cap = next((p for p in chosen if p.get("captain")), None)
    cap_actual = actual(int(cap["id"]), gw, cache) if cap and cap.get("id") is not None else 0
    best_cap_actual = max((actual(int(p["id"]), gw, cache) for p in cap_rows if p.get("id") is not None), default=cap_actual)

    return {
        "evaluation_version": "1.0",
        "gw": gw,
        "frozen_at": snapshot.get("frozen_at"),
        "evaluated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "model_version": snapshot.get("model_version"),
        "decision_layer_version": (snapshot.get("decision_layer") or {}).get("version"),
        "decision": decision,
        "predicted_weighted_gain": n((snapshot.get("decision_explanation") or {}).get("weighted_gain")),
        "actual_chosen_xi": decision_actual,
        "actual_alternative_xi": alternative_actual,
        "decision_regret": alternative_actual - decision_actual,
        "decision_won": decision_actual >= alternative_actual,
        "captain": cap.get("name") if cap else None,
        "captain_actual": cap_actual,
        "best_top5_captain_actual": best_cap_actual,
        "captain_regret": best_cap_actual - cap_actual,
        "captain_hit": cap_actual >= best_cap_actual,
        "xp_mae": round(mae, 3),
        "xp_bias": round(bias, 3),
        "interval_80_coverage": round(coverage, 3),
        "players": samples,
        "three_gw_transfer": pair_three_gw(snapshot, gw, finished_gws, cache),
    }


def aggregate(results):
    if not results:
        return {"version": "1.0", "evaluated_gws": 0, "gws": []}
    def avg(key):
        vals = [n(x.get(key)) for x in results]
        return sum(vals) / len(vals) if vals else 0
    transfer3 = [x["three_gw_transfer"]["actual_pair_gain"] for x in results if x.get("three_gw_transfer")]
    bytt = [x for x in results if x.get("decision") == "BYTT"]
    return {
        "version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "evaluated_gws": len(results),
        "gws": [int(x["gw"]) for x in results],
        "xp_mae": round(avg("xp_mae"), 3),
        "xp_bias": round(avg("xp_bias"), 3),
        "interval_80_coverage": round(avg("interval_80_coverage"), 3),
        "decision_win_rate": round(sum(bool(x.get("decision_won")) for x in results) / len(results), 3),
        "mean_decision_regret": round(avg("decision_regret"), 3),
        "captain_hit_rate": round(sum(bool(x.get("captain_hit")) for x in results) / len(results), 3),
        "mean_captain_regret": round(avg("captain_regret"), 3),
        "bytt_samples": len(bytt),
        "bytt_win_rate": round(sum(bool(x.get("decision_won")) for x in bytt) / len(bytt), 3) if bytt else None,
        "three_gw_samples": len(transfer3),
        "mean_three_gw_pair_gain": round(sum(transfer3) / len(transfer3), 3) if transfer3 else None,
        "adaptive_feedback_ready": len(results) >= 4,
    }


def main():
    OUT_DIR.mkdir(exist_ok=True)
    bootstrap = get("bootstrap-static/")
    finished_gws = {int(e["id"]) for e in bootstrap.get("events", []) if e.get("finished")}
    cache = {}
    results = []
    for path in sorted(SNAP_DIR.glob("gw*.json")):
        snapshot = json.loads(path.read_text(encoding="utf-8"))
        gw = int(snapshot["gw"])
        if gw not in finished_gws:
            continue
        result = evaluate(snapshot, finished_gws, cache)
        out = OUT_DIR / f"gw{gw:02d}.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        results.append(result)
    results.sort(key=lambda x: int(x["gw"]))
    score = aggregate(results)
    SCORECARD.write_text(json.dumps(score, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Backtest scorecard updated: {score.get('evaluated_gws', 0)} finished GWs")


if __name__ == "__main__":
    main()

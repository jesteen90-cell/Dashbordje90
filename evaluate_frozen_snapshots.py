from __future__ import annotations

import json
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
        headers={"Accept": "application/json", "User-Agent": "fpl-autopilot-backtest-v2"},
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


def history(pid, cache):
    if pid not in cache:
        data = get(f"element-summary/{pid}/")
        cache[pid] = {
            int(x["round"]): {
                "points": int(x.get("total_points", 0)),
                "minutes": int(x.get("minutes", 0)),
            }
            for x in data.get("history", [])
        }
    return cache[pid]


def actual(pid, gw, cache):
    return int(history(pid, cache).get(int(gw), {}).get("points", 0))


def actual_minutes(pid, gw, cache):
    return int(history(pid, cache).get(int(gw), {}).get("minutes", 0))


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
        pred_min = n(p.get("expected_minutes"), 90)
        act_min = actual_minutes(int(pid), gw, cache)
        samples.append({
            "id": int(pid),
            "name": p.get("name"),
            "position": p.get("position") or "UNK",
            "predicted": round(pred, 2),
            "actual": act,
            "error": round(act - pred, 2),
            "abs_error": round(abs(act - pred), 2),
            "inside_p10_p90": n(p.get("xp_low"), -1e9) <= act <= n(p.get("xp_high"), 1e9),
            "predicted_minutes": round(pred_min, 1),
            "actual_minutes": act_min,
            "minutes_error": round(act_min - pred_min, 1),
            "minutes_abs_error": round(abs(act_min - pred_min), 1),
            "expected_to_play_but_zero": pred_min >= 60 and act_min == 0,
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
    decision = (snapshot.get("decision_explanation") or {}).get("decision", "BANK")
    chosen = transfer if decision == "BYTT" else current

    samples = player_accuracy(chosen, gw, cache)
    mae = sum(x["abs_error"] for x in samples) / len(samples) if samples else 0
    bias = sum(x["error"] for x in samples) / len(samples) if samples else 0
    coverage = sum(bool(x["inside_p10_p90"]) for x in samples) / len(samples) if samples else 0
    min_mae = sum(x["minutes_abs_error"] for x in samples) / len(samples) if samples else 0
    min_bias = sum(x["minutes_error"] for x in samples) / len(samples) if samples else 0
    zero_misses = sum(bool(x["expected_to_play_but_zero"]) for x in samples)

    cur_actual = xi_actual(current, gw, cache)
    tr_actual = xi_actual(transfer, gw, cache)
    decision_actual = tr_actual if decision == "BYTT" else cur_actual
    alternative_actual = cur_actual if decision == "BYTT" else tr_actual

    cap_rows = snapshot.get("captain_comparison") or []
    cap = next((p for p in chosen if p.get("captain")), None)
    cap_actual = actual(int(cap["id"]), gw, cache) if cap and cap.get("id") is not None else 0
    best_cap_actual = max((actual(int(p["id"]), gw, cache) for p in cap_rows if p.get("id") is not None), default=cap_actual)

    by_position = {}
    for pos in ("GK", "DEF", "MID", "FWD"):
        ps = [x for x in samples if x.get("position") == pos]
        if ps:
            by_position[pos] = {
                "samples": len(ps),
                "xp_mae": round(sum(x["abs_error"] for x in ps) / len(ps), 3),
                "xp_bias": round(sum(x["error"] for x in ps) / len(ps), 3),
                "minutes_mae": round(sum(x["minutes_abs_error"] for x in ps) / len(ps), 2),
                "minutes_bias": round(sum(x["minutes_error"] for x in ps) / len(ps), 2),
            }

    return {
        "evaluation_version": "2.0-component-diagnostics",
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
        "minutes_mae": round(min_mae, 2),
        "minutes_bias": round(min_bias, 2),
        "expected_to_play_zero_count": zero_misses,
        "position_diagnostics": by_position,
        "players": samples,
        "three_gw_transfer": pair_three_gw(snapshot, gw, finished_gws, cache),
    }


def aggregate(results):
    if not results:
        return {"version": "2.0", "evaluated_gws": 0, "gws": [], "component_feedback_ready": False}

    def avg(key, subset=None):
        rows = subset if subset is not None else results
        vals = [n(x.get(key)) for x in rows]
        return sum(vals) / len(vals) if vals else 0

    transfer3 = [x["three_gw_transfer"]["actual_pair_gain"] for x in results if x.get("three_gw_transfer")]
    bytt = [x for x in results if x.get("decision") == "BYTT"]
    bank = [x for x in results if x.get("decision") == "BANK"]

    pos_acc = {}
    for pos in ("GK", "DEF", "MID", "FWD"):
        rows = []
        for r in results:
            d = (r.get("position_diagnostics") or {}).get(pos)
            if d:
                rows.append(d)
        if rows:
            weight = sum(int(x.get("samples") or 0) for x in rows)
            def wavg(key):
                return sum(n(x.get(key)) * int(x.get("samples") or 0) for x in rows) / weight if weight else 0
            pos_acc[pos] = {
                "samples": weight,
                "xp_mae": round(wavg("xp_mae"), 3),
                "xp_bias": round(wavg("xp_bias"), 3),
                "minutes_mae": round(wavg("minutes_mae"), 2),
                "minutes_bias": round(wavg("minutes_bias"), 2),
            }

    total_player_samples = sum(len(r.get("players") or []) for r in results)
    total_zero_misses = sum(int(r.get("expected_to_play_zero_count") or 0) for r in results)

    return {
        "version": "2.0",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "evaluated_gws": len(results),
        "gws": [int(x["gw"]) for x in results],
        "xp_mae": round(avg("xp_mae"), 3),
        "xp_bias": round(avg("xp_bias"), 3),
        "interval_80_coverage": round(avg("interval_80_coverage"), 3),
        "minutes_mae": round(avg("minutes_mae"), 2),
        "minutes_bias": round(avg("minutes_bias"), 2),
        "expected_to_play_zero_rate": round(total_zero_misses / total_player_samples, 4) if total_player_samples else 0,
        "position_diagnostics": pos_acc,
        "decision_win_rate": round(sum(bool(x.get("decision_won")) for x in results) / len(results), 3),
        "mean_decision_regret": round(avg("decision_regret"), 3),
        "bank_samples": len(bank),
        "bank_win_rate": round(sum(bool(x.get("decision_won")) for x in bank) / len(bank), 3) if bank else None,
        "bank_mean_regret": round(avg("decision_regret", bank), 3) if bank else None,
        "bytt_samples": len(bytt),
        "bytt_win_rate": round(sum(bool(x.get("decision_won")) for x in bytt) / len(bytt), 3) if bytt else None,
        "bytt_mean_regret": round(avg("decision_regret", bytt), 3) if bytt else None,
        "captain_hit_rate": round(sum(bool(x.get("captain_hit")) for x in results) / len(results), 3),
        "mean_captain_regret": round(avg("captain_regret"), 3),
        "three_gw_samples": len(transfer3),
        "mean_three_gw_pair_gain": round(sum(transfer3) / len(transfer3), 3) if transfer3 else None,
        "adaptive_feedback_ready": len(results) >= 4,
        "component_feedback_ready": len(results) >= 6,
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
    print(f"Backtest scorecard v2 updated: {score.get('evaluated_gws', 0)} finished GWs")


if __name__ == "__main__":
    main()

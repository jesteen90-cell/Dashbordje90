from __future__ import annotations

import json
from pathlib import Path

PATH = Path("data.json")
SCORECARD = Path("backtest/scorecard.json")
FT_FLEX_VALUE = 0.45
BASE_DO_THRESHOLD = 1.15
CONSIDER_THRESHOLD = 0.35


def n(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def adaptive_controls():
    """Calibrate decision controls from completed frozen snapshots only.

    Threshold feedback starts at 4 GWs. Component-level minute-risk feedback
    needs at least 6 GWs. All adjustments are deliberately small and bounded.
    """
    controls = {
        "threshold": BASE_DO_THRESHOLD,
        "minutes_penalty_scale": 1.0,
        "availability_penalty_scale": 1.0,
        "volatility_penalty_scale": 1.0,
    }
    feedback = {
        "enabled": False,
        "component_enabled": False,
        "base_threshold": BASE_DO_THRESHOLD,
        "effective_threshold": BASE_DO_THRESHOLD,
        "evaluated_gws": 0,
        "reasons": [],
        "diagnostics": {},
    }
    if not SCORECARD.exists():
        return controls, feedback
    try:
        score = json.loads(SCORECARD.read_text(encoding="utf-8"))
    except Exception:
        return controls, feedback

    samples = int(score.get("evaluated_gws") or 0)
    feedback["evaluated_gws"] = samples
    feedback["diagnostics"] = {
        "xp_mae": score.get("xp_mae"),
        "xp_bias": score.get("xp_bias"),
        "minutes_mae": score.get("minutes_mae"),
        "minutes_bias": score.get("minutes_bias"),
        "expected_to_play_zero_rate": score.get("expected_to_play_zero_rate"),
        "captain_hit_rate": score.get("captain_hit_rate"),
        "mean_captain_regret": score.get("mean_captain_regret"),
        "position_diagnostics": score.get("position_diagnostics") or {},
    }

    if samples < 4 or not score.get("adaptive_feedback_ready"):
        feedback["reasons"].append("Minst 4 ferdige frozen-snapshot GWs kreves før terskelkalibrering")
        return controls, feedback

    adjustment = 0.0
    bytt_samples = int(score.get("bytt_samples") or 0)
    bank_samples = int(score.get("bank_samples") or 0)
    bytt_win = score.get("bytt_win_rate")
    bank_win = score.get("bank_win_rate")
    bytt_regret = n(score.get("bytt_mean_regret"))
    bank_regret = n(score.get("bank_mean_regret"))
    coverage = n(score.get("interval_80_coverage"), 0.8)

    # If BYTT has performed poorly, demand more edge. If BANK has repeatedly
    # left points on the table, lower the threshold modestly.
    if bytt_samples >= 2 and bytt_win is not None:
        bw = n(bytt_win)
        if bw < 0.45:
            adjustment += 0.16
            feedback["reasons"].append("Historiske BYTT-beslutninger har vunnet for sjelden")
        elif bw > 0.70:
            adjustment -= 0.08
            feedback["reasons"].append("Historiske BYTT-beslutninger har vært robuste")
        if bytt_regret > 1.0:
            adjustment += 0.08
            feedback["reasons"].append("BYTT-feil har hatt merkbar faktisk kostnad")

    if bank_samples >= 2 and bank_win is not None:
        bkw = n(bank_win)
        if bkw < 0.45 or bank_regret > 1.0:
            adjustment -= 0.12
            feedback["reasons"].append("BANK har for ofte latt et bedre alternativ stå ubrukt")
        elif bkw > 0.75 and bank_regret <= 0:
            adjustment += 0.04
            feedback["reasons"].append("BANK-beslutninger har vært svært robuste")

    if coverage < 0.65:
        adjustment += 0.07
        feedback["reasons"].append("Usikkerhetsintervallene har vært for optimistiske")

    controls["threshold"] = max(0.90, min(1.45, BASE_DO_THRESHOLD + adjustment))
    feedback.update({
        "enabled": True,
        "effective_threshold": round(controls["threshold"], 2),
        "adjustment": round(controls["threshold"] - BASE_DO_THRESHOLD, 2),
        "bytt_samples": bytt_samples,
        "bytt_win_rate": bytt_win,
        "bytt_mean_regret": score.get("bytt_mean_regret"),
        "bank_samples": bank_samples,
        "bank_win_rate": bank_win,
        "bank_mean_regret": score.get("bank_mean_regret"),
        "interval_80_coverage": score.get("interval_80_coverage"),
    })

    # Component-level adaptation begins later. Negative minutes bias means
    # actual minutes have been below expected minutes on average.
    if samples >= 6 and score.get("component_feedback_ready"):
        feedback["component_enabled"] = True
        min_bias = n(score.get("minutes_bias"))
        zero_rate = n(score.get("expected_to_play_zero_rate"))
        min_mae = n(score.get("minutes_mae"))

        if min_bias < -8:
            controls["minutes_penalty_scale"] = 1.18
            feedback["reasons"].append("Minuttmodellen har vært for optimistisk; rotasjonsstraffen økes")
        elif min_bias > 8 and min_mae < 24:
            controls["minutes_penalty_scale"] = 0.92
            feedback["reasons"].append("Minuttmodellen har vært forsiktig; rotasjonsstraffen reduseres litt")

        if zero_rate > 0.07:
            controls["availability_penalty_scale"] = 1.18
            feedback["reasons"].append("For mange antatte startere har endt på 0 minutter; tilgjengelighetsstraffen økes")
        elif zero_rate < 0.025 and min_mae < 20:
            controls["availability_penalty_scale"] = 0.95

        if coverage < 0.60:
            controls["volatility_penalty_scale"] = 1.12

    feedback["controls"] = {k: round(v, 3) for k, v in controls.items()}
    return controls, feedback


def risk_penalty(player, controls):
    availability = max(0.0, min(1.0, n(player.get("availability"), 1.0)))
    xmins = max(0.0, min(90.0, n(player.get("expected_minutes"), 90.0)))
    volatility = max(0.0, n(player.get("volatility"), 0.0))
    availability_penalty = max(0.0, 0.92 - availability) * 3.0 * controls["availability_penalty_scale"]
    minutes_penalty = max(0.0, 70.0 - xmins) / 70.0 * 0.85 * controls["minutes_penalty_scale"]
    volatility_penalty = max(0.0, volatility - 1.05) * 0.30 * controls["volatility_penalty_scale"]
    return availability_penalty + minutes_penalty + volatility_penalty


def candidate_quality(candidate, controls):
    pair = (candidate.get("pairs") or [{}])[0]
    outgoing, incoming = pair.get("out") or {}, pair.get("in") or {}
    horizon, short = n(candidate.get("horizon_gain")), n(candidate.get("short_gain"))
    fragility_delta = max(0.0, risk_penalty(incoming, controls) - risk_penalty(outgoing, controls))
    short_bonus = max(-0.25, min(0.35, short * 0.07))
    score = horizon - FT_FLEX_VALUE - fragility_delta + short_bonus
    reasons = []
    if fragility_delta > 0.20: reasons.append("Innkommende spiller har mer usikre minutter/tilgjengelighet")
    if short < 0: reasons.append("Byttet taper forventede poeng de neste tre rundene")
    if horizon <= FT_FLEX_VALUE: reasons.append("Langsiktig gevinst dekker ikke verdien av å beholde fleksibilitet")
    if n(incoming.get("expected_minutes"), 90) < 65: reasons.append("For lavt forventet minuttgrunnlag")
    if n(incoming.get("availability"), 1) < 0.85: reasons.append("Tilgjengeligheten er for usikker")
    threshold = controls["threshold"]
    status = "GJØR DET" if score >= threshold and not reasons else "VURDERES" if score >= CONSIDER_THRESHOLD else "SVAK"
    return round(score, 2), status, reasons


def reorder_bench(bench):
    outfield = [p for p in bench if p.get("position") != "GK"]
    keepers = [p for p in bench if p.get("position") == "GK"]
    outfield.sort(key=lambda p: (n(p.get("availability"), 1), n(p.get("expected_minutes")), n(p.get("xp"))), reverse=True)
    keepers.sort(key=lambda p: n(p.get("xp")), reverse=True)
    return outfield + keepers


def hard_gate_first_move(data, controls):
    comparison = data.get("comparison") or {}
    changes = comparison.get("changes") or []
    gain = n((data.get("optimizer") or {}).get("weighted_gain"))
    if not changes:
        return False, ["Ingen foreslått overgang i første trekk"]
    reasons = []
    for change in changes:
        incoming = change.get("in") or {}
        if n(incoming.get("availability"), 1) < 0.85:
            reasons.append(f"{incoming.get('name','Spilleren')} har usikker tilgjengelighet")
        if n(incoming.get("expected_minutes"), 90) < 65:
            reasons.append(f"{incoming.get('name','Spilleren')} har for lavt forventet minuttall")
    if gain < controls["threshold"]:
        reasons.append(f"Netto modellfordel {gain:.2f} er under beslutningsterskelen {controls['threshold']:.2f}")
    return not reasons, reasons


def choose_safer_vice(lineup):
    captain = next((p for p in lineup if p.get("captain")), None)
    candidates = [p for p in lineup if not p.get("captain")]
    if not candidates:
        return
    def vice_score(p):
        return n(p.get("xp")) * (0.72 + 0.18*n(p.get("availability"),1) + 0.10*n(p.get("expected_minutes"),90)/90)
    best = max(candidates, key=vice_score)
    for p in lineup:
        p["vice"] = p is best
    if captain:
        captain["vice"] = False


def captain_comparison(lineup):
    rows = []
    for p in lineup:
        xp = n(p.get("xp")); mins = n(p.get("expected_minutes"), 90); avail = n(p.get("availability"), 1)
        high = n(p.get("xp_high"), xp)
        ceiling = max(xp, high)
        score = xp*0.70 + ceiling*0.20 + (mins/90)*0.06 + avail*0.04
        rows.append({"id":p.get("id"),"name":p.get("name"),"team":p.get("team"),"xp":round(xp,2),"ceiling":round(ceiling,2),"expected_minutes":round(mins,0),"availability":round(avail,2),"score":round(score,3),"captain":bool(p.get("captain")),"vice":bool(p.get("vice"))})
    return sorted(rows, key=lambda x:x["score"], reverse=True)[:5]


def explain_decision(data, approved, blockers, controls):
    cmp = data.get("comparison") or {}; changes = cmp.get("changes") or []
    opt = data.get("optimizer") or {}; gain = n(opt.get("weighted_gain"))
    best = (data.get("candidates") or [{}])[0]
    short, horizon = n(best.get("short_gain")), n(best.get("horizon_gain"))
    reasons = []
    if changes:
        names = ", ".join(f"{(c.get('out') or {}).get('name','?')} → {(c.get('in') or {}).get('name','?')}" for c in changes)
        reasons.append(f"Første trekk modellen vurderer er {names}.")
    reasons.append(f"Estimert gevinst: {short:+.2f} xP neste 3 GW og {horizon:+.2f} xP over planhorisonten.")
    reasons.append(f"Gratisbytte-fleksibilitet verdsettes til {FT_FLEX_VALUE:.2f} xP; robust BYTT-terskel er {controls['threshold']:.2f}.")
    if blockers: reasons.extend(blockers[:2])
    else: reasons.append("Ingen harde minutt- eller tilgjengelighetsblokker stopper trekket.")
    distance = round(controls["threshold"] - gain, 2)
    trigger = "Anbefalingen er robust nok nå." if approved else f"Trenger omtrent {max(0,distance):.2f} mer netto modellfordel, eller at en blokkering forsvinner, før BYTT godkjennes."
    return {"decision":"BYTT" if approved else "BANK","why":reasons[:5],"weighted_gain":round(gain,2),"threshold":round(controls["threshold"],2),"distance_to_switch":max(0,distance),"switch_trigger":trigger,"horizon_3gw":round(short,2),"horizon_plan":round(horizon,2)}


def main():
    data = json.loads(PATH.read_text(encoding="utf-8"))
    controls, feedback = adaptive_controls()
    candidates = data.get("candidates") or []
    for c in candidates:
        score,status,reasons = candidate_quality(c, controls)
        c["edge"],c["status"] = score,status
        c["gate_misses"] = list(dict.fromkeys(reasons + list(c.get("gate_misses") or [])))[:3]
    candidates.sort(key=lambda c:(n(c.get("edge")),n(c.get("horizon_gain"))), reverse=True)
    strong=[c for c in candidates if c.get("status")!="SVAK"]
    data["candidates"] = strong[:6] if strong else candidates[:4]
    data["bench"] = reorder_bench(data.get("bench") or [])
    for lineup in [data.get("lineup") or [], (data.get("comparison") or {}).get("current_xi") or [], (data.get("comparison") or {}).get("transfer_xi") or []]:
        choose_safer_vice(lineup)
    approved, blockers = hard_gate_first_move(data, controls)
    comparison=data.get("comparison") or {}
    if comparison.get("changes"):
        comparison["status"]="GJØR DET" if approved else "BANK"
    data["comparison"]=comparison
    data["headline"]="GJØR BYTTET" if approved else "SPAR BYTTET"
    data.setdefault("recommendation",{})["transfers"] = (comparison.get("changes") or []) if approved else []
    lineup = comparison.get("transfer_xi") if approved else comparison.get("current_xi")
    lineup = lineup or data.get("lineup") or []
    data["captain_comparison"] = captain_comparison(lineup)
    data["decision_explanation"] = explain_decision(data, approved, blockers, controls)
    data["decision_layer"]={
        "version":"4.3-component-adaptive",
        "approved_first_move":approved,
        "threshold":round(controls["threshold"],2),
        "base_threshold":BASE_DO_THRESHOLD,
        "adaptive_feedback":feedback,
        "controls":{k:round(v,3) for k,v in controls.items()},
        "blockers":blockers,
        "candidate_count":len(data.get("candidates") or []),
        "bench_ordering":"outfield by availability/minutes/xP; goalkeeper last",
        "explainability":True,
        "captain_comparison":True,
        "backtest_adaptive":True,
        "component_adaptive":True,
    }
    PATH.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Decision layer 4.3 applied", "APPROVE" if approved else "BANK", f"threshold={controls['threshold']:.2f}")


if __name__ == "__main__":
    main()

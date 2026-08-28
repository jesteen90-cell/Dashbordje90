from __future__ import annotations

import json
from pathlib import Path

PATH = Path("data.json")
FT_FLEX_VALUE = 0.45
DO_THRESHOLD = 1.15
CONSIDER_THRESHOLD = 0.35


def n(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def risk_penalty(player):
    availability = max(0.0, min(1.0, n(player.get("availability"), 1.0)))
    xmins = max(0.0, min(90.0, n(player.get("expected_minutes"), 90.0)))
    volatility = max(0.0, n(player.get("volatility"), 0.0))
    return (max(0.0, 0.92 - availability) * 3.0
            + max(0.0, 70.0 - xmins) / 70.0 * 0.85
            + max(0.0, volatility - 1.05) * 0.30)


def candidate_quality(candidate):
    pair = (candidate.get("pairs") or [{}])[0]
    outgoing, incoming = pair.get("out") or {}, pair.get("in") or {}
    horizon, short = n(candidate.get("horizon_gain")), n(candidate.get("short_gain"))
    fragility_delta = max(0.0, risk_penalty(incoming) - risk_penalty(outgoing))
    short_bonus = max(-0.25, min(0.35, short * 0.07))
    score = horizon - FT_FLEX_VALUE - fragility_delta + short_bonus
    reasons = []
    if fragility_delta > 0.20: reasons.append("Innkommende spiller har mer usikre minutter/tilgjengelighet")
    if short < 0: reasons.append("Byttet taper forventede poeng de neste tre rundene")
    if horizon <= FT_FLEX_VALUE: reasons.append("Langsiktig gevinst dekker ikke verdien av å beholde fleksibilitet")
    if n(incoming.get("expected_minutes"), 90) < 65: reasons.append("For lavt forventet minuttgrunnlag")
    if n(incoming.get("availability"), 1) < 0.85: reasons.append("Tilgjengeligheten er for usikker")
    status = "GJØR DET" if score >= DO_THRESHOLD and not reasons else "VURDERES" if score >= CONSIDER_THRESHOLD else "SVAK"
    return round(score, 2), status, reasons


def reorder_bench(bench):
    outfield = [p for p in bench if p.get("position") != "GK"]
    keepers = [p for p in bench if p.get("position") == "GK"]
    outfield.sort(key=lambda p: (n(p.get("availability"), 1), n(p.get("expected_minutes")), n(p.get("xp"))), reverse=True)
    keepers.sort(key=lambda p: n(p.get("xp")), reverse=True)
    return outfield + keepers


def hard_gate_first_move(data):
    comparison = data.get("comparison") or {}
    changes = comparison.get("changes") or []
    gain = n((data.get("optimizer") or {}).get("weighted_gain"))
    if not changes: return False, ["Ingen foreslått overgang i første trekk"]
    reasons = []
    for change in changes:
        incoming = change.get("in") or {}
        if n(incoming.get("availability"), 1) < 0.85: reasons.append(f"{incoming.get('name','Spilleren')} har usikker tilgjengelighet")
        if n(incoming.get("expected_minutes"), 90) < 65: reasons.append(f"{incoming.get('name','Spilleren')} har for lavt forventet minuttall")
    if gain < DO_THRESHOLD: reasons.append(f"Netto modellfordel {gain:.2f} er under beslutningsterskelen {DO_THRESHOLD:.2f}")
    return not reasons, reasons


def choose_safer_vice(lineup):
    captain = next((p for p in lineup if p.get("captain")), None)
    candidates = [p for p in lineup if not p.get("captain")]
    if not candidates: return
    def vice_score(p):
        return n(p.get("xp")) * (0.72 + 0.18*n(p.get("availability"),1) + 0.10*n(p.get("expected_minutes"),90)/90)
    best = max(candidates, key=vice_score)
    for p in lineup: p["vice"] = p is best
    if captain: captain["vice"] = False


def captain_comparison(lineup):
    rows = []
    for p in lineup:
        xp = n(p.get("xp")); mins = n(p.get("expected_minutes"), 90); avail = n(p.get("availability"), 1)
        low, high = n(p.get("xp_low"), xp), n(p.get("xp_high"), xp)
        ceiling = max(xp, high)
        score = xp*0.70 + ceiling*0.20 + (mins/90)*0.06 + avail*0.04
        rows.append({"id":p.get("id"),"name":p.get("name"),"team":p.get("team"),"xp":round(xp,2),"ceiling":round(ceiling,2),"expected_minutes":round(mins,0),"availability":round(avail,2),"score":round(score,3),"captain":bool(p.get("captain")),"vice":bool(p.get("vice"))})
    return sorted(rows, key=lambda x:x["score"], reverse=True)[:5]


def explain_decision(data, approved, blockers):
    cmp = data.get("comparison") or {}; changes = cmp.get("changes") or []
    opt = data.get("optimizer") or {}; gain = n(opt.get("weighted_gain"))
    best = (data.get("candidates") or [{}])[0]
    short, horizon = n(best.get("short_gain")), n(best.get("horizon_gain"))
    reasons = []
    if changes:
        names = ", ".join(f"{(c.get('out') or {}).get('name','?')} → {(c.get('in') or {}).get('name','?')}" for c in changes)
        reasons.append(f"Første trekk modellen vurderer er {names}.")
    reasons.append(f"Estimert gevinst: {short:+.2f} xP neste 3 GW og {horizon:+.2f} xP over planhorisonten.")
    reasons.append(f"Gratisbytte-fleksibilitet verdsettes til {FT_FLEX_VALUE:.2f} xP; robust BYTT-terskel er {DO_THRESHOLD:.2f}.")
    if blockers: reasons.extend(blockers[:2])
    else: reasons.append("Ingen harde minutt- eller tilgjengelighetsblokker stopper trekket.")
    distance = round(DO_THRESHOLD - gain, 2)
    trigger = "Anbefalingen er robust nok nå." if approved else f"Trenger omtrent {max(0,distance):.2f} mer netto modellfordel, eller at en blokkering forsvinner, før BYTT godkjennes."
    return {"decision":"BYTT" if approved else "BANK","why":reasons[:5],"weighted_gain":round(gain,2),"threshold":DO_THRESHOLD,"distance_to_switch":max(0,distance),"switch_trigger":trigger,"horizon_3gw":round(short,2),"horizon_plan":round(horizon,2)}


def main():
    data = json.loads(PATH.read_text(encoding="utf-8"))
    candidates = data.get("candidates") or []
    for c in candidates:
        score,status,reasons = candidate_quality(c); c["edge"],c["status"] = score,status
        c["gate_misses"] = list(dict.fromkeys(reasons + list(c.get("gate_misses") or [])))[:3]
    candidates.sort(key=lambda c:(n(c.get("edge")),n(c.get("horizon_gain"))), reverse=True)
    strong=[c for c in candidates if c.get("status")!="SVAK"]; data["candidates"] = strong[:6] if strong else candidates[:4]
    data["bench"] = reorder_bench(data.get("bench") or [])
    for lineup in [data.get("lineup") or [], (data.get("comparison") or {}).get("current_xi") or [], (data.get("comparison") or {}).get("transfer_xi") or []]: choose_safer_vice(lineup)
    approved, blockers = hard_gate_first_move(data)
    comparison=data.get("comparison") or {}
    if comparison.get("changes"): comparison["status"]="GJØR DET" if approved else "BANK"
    data["comparison"]=comparison
    data["headline"]="GJØR BYTTET" if approved else "SPAR BYTTET"
    data.setdefault("recommendation",{})["transfers"] = comparison.get("changes") or [] if approved else []
    lineup = comparison.get("transfer_xi") if approved else comparison.get("current_xi")
    lineup = lineup or data.get("lineup") or []
    data["captain_comparison"] = captain_comparison(lineup)
    data["decision_explanation"] = explain_decision(data, approved, blockers)
    data["decision_layer"]={"version":"4.1-explainable","approved_first_move":approved,"threshold":DO_THRESHOLD,"blockers":blockers,"candidate_count":len(data.get("candidates") or []),"bench_ordering":"outfield by availability/minutes/xP; goalkeeper last","explainability":True,"captain_comparison":True}
    PATH.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8")
    print("Decision layer 4.1 applied", "APPROVE" if approved else "BANK")

if __name__ == "__main__": main()

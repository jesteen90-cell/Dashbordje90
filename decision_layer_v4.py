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
    """Penalize fragile incoming picks without double-counting ordinary xP risk."""
    availability = max(0.0, min(1.0, n(player.get("availability"), 1.0)))
    xmins = max(0.0, min(90.0, n(player.get("expected_minutes"), 90.0)))
    volatility = max(0.0, n(player.get("volatility"), 0.0))

    availability_penalty = max(0.0, 0.92 - availability) * 3.0
    minutes_penalty = max(0.0, 70.0 - xmins) / 70.0 * 0.85
    volatility_penalty = max(0.0, volatility - 1.05) * 0.30
    return availability_penalty + minutes_penalty + volatility_penalty


def candidate_quality(candidate):
    pair = (candidate.get("pairs") or [{}])[0]
    outgoing = pair.get("out") or {}
    incoming = pair.get("in") or {}

    horizon = n(candidate.get("horizon_gain"))
    short = n(candidate.get("short_gain"))
    raw_edge = horizon - FT_FLEX_VALUE

    # Only penalize *additional* fragility versus the player being sold.
    fragility_delta = max(0.0, risk_penalty(incoming) - risk_penalty(outgoing))

    # A small near-term bonus prevents a strong immediate fixture swing from being
    # buried by a merely decent six-GW hold, while horizon value remains primary.
    short_bonus = max(-0.25, min(0.35, short * 0.07))
    score = raw_edge - fragility_delta + short_bonus

    reasons = []
    if fragility_delta > 0.20:
        reasons.append("Innkommende spiller har mer usikre minutter/tilgjengelighet")
    if short < 0:
        reasons.append("Byttet taper forventede poeng de neste tre rundene")
    if horizon <= FT_FLEX_VALUE:
        reasons.append("Langsiktig gevinst dekker ikke verdien av å beholde fleksibilitet")
    if n(incoming.get("expected_minutes"), 90) < 65:
        reasons.append("For lavt forventet minuttgrunnlag")
    if n(incoming.get("availability"), 1) < 0.85:
        reasons.append("Tilgjengeligheten er for usikker")

    if score >= DO_THRESHOLD and not reasons:
        status = "GJØR DET"
    elif score >= CONSIDER_THRESHOLD:
        status = "VURDERES"
    else:
        status = "SVAK"

    return round(score, 2), status, reasons


def reorder_bench(bench):
    """Best outfield auto-sub first, goalkeeper last."""
    outfield = [p for p in bench if p.get("position") != "GK"]
    keepers = [p for p in bench if p.get("position") == "GK"]
    outfield.sort(
        key=lambda p: (
            n(p.get("availability"), 1.0),
            n(p.get("expected_minutes")),
            n(p.get("xp")),
        ),
        reverse=True,
    )
    keepers.sort(key=lambda p: n(p.get("xp")), reverse=True)
    return outfield + keepers


def hard_gate_first_move(data):
    """Do not promote a transfer unless the first move clears a robust threshold."""
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

    if gain < DO_THRESHOLD:
        reasons.append(f"Netto modellfordel {gain:.2f} er under beslutningsterskelen {DO_THRESHOLD:.2f}")
    return not reasons, reasons


def choose_safer_vice(lineup):
    captain = next((p for p in lineup if p.get("captain")), None)
    candidates = [p for p in lineup if not p.get("captain")]
    if not candidates:
        return

    def vice_score(p):
        availability = n(p.get("availability"), 1)
        mins = n(p.get("expected_minutes"), 90) / 90
        return n(p.get("xp")) * (0.72 + 0.18 * availability + 0.10 * mins)

    best = max(candidates, key=vice_score)
    for p in lineup:
        p["vice"] = p is best
    if captain:
        captain["vice"] = False


def main():
    data = json.loads(PATH.read_text(encoding="utf-8"))

    candidates = data.get("candidates") or []
    for candidate in candidates:
        score, status, reasons = candidate_quality(candidate)
        candidate["edge"] = score
        candidate["status"] = status
        existing = list(candidate.get("gate_misses") or [])
        candidate["gate_misses"] = list(dict.fromkeys(reasons + existing))[:3]

    # Prefer robust decision score; remove low-value clutter from the visible shortlist.
    candidates.sort(key=lambda c: (n(c.get("edge")), n(c.get("horizon_gain"))), reverse=True)
    strong = [c for c in candidates if c.get("status") != "SVAK"]
    data["candidates"] = (strong[:6] if strong else candidates[:4])

    data["bench"] = reorder_bench(data.get("bench") or [])
    choose_safer_vice(data.get("lineup") or [])
    choose_safer_vice((data.get("comparison") or {}).get("current_xi") or [])
    choose_safer_vice((data.get("comparison") or {}).get("transfer_xi") or [])

    approved, blockers = hard_gate_first_move(data)
    comparison = data.get("comparison") or {}
    if comparison.get("changes"):
        comparison["status"] = "GJØR DET" if approved else "BANK"
    data["comparison"] = comparison

    if approved:
        data["headline"] = "GJØR BYTTET"
        data.setdefault("recommendation", {})["transfers"] = comparison.get("changes") or []
    else:
        data["headline"] = "SPAR BYTTET"
        data.setdefault("recommendation", {})["transfers"] = []

    data["decision_layer"] = {
        "version": "4.0-risk-aware",
        "approved_first_move": approved,
        "threshold": DO_THRESHOLD,
        "blockers": blockers,
        "candidate_count": len(data.get("candidates") or []),
        "bench_ordering": "outfield by availability/minutes/xP; goalkeeper last",
    }

    PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Decision layer 4.0 applied", "APPROVE" if approved else "BANK")


if __name__ == "__main__":
    main()

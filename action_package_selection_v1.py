"""Select BANK, one transfer, or the optimiser package on one fair surface.

Every action starts from the same best legal XI. A hit is charged exactly once
in the decision score. The selected action also gets an exact XI for the UI.
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

P = Path("data.json")
d = json.loads(P.read_text())
candidates = d.get("candidates") or []


def n(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp(value, low=0.0, high=1.0):
    return max(low, min(high, value))


def signature(pairs):
    return "|".join(sorted(
        f"{int((pair.get('out') or {}).get('id') or 0)}>{int((pair.get('in') or {}).get('id') or 0)}"
        for pair in pairs or []
    ))


def package_label(pairs):
    return " + ".join(
        f"{(pair.get('out') or {}).get('name', '?')} → {(pair.get('in') or {}).get('name', '?')}"
        for pair in pairs or []
    )


def projection(player, gw):
    for fixture in player.get("fixture_outlook") or []:
        if int(fixture.get("gw") or 0) == gw:
            return n(fixture.get("xp"))
    return n(player.get("xp"))


def legal(players):
    counts = {pos: sum(p.get("position") == pos for p in players) for pos in ("GK", "DEF", "MID", "FWD")}
    return len(players) == 11 and counts["GK"] == 1 and counts["DEF"] >= 3 and counts["MID"] >= 2 and counts["FWD"] >= 1


def best_xi(squad, gw):
    legal_xis = (list(combo) for combo in itertools.combinations(squad, 11) if legal(combo))
    best = max(legal_xis, key=lambda xi: sum(projection(player, gw) for player in xi))
    ids = {int(player["id"]) for player in best}
    bench = [player for player in squad if int(player["id"]) not in ids]
    bench = sorted(
        [player for player in bench if player.get("position") != "GK"],
        key=lambda player: projection(player, gw), reverse=True,
    ) + [player for player in bench if player.get("position") == "GK"]
    return best, bench


def apply_pairs(squad, pairs):
    outgoing = {int((pair.get("out") or {}).get("id") or 0) for pair in pairs or []}
    incoming = [dict(pair.get("in") or {}) for pair in pairs or []]
    return [dict(player) for player in squad if int(player.get("id") or 0) not in outgoing] + incoming


def reliability(pairs):
    incoming = [pair.get("in") or {} for pair in pairs or []]
    availability = min((n(player.get("availability"), 1) for player in incoming), default=1)
    minutes = min((n(player.get("expected_minutes"), 90) for player in incoming), default=90)
    score = clamp((0.58 + 0.42 * availability) * (0.68 + 0.32 * clamp(minutes / 80)))
    return score, availability, minutes


def candidate_timing(pairs):
    target = signature(pairs)
    exact = next((c for c in candidates if signature(c.get("pairs")) == target), None)
    if exact:
        return n((exact.get("timing_value_shadow") or {}).get("information_value"), 0.5)
    component_values = []
    pair_signatures = set(target.split("|"))
    for candidate in candidates:
        if set(signature(candidate.get("pairs")).split("|")) & pair_signatures:
            component_values.append(n((candidate.get("timing_value_shadow") or {}).get("information_value"), 0.5))
    return max(component_values, default=0.5)


def action_metrics(current, proposed, hit, first_gw):
    current_scores, proposed_scores = [], []
    for gw in range(first_gw, first_gw + 3):
        current_xi, _ = best_xi(current, gw)
        proposed_xi, _ = best_xi(proposed, gw)
        current_scores.append(sum(projection(player, gw) for player in current_xi))
        proposed_scores.append(sum(projection(player, gw) for player in proposed_xi))
    raw_next = proposed_scores[0] - current_scores[0]
    raw_three = sum(proposed_scores) - sum(current_scores)
    return raw_next, raw_three, raw_three, raw_next - hit, raw_three - hit


def action_score(raw_next, raw_three, raw_plan, rel, hit, information=0.0):
    value = (0.22 * raw_next + 0.34 * raw_three + 0.18 * raw_plan) * (0.55 + 0.45 * rel)
    return round(value - 0.55 * information - hit, 3)


first_gw = int(d.get("gameweek") or d.get("gw") or 1)
ft = int((d.get("current_transfer_state") or {}).get("free_transfers_remaining", d.get("free_transfers_assumed") or 1))
bank = n((d.get("budget") or {}).get("bank"))
current = [dict(player) for player in ((d.get("current_squad") or {}).get("players") or [])]
choices = [{
    "kind": "bank", "label": "SPAR GRATISBYTTET", "signature": "BANK", "pairs": [],
    "transfers": 0, "hit": 0, "next_gw_gain_after_cost": 0.0,
    "three_gw_gain_after_cost": 0.0, "plan_gain_after_cost": 0.0,
    "reliability": 1.0, "score": 0.0, "bank_after": bank,
    "free_transfers_next_gw": min(5, ft + 1),
}]

selection = d.get("candidate_selection") or {}
candidate_rows = selection.get("rows") or []
if candidate_rows and len(current) == 15:
    item = candidate_rows[0]
    index = int(item["candidate_index"])
    candidate = candidates[index]
    pairs = candidate.get("pairs") or []
    hit = max(0, len(pairs) - ft) * 4
    proposed = apply_pairs(current, pairs)
    raw_next, raw_three, raw_plan, net_next, net_three = action_metrics(current, proposed, hit, first_gw)
    rel = n(item.get("reliability"))
    information = n((candidate.get("timing_value_shadow") or {}).get("information_value"), 0.5)
    choices.append({
        "kind": "single", "label": package_label(pairs), "signature": signature(pairs), "pairs": pairs,
        "candidate_index": index, "transfers": len(pairs), "hit": hit,
        "next_gw_gain_after_cost": round(net_next, 2), "three_gw_gain_after_cost": round(net_three, 2),
        "plan_gain_after_cost": round(raw_plan - hit, 2), "reliability": round(rel, 3),
        "information_penalty": round(0.55 * information, 3),
        "score": action_score(raw_next, raw_three, raw_plan, rel, hit, information),
        "bank_after": candidate.get("bank_after"),
        "free_transfers_next_gw": min(5, max(0, ft - len(pairs)) + 1),
    })

optimizer = ((d.get("optimizer") or {}).get("plan") or [{}])[0]
optimizer_pairs = (d.get("comparison") or {}).get("changes") or []
if optimizer.get("action") == "transfer" and optimizer_pairs and len(current) == 15:
    sig = signature(optimizer_pairs)
    if not any(choice["signature"] == sig for choice in choices):
        hit = max(0, len(optimizer_pairs) - ft) * 4
        proposed = apply_pairs(current, optimizer_pairs)
        raw_next, raw_three, raw_plan, net_next, net_three = action_metrics(current, proposed, hit, first_gw)
        rel, availability, minutes = reliability(optimizer_pairs)
        information = candidate_timing(optimizer_pairs)
        bank_after = bank + sum(
            n((pair.get("out") or {}).get("selling_price", (pair.get("out") or {}).get("price")))
            - n((pair.get("in") or {}).get("price")) for pair in optimizer_pairs
        )
        choices.append({
            "kind": "double" if len(optimizer_pairs) > 1 else "optimizer_single",
            "label": package_label(optimizer_pairs), "signature": sig, "pairs": optimizer_pairs,
            "transfers": len(optimizer_pairs), "hit": hit,
            "next_gw_gain_after_cost": round(net_next, 2), "three_gw_gain_after_cost": round(net_three, 2),
            "plan_gain_after_cost": round(raw_plan - hit, 2), "reliability": round(rel, 3),
            "availability_floor": round(availability, 3), "minutes_floor": round(minutes, 1),
            "information_penalty": round(0.55 * information, 3),
            "score": action_score(raw_next, raw_three, raw_plan, rel, hit, information),
            "bank_after": round(bank_after, 1),
            "free_transfers_next_gw": min(5, max(0, ft - len(optimizer_pairs)) + 1),
        })

ranked_choices = sorted(choices, key=lambda choice: choice["score"], reverse=True)
selected = ranked_choices[0]
proposed = apply_pairs(current, selected.get("pairs") or [])

if len(current) == 15 and len(proposed) == 15:
    xi, bench = best_xi(proposed, first_gw)
    for player in proposed:
        player["captain"] = False
        player["vice"] = False
    xi_ids = {int(player["id"]) for player in xi}
    captain_order = [
        int(player.get("id")) for player in d.get("captain_comparison") or []
        if int(player.get("id") or 0) in xi_ids
    ]
    captain_order += [
        int(player["id"]) for player in sorted(xi, key=lambda x: projection(x, first_gw), reverse=True)
        if int(player["id"]) not in captain_order
    ]
    captain_id, vice_id = captain_order[:2]
    for player in xi:
        player["captain"] = int(player["id"]) == captain_id
        player["vice"] = int(player["id"]) == vice_id
    position_order = {"FWD": 1, "MID": 2, "DEF": 3, "GK": 4}
    xi.sort(key=lambda player: (position_order.get(player.get("position"), 9), -projection(player, first_gw)))
    formation = "-".join(str(sum(player.get("position") == pos for player in xi)) for pos in ("DEF", "MID", "FWD"))
    selected_lineup = {
        "version": "1.1-selected-package-xi", "lineup": xi, "bench": bench, "formation": formation,
        "captain_id": captain_id, "vice_id": vice_id,
        "expected_team_score": round(sum(projection(player, first_gw) for player in xi), 2),
        "pairs": selected.get("pairs") or [], "action_kind": selected["kind"], "hit": selected["hit"],
    }
else:
    selected_lineup = {"version": "1.1-selected-package-xi", "error": "Could not reconstruct legal 15-player proposed squad"}

d["action_package_selection"] = {
    "version": "1.1-common-action-surface", "choices": ranked_choices, "selected": selected,
    "rule": "BANK, single and optimiser package use the same legal-XI baseline. Hits are charged exactly once.",
}
d["selected_package_lineup"] = selected_lineup
P.write_text(json.dumps(d, ensure_ascii=False, indent=2))
print("Action package selected", selected["kind"], selected["label"], "score", selected["score"], "hit", selected["hit"])

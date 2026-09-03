"""Expose the common BANK/single/package comparison to the dashboard."""
import json
from pathlib import Path

P = Path("data.json")
d = json.loads(P.read_text())
selection = d.get("action_package_selection") or {}
gate = d.get("final_transfer_gate") or {}
choices = selection.get("choices") or []
selected = selection.get("selected") or {}

rows = []
for rank, choice in enumerate(choices, 1):
    rows.append({
        "kind": choice.get("kind"), "rank": rank, "label": choice.get("label"),
        "selected": choice.get("signature") == selected.get("signature"),
        "score_vs_bank": choice.get("score"), "hit": choice.get("hit", 0),
        "next_gw_gain_after_cost": choice.get("next_gw_gain_after_cost"),
        "three_gw_gain_after_cost": choice.get("three_gw_gain_after_cost"),
        "plan_gain_after_cost": choice.get("plan_gain_after_cost"),
        "reliability": choice.get("reliability"), "bank_after": choice.get("bank_after"),
        "free_transfers_next_gw": choice.get("free_transfers_next_gw"),
    })

runner_up_gap = None
if len(rows) > 1:
    runner_up_gap = round(float(rows[0].get("score_vs_bank") or 0) - float(rows[1].get("score_vs_bank") or 0), 2)

d["final_transfer_duel"] = {
    "version": "2.2-common-action-surface", "affects_transfer_ranking": False,
    "production_approved": bool((d.get("decision_layer") or {}).get("approved_first_move")),
    "verdict": gate.get("verdict", "NO-GO"), "confidence": gate.get("confidence"),
    "selected_action_kind": selected.get("kind"), "selected_action_label": selected.get("label"),
    "rows": rows, "winner_vs_runner_up_gap": runner_up_gap,
    "warnings": gate.get("warnings") or [], "blockers": gate.get("blockers") or [],
    "explanation": "Sammenligner SPAR, beste enkeltbytte og optimalisererens pakke på samme kostnadsjusterte flate.",
    "rule": "Rangeringen velger ett forslag. Final Gate avgjør om det er trygt å gjennomføre nå.",
}
P.write_text(json.dumps(d, ensure_ascii=False, indent=2))
print("Final transfer duel", selected.get("label"), gate.get("verdict"))

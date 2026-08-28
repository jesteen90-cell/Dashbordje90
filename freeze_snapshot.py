from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

DATA = Path("data.json")
ROOT = Path("snapshots")
INDEX = ROOT / "index.json"


def main():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    gw = int(data["gw"])
    deadline = datetime.fromisoformat(data["deadline_time"].replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)

    ROOT.mkdir(exist_ok=True)
    snap = ROOT / f"gw{gw:02d}.json"

    # A frozen snapshot is strictly pre-deadline and write-once.
    if now >= deadline:
        print(f"GW{gw}: deadline passed; no frozen snapshot written")
        return
    if snap.exists():
        print(f"GW{gw}: frozen snapshot already exists; keeping original")
        return

    payload = {
        "snapshot_version": "1.0",
        "frozen_at": now.isoformat().replace("+00:00", "Z"),
        "gw": gw,
        "deadline_time": data.get("deadline_time"),
        "model_version": data.get("model_version"),
        "decision_layer": data.get("decision_layer"),
        "headline": data.get("headline"),
        "decision_explanation": data.get("decision_explanation"),
        "recommendation": data.get("recommendation"),
        "comparison": data.get("comparison"),
        "lineup": data.get("lineup"),
        "bench": data.get("bench"),
        "captain_comparison": data.get("captain_comparison"),
        "candidates": data.get("candidates"),
        "future": data.get("future"),
        "optimizer": data.get("optimizer"),
        "source_snapshot_gw": data.get("source_snapshot_gw"),
        "free_transfers_assumed": data.get("free_transfers_assumed"),
        "generated_at": data.get("generated_at"),
    }
    snap.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    index = []
    if INDEX.exists():
        try:
            index = json.loads(INDEX.read_text(encoding="utf-8"))
        except Exception:
            index = []
    index = [x for x in index if int(x.get("gw", -1)) != gw]
    index.append({
        "gw": gw,
        "file": snap.as_posix(),
        "frozen_at": payload["frozen_at"],
        "deadline_time": payload["deadline_time"],
        "model_version": payload["model_version"],
        "decision_layer_version": (payload.get("decision_layer") or {}).get("version"),
        "decision": (payload.get("decision_explanation") or {}).get("decision"),
        "headline": payload.get("headline"),
    })
    index.sort(key=lambda x: int(x["gw"]))
    INDEX.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Frozen pre-deadline snapshot written: {snap}")


if __name__ == "__main__":
    main()

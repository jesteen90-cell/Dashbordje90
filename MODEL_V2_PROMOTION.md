# Model v2 promotion checklist

The live branch must not receive experimental overlays merely because they are newer.

## Proven core
- Calibrated xP must beat baseline MAE on untouched holdout.
- Ranking quality and top-5 selection must not regress.
- Multi-GW transfer strategy must pass its holdout gate.
- Predictive intervals must be valid.

## Experimental overlays
- Recent six-match xGI overlay stays OFF unless `recent_form_ab_status.json` exists and `promote=true`.
- Upside captain overlay stays OFF unless its holdout test promotes it.
- Any new team-strength/form feature needs an explicit historical A/B test before promotion.

## Release rule
Promote the strongest proven configuration, not necessarily the newest configuration. If an experimental overlay fails or has no valid result, production falls back to the last proven core automatically.

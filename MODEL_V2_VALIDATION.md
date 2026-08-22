# Model v2 validation gates

The model does not replace live v1 merely because it is more complicated.

## Leakage rule
Every prediction for GW N must be generated exclusively from information that existed before the GW N deadline. No end-of-season totals, later starts, later injury information, or future fixture results may enter features.

## Baselines
V2 must be compared with: (1) current v1, (2) FPL ep_next when archived pre-deadline, (3) season-to-date points/minute with a minutes projection, and (4) a simple recent-form baseline.

## Primary metrics
- MAE on actual FPL points for players projected for >=45 minutes.
- Rank correlation: important because FPL is a selection problem.
- Top-decile precision / realised score: do highly ranked players actually outperform?
- Captain decision: actual points from the model's highest projected captain vs baselines.
- Calibration by xP bucket and expected-minutes bucket.

## Promotion gates
V2 can become live only when:
1. no temporal leakage is found;
2. MAE beats v1 on held-out/walk-forward data, or is statistically tied while materially improving decision metrics;
3. captaincy is not materially worse than v1;
4. gains are not caused by one position or a handful of outliers;
5. blank and double gameweeks, unavailable players, autosub constraints, club limits and price constraints have dedicated tests;
6. the dashboard can expose component xP so unexpected projections can be audited.

## Model architecture target
Expected points = appearance + goals + assists + clean sheets + saves + defensive contributions + bonus - cards - goals conceded - penalty misses/own goals where estimable.

Minutes are upstream of every event component. Team attacking/defensive strength is fixture-specific. Player rates use shrinkage toward positional/role priors when samples are small. Defensive-contribution points should use a threshold probability rather than a linear average. Transfer planning optimises cumulative squad points and includes the opportunity value of retaining a free transfer.

## Accuracy log
Every production deadline should archive the prediction snapshot. After the GW is final, append actual scores and publish v1/v2 errors. This creates a live out-of-sample track record rather than relying only on historical backtests.

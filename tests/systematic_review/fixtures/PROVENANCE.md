# Test fixture provenance (real data only)

| Fixture | What it is | How it was made |
|---|---|---|
| `bcg_colditz1994.csv` | The 13 BCG vaccine trials meta-analysed by Colditz et al. 1994 (JAMA 271:698-702): TB cases and non-cases per arm, latitude, allocation | Exported from R `metafor::dat.bcg` (metafor 3.8.1) on 2026-10-16 |
| `bcg_metafor_reference.json` | metafor's results on those trials: log risk ratios and variances (`escalc`), DL, REML, REML with Hartung-Knapp (`test="knha"`), fixed effect, prediction intervals, I2, Q, and Egger's regression test (`regtest`, model lm), Mantel-Haenszel RR and OR (`rma.mh`), Peto OR (`rma.peto`), Q-profile CI for tau2 (`confint`), Cochrane subgroup test by allocation (separate REML fits, then fixed-effect Q between subgroup estimates), leave-one-out (`leave1out`) | `Rscript` with metafor 3.8.1 on 2026-10-16; the independent reference implementation the Python module is checked against |
| `bcg_extraction.jsonl`, `bcg_labels.json` | The same 13 BCG trials in the extraction-record layout (`outcome:tb:events_t` etc., allocation, latitude) and their author-year labels | Converted from `bcg_colditz1994.csv`; totals are events + non-events per arm |

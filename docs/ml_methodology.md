# ML and analytics methodology

## Data contract

Inputs are collected host observations with UTC timestamps. Utilization values outside 0–100 and non-finite values are rejected. Forecasting ignores invalid/missing observations and requires 12 timestamped observations. No labels are fabricated. Windows host data is real for that Windows host; it is not presented as Ubuntu data.

## Anomaly detection

`backend/app/intelligence.py` evaluates recent multivariate vectors using CPU, memory, disk utilization, load, and network receive/send rates. It requires 20 actual observations. When scikit-learn is installed it fits an `IsolationForest` with fixed `random_state=42`, 200 estimators, and automatic contamination. The fallback computes per-feature robust median absolute deviation scores and flags max standardized deviation at 3.5 or higher. Each finding stores the method, bounded score, dominant metric, same-window median baseline, observed value, timestamp and an explanation.

This detector is unsupervised. Its output means “unusual relative to this sample window,” not confirmed failure, attack, or root cause. It currently refits the window during collection and does not persist a serialized Isolation Forest model artifact or per-host model-health dashboard. Rule thresholds are separately configurable and remain distinct from statistical anomalies.

## Resource forecast

`backend/app/forecasting.py` estimates CPU, memory, and disk utilization up to 24 hours ahead. It fits a simple linear trend using only observations before each chronological validation point, and compares walk-forward mean absolute error with a last-value baseline. The model with lower measured MAE is selected; when the trend does not beat baseline, the last value is selected. Threshold crossing is an extrapolation from the latest slope and is omitted when the estimated slope is non-positive or the value is already at/above threshold.

Persisted records include model version, method, sample count, forecast horizon, observation/target timestamps, threshold, selected-model MAE, baseline MAE, evaluation count and explanation. The `confidence_score` is `100 - 5 * selected MAE`, clipped to 0–100; it is labeled as a data-quality score, not a calibrated probability or confidence interval. Evaluation results are workload-dependent. The app has no labeled failure target, so it does not claim to predict outages.

## Root-cause support

Rule-based hypotheses use contemporaneous host pressure, high-resource process snapshots, historical resource context, anomaly findings, resource forecasts, failed service state transitions, journal entries, typed dependency edges, related incidents and recent service actions. Each hypothesis includes a documented evidence-strength rubric, alternatives and diagnostic steps. Network deviation compares recent ingress against the same host's stored median where enough history exists. These are ranked diagnostic leads, not causal statements.

## Reproducibility and evaluation limits

The fallback paths and linear trend are deterministic for fixed data. Isolation Forest uses a fixed seed. Walk-forward metrics are computed from actual chronological observations; no synthetic accuracy scores are included. No representative Ubuntu workload, labeled failure corpus or production history is available in this workspace, so model quality at a target deployment has not been established. The current `evaluation_runs` table stores actual walk-forward MAE and baseline comparisons after sufficient observations; it does not store classification precision/recall because no labeled classification task is defined.

The authenticated [`ml/evaluation.ipynb`](../ml/evaluation.ipynb) notebook fetches stored observations from the running API and calls the same production inference modules. Run it on the target host after collecting history; its outputs are not committed so they cannot be mistaken for benchmark results.

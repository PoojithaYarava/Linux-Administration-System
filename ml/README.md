# Intelligence foundation

`backend/app/intelligence.py` is the executable anomaly detector used by the API. It loads historical rows from `system_metrics`, evaluates CPU, memory, disk, and load together with `IsolationForest` when scikit-learn is available, and falls back to a transparent CPU baseline otherwise.

The detector is intentionally small for Review 2. Future work can add model persistence, feature windows, evaluation metrics, and RCA context without changing the API shape.

from __future__ import annotations

from math import isfinite
from statistics import median
from typing import Any


def detect_anomalies(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Score stored host observations using Isolation Forest or robust MAD z-scores."""
    fields = ("cpu_usage", "memory_usage", "disk_usage", "load_average", "network_received_rate", "network_sent_rate")
    valid_rows = []
    vectors = []
    for row in rows:
        vector = []
        for field in fields:
            try:
                value = float(row.get(field, 0) or 0)
            except (TypeError, ValueError):
                value = 0.0
            vector.append(value if isfinite(value) else 0.0)
        valid_rows.append(row)
        vectors.append(vector)
    if len(valid_rows) < 20:
        return [{**row, "is_anomaly": False, "detection_method": "insufficient_data", "anomaly_score": None, "explanation": f"The multivariate detector needs at least 20 actual observations; {len(valid_rows)} are available."} for row in valid_rows]

    method = "robust_mad_multivariate"
    anomaly_flags: list[bool]
    scores: list[float]
    try:
        from sklearn.ensemble import IsolationForest
        model = IsolationForest(contamination="auto", random_state=42, n_estimators=200)
        predictions = model.fit_predict(vectors)
        scores = [-float(score) for score in model.decision_function(vectors)]
        anomaly_flags = [prediction == -1 for prediction in predictions]
        method = "isolation_forest"
    except ImportError:
        medians = [median(vector[index] for vector in vectors) for index in range(len(fields))]
        mads = [median(abs(vector[index] - medians[index]) for vector in vectors) for index in range(len(fields))]
        z_vectors = []
        for vector in vectors:
            z_vectors.append([
                min(1000.0, abs(vector[index] - medians[index]) * 0.6745 / mads[index]) if mads[index] else (0.0 if vector[index] == medians[index] else 1000.0)
                for index in range(len(fields))
            ])
        scores = [max(vector) for vector in z_vectors]
        anomaly_flags = [score >= 3.5 for score in scores]

    baselines = {field: median(vector[index] for vector in vectors) for index, field in enumerate(fields)}
    results = []
    for row, vector, is_anomaly, score in zip(valid_rows, vectors, anomaly_flags, scores):
        dominant = max(range(len(fields)), key=lambda index: abs(vector[index] - baselines[fields[index]]))
        field = fields[dominant]
        label = field.replace("_", " ")
        explanation = (
            f"{label} was {vector[dominant]:.2f}; the recent multivariate median was {baselines[field]:.2f}. "
            f"The {method.replace('_', ' ')} score was {score:.3f}. This is an unusual observation, not proof of a failure."
        )
        results.append({**row, "is_anomaly": is_anomaly, "detection_method": method, "anomaly_score": min(1000.0, float(score)), "dominant_metric": field, "baseline_value": baselines[field], "explanation": explanation})
    return results

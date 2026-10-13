from __future__ import annotations

from typing import Any


def detect_anomalies(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Run Isolation Forest when available; use a documented robust baseline otherwise."""
    if len(rows) < 10:
        return []
    try:
        from sklearn.ensemble import IsolationForest
        features = [[row["cpu_usage"], row["memory_usage"], row["disk_usage"], row["load_average"]] for row in rows]
        predictions = IsolationForest(contamination="auto", random_state=42).fit_predict(features)
        baseline = sum(row["cpu_usage"] for row in rows) / len(rows)
        return [{**row, "is_anomaly": prediction == -1, "explanation": f"CPU utilization was {row['cpu_usage']:.1f}% versus a recent baseline of {baseline:.1f}%; the model evaluated CPU, memory, disk, and load together."} for row, prediction in zip(rows, predictions)]
    except ImportError:
        values = [row["cpu_usage"] for row in rows]
        baseline = sum(values) / len(values)
        spread = max(1, (max(values) - min(values)) / 4)
        return [{**row, "is_anomaly": row["cpu_usage"] > baseline + 2 * spread, "explanation": f"CPU utilization was {row['cpu_usage']:.1f}% versus a recent baseline of {baseline:.1f}%; install scikit-learn to enable multivariate Isolation Forest detection."} for row in rows]

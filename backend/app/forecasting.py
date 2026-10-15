"""Leakage-aware resource trend forecasts using stored observations only."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isfinite
from statistics import fmean
from typing import Any

METRICS = {
    "cpu_usage": {"label": "CPU utilization", "threshold": 90.0, "unit": "%"},
    "memory_usage": {"label": "Memory utilization", "threshold": 90.0, "unit": "%"},
    "disk_usage": {"label": "Disk utilization", "threshold": 90.0, "unit": "%"},
}
MIN_TRAINING_SAMPLES = 12
MODEL_VERSION = "resource-trend-v1"


def _time_value(row: dict[str, Any]) -> float | None:
    try:
        value = datetime.fromisoformat(str(row["timestamp"]).replace("Z", "+00:00"))
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.timestamp()
    except (KeyError, TypeError, ValueError, OverflowError):
        return None


def _slope(points: list[tuple[float, float]]) -> tuple[float, float]:
    origin = points[0][0]
    xs = [(x - origin) / 3600 for x, _ in points]
    ys = [y for _, y in points]
    x_mean, y_mean = fmean(xs), fmean(ys)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys)) / denominator if denominator else 0.0
    return slope, y_mean - slope * x_mean


def _predict(points: list[tuple[float, float]], timestamp: float, method: str) -> float:
    if method == "last_value":
        return points[-1][1]
    slope, intercept = _slope(points)
    return slope * ((timestamp - points[0][0]) / 3600) + intercept


def _walk_forward_errors(points: list[tuple[float, float]]) -> tuple[float | None, float | None, int]:
    start = max(8, int(len(points) * 0.75))
    trend_errors: list[float] = []
    baseline_errors: list[float] = []
    for index in range(start, len(points)):
        history, actual = points[:index], points[index][1]
        trend_errors.append(abs(_predict(history, points[index][0], "linear_trend") - actual))
        baseline_errors.append(abs(_predict(history, points[index][0], "last_value") - actual))
    if not trend_errors:
        return None, None, 0
    return fmean(trend_errors), fmean(baseline_errors), len(trend_errors)


def forecast_resources(
    rows: list[dict[str, Any]], horizon_hours: float = 1.0
) -> list[dict[str, Any]]:
    """Forecast a short-horizon capacity trend and compare it with a naive baseline.

    The held-out evaluation is chronological: every prediction is fitted only on
    observations preceding its target. Confidence is a data-quality score derived
    from measured walk-forward error, not a probability of system failure.
    """
    if not isfinite(horizon_hours) or not 0 < horizon_hours <= 24:
        raise ValueError("horizon_hours must be greater than 0 and at most 24")
    forecasts = []
    for field, metadata in METRICS.items():
        points = []
        for row in rows:
            timestamp = _time_value(row)
            try:
                value = float(row[field])
            except (KeyError, TypeError, ValueError):
                continue
            if timestamp is not None and isfinite(value) and 0 <= value <= 100:
                points.append((timestamp, value))
        points.sort(key=lambda point: point[0])
        if len(points) < MIN_TRAINING_SAMPLES:
            forecasts.append({
                "metric": field, "label": metadata["label"], "status": "insufficient_data",
                "sample_count": len(points), "minimum_samples": MIN_TRAINING_SAMPLES,
                "explanation": f"At least {MIN_TRAINING_SAMPLES} valid timestamped observations are required; {len(points)} are available.",
            })
            continue

        trend_mae, baseline_mae, evaluation_count = _walk_forward_errors(points)
        method = "linear_trend" if trend_mae is not None and baseline_mae is not None and trend_mae <= baseline_mae else "last_value"
        observed_at, latest_value = points[-1]
        target_time = observed_at + horizon_hours * 3600
        raw_forecast = _predict(points, target_time, method)
        predicted_value = max(0.0, min(100.0, raw_forecast))
        slope_per_hour, _ = _slope(points[-min(48, len(points)):])
        threshold = float(metadata["threshold"])
        crossing_hours = (threshold - latest_value) / slope_per_hour if slope_per_hour > 0 and latest_value < threshold else None
        error = trend_mae if method == "linear_trend" else baseline_mae
        confidence = max(0.0, min(100.0, 100 - (error or 0.0) * 5)) if error is not None else None
        forecasts.append({
            "metric": field, "label": metadata["label"], "status": "forecasted",
            "method": method, "model_version": MODEL_VERSION,
            "observed_at": datetime.fromtimestamp(observed_at, timezone.utc).isoformat(),
            "forecast_at": datetime.fromtimestamp(target_time, timezone.utc).isoformat(),
            "horizon_hours": horizon_hours, "observed_value": latest_value,
            "predicted_value": predicted_value, "threshold": threshold,
            "estimated_hours_to_threshold": crossing_hours,
            "walk_forward_mae": error, "baseline_mae": baseline_mae,
            "evaluation_count": evaluation_count, "sample_count": len(points),
            "confidence_score": confidence,
            "explanation": (
                f"Using {len(points)} actual observations and a chronological walk-forward comparison, "
                f"the selected {method.replace('_', ' ')} estimates {predicted_value:.1f}{metadata['unit']} "
                f"in {horizon_hours:g} hour(s). Held-out MAE was {error:.2f} percentage points "
                f"versus {baseline_mae:.2f} for the last-value baseline. This is a resource trend estimate, "
                "not a prediction that a system failure will occur."
            ),
        })
    return forecasts

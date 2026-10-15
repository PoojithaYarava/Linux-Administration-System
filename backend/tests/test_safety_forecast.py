from datetime import datetime, timedelta, timezone

from app.forecasting import forecast_resources
from app.safety import WEIGHTS, action_fingerprint, assess_action


def test_forecast_requires_real_history_and_uses_walk_forward_metrics():
    short = forecast_resources([])
    assert all(item["status"] == "insufficient_data" for item in short)
    start = datetime.now(timezone.utc) - timedelta(hours=24)
    rows = [
        {"timestamp": (start + timedelta(hours=index)).isoformat(), "cpu_usage": 30 + index, "memory_usage": 40, "disk_usage": 55}
        for index in range(16)
    ]
    forecasts = forecast_resources(rows)
    cpu = next(item for item in forecasts if item["metric"] == "cpu_usage")
    assert cpu["sample_count"] == 16
    assert cpu["evaluation_count"] > 0
    assert cpu["baseline_mae"] is not None
    assert "not a prediction that a system failure" in cpu["explanation"]


def test_risk_weights_and_protected_service_policy_are_explicit():
    assert sum(WEIGHTS.values()) == 1
    result = assess_action("stop", "ssh", "active", [], [], None)
    assert result["score"] <= 100
    assert result["policy"]["decision"] == "prohibited"
    assert result["unknowns"]
    assert action_fingerprint("restart", "ssh") != action_fingerprint("stop", "ssh")

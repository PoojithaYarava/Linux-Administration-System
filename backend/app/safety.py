"""Explainable impact, risk, policy, and recommendation helpers."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

WEIGHTS = {
    "service_criticality": 0.20,
    "affected_dependencies": 0.18,
    "current_service_health": 0.15,
    "active_alerts": 0.14,
    "resource_pressure": 0.10,
    "reversibility": 0.10,
    "recovery_readiness": 0.08,
    "evidence_quality": 0.05,
}


def _band(score: int) -> str:
    low = int(os.getenv("RISK_MEDIUM_MIN", "31"))
    high = int(os.getenv("RISK_HIGH_MIN", "61"))
    critical = int(os.getenv("RISK_CRITICAL_MIN", "81"))
    if score >= critical:
        return "CRITICAL"
    if score >= high:
        return "HIGH"
    if score >= low:
        return "MEDIUM"
    return "LOW"


def _criticality(service: str) -> tuple[str, float]:
    configured = {}
    for item in os.getenv("SERVICE_CRITICALITY", "ssh:critical,cron:medium,systemd-journald:high").split(","):
        name, separator, level = item.strip().partition(":")
        if separator:
            configured[name.strip()] = level.strip().lower()
    level = configured.get(service, "unknown")
    return level, {"low": 0.2, "medium": 0.5, "high": 0.8, "critical": 1.0, "unknown": 0.35}.get(level, 0.35)


def action_fingerprint(operation: str, target: str) -> str:
    canonical = json.dumps({"operation": operation, "target": target}, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def assess_action(
    operation: str,
    target: str,
    service_state: str | None,
    dependencies: list[dict[str, Any]],
    alerts: list[dict[str, Any]],
    metrics: dict[str, Any] | None,
) -> dict[str, Any]:
    criticality_name, criticality_value = _criticality(target)
    dependents = [
        edge for edge in dependencies
        if edge.get("relationship") in {"Requires", "BindsTo", "PartOf", "WantedBy"}
        and edge.get("target_service") == target
        and edge.get("source_service") != target
    ]
    active_alerts = [alert for alert in alerts if alert.get("status") == "open"]
    related_alerts = [alert for alert in active_alerts if target in {alert.get("source"), alert.get("component")}]
    service_health = 1.0 if service_state == "failed" else 0.6 if service_state == "inactive" else 0.2 if service_state == "active" else 0.5
    pressure_values = [float(metrics[key]) for key in ("cpu_usage", "memory_usage", "disk_usage") if metrics and metrics.get(key) is not None]
    pressure = max((min(1.0, max(0.0, value) / 100) for value in pressure_values), default=0.5)
    reversibility = 0.9 if operation == "stop" else 0.3 if operation == "start" else 0.45
    recovery_readiness = 0.35 if not service_state or service_state == "unknown" else 0.65
    evidence_quality = round((0.35 if service_state and service_state != "unknown" else 0) + (0.25 if dependencies else 0) + (0.25 if metrics else 0) + 0.15, 2)
    dependent_score = min(1.0, len(dependents) / 4)
    alert_score = min(1.0, len(related_alerts) / 3 if related_alerts else len(active_alerts) / 8)
    factors = {
        "service_criticality": {"weight": WEIGHTS["service_criticality"], "normalized_value": criticality_value, "basis": criticality_name},
        "affected_dependencies": {"weight": WEIGHTS["affected_dependencies"], "normalized_value": dependent_score, "count": len(dependents)},
        "current_service_health": {"weight": WEIGHTS["current_service_health"], "normalized_value": service_health, "basis": service_state or "unknown"},
        "active_alerts": {"weight": WEIGHTS["active_alerts"], "normalized_value": alert_score, "count": len(active_alerts)},
        "resource_pressure": {"weight": WEIGHTS["resource_pressure"], "normalized_value": pressure, "observations": {key: metrics.get(key) for key in ("cpu_usage", "memory_usage", "disk_usage")} if metrics else None},
        "reversibility": {"weight": WEIGHTS["reversibility"], "normalized_value": reversibility, "basis": operation},
        "recovery_readiness": {"weight": WEIGHTS["recovery_readiness"], "normalized_value": recovery_readiness, "basis": "service state known" if service_state else "unknown"},
        "evidence_quality": {"weight": WEIGHTS["evidence_quality"], "normalized_value": evidence_quality, "basis": "service state, dependency inventory, host metrics, and completed alert query coverage"},
    }
    contributions = {name: round(item["weight"] * item["normalized_value"] * 100, 2) for name, item in factors.items()}
    score = max(0, min(100, round(sum(contributions.values()))))
    protected = set(filter(None, (value.strip() for value in os.getenv("PROTECTED_SERVICES", "ssh,systemd-journald").split(","))))
    prohibited = operation == "stop" and target in protected
    missing = []
    if not dependencies:
        missing.append("Dependency inventory is unavailable or empty; affected services may be unknown.")
    if service_state is None:
        missing.append("Current service state could not be verified.")
    if criticality_name == "unknown":
        missing.append("Service criticality is not configured; the documented unknown default was used.")
    if evidence_quality < 0.99:
        missing.append(f"Evidence completeness is {evidence_quality:.0%}; service state, dependencies, or host metrics are unavailable.")
    return {
        "operation": operation, "target": target, "score": score, "band": _band(score),
        "formula": "round(sum(weight * normalized_factor * 100)); weights total 1.00",
        "factors": factors, "contributions": contributions,
        "affected_services": sorted({edge.get("source_service") for edge in dependents if edge.get("source_service")}),
        "unknowns": missing,
        "policy": {"decision": "prohibited" if prohibited else "approval_required", "reason": f"Stopping protected service '{target}' is prohibited by policy." if prohibited else "All service operations require a human approval bound to this operation and target."},
        "requires_second_approver": score >= int(os.getenv("TWO_PERSON_APPROVAL_SCORE", "61")),
    }


def recommendations_from_state(
    metrics: dict[str, Any] | None,
    forecasts: list[dict[str, Any]],
    anomalies: list[dict[str, Any]],
    services: list[dict[str, Any]],
    top_processes: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    recommendations = []
    for forecast in forecasts:
        hours = forecast.get("estimated_hours_to_threshold")
        if forecast.get("status") == "forecasted" and hours is not None and hours <= 24:
            recommendations.append({
                "key": f"forecast:{forecast['metric']}", "category": "capacity",
                "title": f"Review {forecast['label'].lower()} trend",
                "problem": f"A trend estimate suggests the configured {forecast['threshold']:.0f}% threshold may be reached in {hours:.1f} hours.",
                "evidence": [forecast.get("explanation", "Historical resource trend analysis.")],
                "proposed_action": "Inspect recent changes and plan capacity or workload adjustments.",
                "expected_benefit": "More time to investigate capacity pressure before the threshold is reached.",
                "potential_impact": "Read-only investigation; no automatic system action is taken.",
                "risk_score": 0, "risk_factors": {"read_only": 0, "basis": "investigation only; no system change requested"}, "requires_approval": False,
                "verification": "Review the next collected observations and recompute the forecast.",
                "do_not_follow_when": "The history is stale or the monitored workload has changed materially.",
            })
    for anomaly in anomalies:
        recommendations.append({
            "key": f"anomaly:{anomaly.get('id', anomaly.get('metric_id', 'unknown'))}",
            "category": "investigation", "title": "Investigate a detected metric anomaly",
            "problem": anomaly.get("explanation", "A metric differs from its recent baseline."),
            "evidence": [anomaly.get("explanation", "Stored metric anomaly.")],
            "proposed_action": "Inspect the process inventory, related service state, and relevant logs.",
            "expected_benefit": "Gather evidence before making an operational change.",
            "potential_impact": "Read-only investigation.", "risk_score": 0, "risk_factors": {"read_only": 0, "basis": "evidence review only"},
            "requires_approval": False, "verification": "Record whether the observation returns to baseline.",
            "do_not_follow_when": "The observation is stale or already resolved.",
        })
    for service in services:
        if service.get("active") == "failed":
            recommendations.append({
                "key": f"service:{service.get('name')}:failed", "category": "service_health",
                "title": f"Investigate failed service {service.get('name')}",
                "problem": f"systemd reports {service.get('name')} as failed.",
                "evidence": [f"Observed service state: {service.get('active')} ({service.get('status')})."],
                "proposed_action": "Review the service journal and dependency graph, then request an approved recovery action if appropriate.",
                "expected_benefit": "Identify the service failure context before recovery.",
                "potential_impact": "Inspection is read-only; service recovery may affect dependents.",
                "risk_score": 0, "risk_factors": {"basis": "service failure needs a fresh action-specific assessment"}, "requires_approval": True,
                "verification": "Check systemd active state and dependent service health after any approved action.",
                "do_not_follow_when": "The service is intentionally stopped or the failure has already been resolved.",
            })
    if metrics and metrics.get("cpu_usage", 0) >= 85 and top_processes:
        process = top_processes[0]
        recommendations.append({
            "key": f"process:{process.get('pid')}:cpu", "category": "resource_pressure",
            "title": f"Inspect CPU-intensive process {process.get('name')}",
            "problem": f"Current CPU is {metrics['cpu_usage']:.1f}% and the highest observed process is {process.get('name')} at {process.get('cpu_usage', 0):.1f}%.",
            "evidence": [f"Process PID {process.get('pid')} was observed at {process.get('cpu_usage', 0):.1f}% CPU."],
            "proposed_action": "Inspect the process owner, command, and recent logs; do not terminate it solely from this recommendation.",
            "expected_benefit": "Identify whether the workload is expected or needs operator attention.",
            "potential_impact": "Read-only investigation.", "risk_score": 0, "risk_factors": {"read_only": 0, "basis": "evidence review only"},
            "requires_approval": False, "verification": "Compare process and host CPU after investigation.",
            "do_not_follow_when": "The process is an expected short-lived workload.",
        })
    return recommendations

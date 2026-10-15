"""Evidence-ranked hypotheses. Correlation is explicitly not causal proof."""

from __future__ import annotations

from statistics import median
from typing import Any


def analyze_root_causes(
    metric: dict[str, Any] | None,
    processes: list[dict[str, Any]],
    services: list[dict[str, Any]],
    logs: list[dict[str, Any]],
    dependencies: list[dict[str, Any]],
    incidents: list[dict[str, Any]],
    actions: list[dict[str, Any]] | None = None,
    anomalies: list[dict[str, Any]] | None = None,
    predictions: list[dict[str, Any]] | None = None,
    history: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    actions, anomalies, predictions, history = actions or [], anomalies or [], predictions or [], history or []
    findings: list[dict[str, Any]] = []
    if metric:
        top_cpu = max(processes, key=lambda row: row.get("cpu_usage", 0), default=None)
        top_memory = max(processes, key=lambda row: row.get("memory_usage", 0), default=None)
        if metric.get("cpu_usage", 0) >= 80 and top_cpu and top_cpu.get("cpu_usage", 0) >= 20:
            value = float(top_cpu["cpu_usage"])
            related = [item for item in actions if item.get("target") == top_cpu.get("name")]
            anomaly_evidence = [item for item in anomalies if item.get("metric") == "cpu_usage"]
            forecast_evidence = [item for item in predictions if item.get("metric") == "cpu_usage" and item.get("estimated_hours_to_threshold") is not None]
            trend = next((row for row in reversed(history[:-1]) if row.get("timestamp") != metric.get("timestamp")), None)
            evidence = [f"Host CPU was {metric['cpu_usage']:.1f}% at {metric.get('timestamp')}.", f"The process was observed at {value:.1f}% CPU, PID {top_cpu.get('pid')}."]
            if trend:
                evidence.append(f"Previous stored host CPU was {float(trend.get('cpu_usage', 0)):.1f}% at {trend.get('timestamp')}.")
            evidence.extend(f"Stored CPU anomaly at {item.get('created_at')}: {item.get('explanation', '')}" for item in anomaly_evidence[:2])
            evidence.extend(f"Forecast computed at {item.get('created_at')} estimates {item.get('predicted_value')}% CPU." for item in forecast_evidence[:1])
            evidence.extend(f"Recent action {item.get('action_type')} on {item.get('target')} ended {item.get('state')} at {item.get('executed_at') or item.get('requested_at')}." for item in related[-2:])
            findings.append({
                "hypothesis": f"Process {top_cpu.get('name')} (PID {top_cpu.get('pid')}) may be contributing to elevated CPU utilization.",
                "component": str(top_cpu.get("name", "process")), "confidence": min(75, 40 + round(value / 4)),
                "confidence_definition": "Evidence strength rubric: one temporally aligned high-resource process is moderate evidence (40–75/100); it is not a probability and does not establish causation.",
                "evidence": evidence,
                "alternatives": ["Other processes may have contributed between samples.", "The workload may be expected for this host."],
                "diagnostics": ["Inspect the process owner and full command in the process view.", "Compare CPU history and related service logs before acting."],
                "related_incidents": [item["id"] for item in incidents if item.get("component") == top_cpu.get("name")],
                "observed_at": metric.get("timestamp"),
            })
        if metric.get("memory_usage", 0) >= 80 and top_memory and top_memory.get("memory_usage", 0) >= 15:
            value = float(top_memory["memory_usage"])
            related = [item for item in actions if item.get("target") == top_memory.get("name")]
            anomaly_evidence = [item for item in anomalies if item.get("metric") == "memory_usage"]
            forecast_evidence = [item for item in predictions if item.get("metric") == "memory_usage" and item.get("estimated_hours_to_threshold") is not None]
            evidence = [f"Host memory utilization was {metric['memory_usage']:.1f}% at {metric.get('timestamp')}.", f"The process was observed using {value:.1f}% of memory, PID {top_memory.get('pid')}."]
            evidence.extend(f"Stored memory anomaly at {item.get('created_at')}: {item.get('explanation', '')}" for item in anomaly_evidence[:2])
            evidence.extend(f"Forecast computed at {item.get('created_at')} estimates {item.get('predicted_value')}% memory use." for item in forecast_evidence[:1])
            evidence.extend(f"Recent action {item.get('action_type')} on {item.get('target')} ended {item.get('state')} at {item.get('executed_at') or item.get('requested_at')}." for item in related[-2:])
            findings.append({
                "hypothesis": f"Process {top_memory.get('name')} (PID {top_memory.get('pid')}) may be contributing to memory pressure.",
                "component": str(top_memory.get("name", "process")), "confidence": min(75, 40 + round(value)),
                "confidence_definition": "Evidence strength rubric: one temporally aligned high-resource process is moderate evidence (40–75/100); it is not a probability and does not establish causation.",
                "evidence": evidence,
                "alternatives": ["The host may be using memory for cache or expected workload.", "Other processes may explain the remaining utilization."],
                "diagnostics": ["Compare process memory snapshots over time.", "Inspect application logs and memory limits before making changes."],
                "related_incidents": [item["id"] for item in incidents if item.get("component") == top_memory.get("name")],
                "observed_at": metric.get("timestamp"),
            })
        if metric.get("disk_usage", 0) >= 85:
            evidence = [f"Host filesystem utilization was {metric['disk_usage']:.1f}% at {metric.get('timestamp')}."]
            evidence.extend(f"Stored disk anomaly at {item.get('created_at')}: {item.get('explanation', '')}" for item in anomalies if item.get("metric") == "disk_usage")
            disk_forecasts = [item for item in predictions if item.get("metric") == "disk_usage" and item.get("estimated_hours_to_threshold") is not None]
            evidence.extend(f"A stored resource forecast estimated threshold crossing in {item.get('estimated_hours_to_threshold'):.1f} hours." for item in disk_forecasts[:1])
            findings.append({
                "hypothesis": "Filesystem capacity pressure may be contributing to the reported disk issue; the file or process responsible is not identified by these observations.",
                "component": "filesystem", "confidence": 45, "confidence_definition": "Evidence strength rubric: an elevated host utilization measurement is a weak-to-moderate signal (45/100), not proof of the cause.",
                "evidence": evidence, "alternatives": ["A large but expected dataset may account for utilization.", "The monitored mount may not be the affected filesystem."],
                "diagnostics": ["Inspect per-mount free space and recent disk growth.", "Review application logs and approved storage locations before cleanup."],
                "related_incidents": [item["id"] for item in incidents if item.get("component") in {"filesystem", "disk"}], "observed_at": metric.get("timestamp"),
            })

        prior_rates = [float(row.get("network_received_rate", 0) or 0) for row in history[:-1] if row.get("network_received_rate") is not None]
        current_rate = float(metric.get("network_received_rate", 0) or 0)
        if len(prior_rates) >= 8 and current_rate > max(1_000_000, median(prior_rates) * 3):
            related_anomalies = [item for item in anomalies if item.get("metric") == "network_received_rate"]
            findings.append({
                "hypothesis": "Inbound network throughput is unusually high compared with the stored host baseline; the source and purpose are unknown.",
                "component": "network", "confidence": 45, "confidence_definition": "Evidence strength rubric: a large deviation from the same-host median is a weak-to-moderate lead (45/100), not attribution or proof of malicious traffic.",
                "evidence": [f"Inbound rate was {current_rate:.0f} bytes/s at {metric.get('timestamp')}.", f"Prior observation median was {median(prior_rates):.0f} bytes/s."] + [item.get("explanation", "Stored network anomaly.") for item in related_anomalies[:2]],
                "alternatives": ["A legitimate transfer or scheduled backup may explain the rate.", "Interface aggregation or measurement intervals may change the comparison."],
                "diagnostics": ["Review per-interface counters and expected transfer schedules.", "Inspect network and service logs before changing firewall or service state."],
                "related_incidents": [item["id"] for item in incidents if item.get("component") == "network"], "observed_at": metric.get("timestamp"),
            })

    failed = [service for service in services if service.get("active") == "failed"]
    for service in failed:
        name = service.get("name", "unknown")
        related_logs = [entry for entry in logs if name in str(entry.get("source", "")) or name in str(entry.get("unit", ""))]
        related_actions = [item for item in actions if item.get("target") == name]
        affected = sorted({
            edge.get("source_service") for edge in dependencies
            if edge.get("target_service") == name and edge.get("relationship") in {"Requires", "BindsTo"}
        } - {None})
        evidence = [f"systemd reported {name} as failed at {service.get('checked_at', 'the last service refresh')}."]
        if service.get("previous_active") and service.get("previous_active") != "failed":
            evidence.append(f"The previous stored service snapshot was {service['previous_active']}; this is an observed transition, not the initiating cause.")
        if related_logs:
            evidence.extend([f"Related journal entry at {row.get('timestamp')}: {str(row.get('message', ''))[:240]}" for row in related_logs[:3]])
        if affected:
            evidence.append(f"The dependency graph lists these requiring units: {', '.join(affected)}.")
        evidence.extend(f"Related service action {item.get('action_type')} by user {item.get('requested_by')} reached {item.get('state')} at {item.get('executed_at') or item.get('requested_at')}." for item in related_actions[-3:])
        findings.append({
            "hypothesis": f"Service {name} is in a failed state; the initiating cause is not confirmed.",
            "component": name, "confidence": 60 if related_logs else 35,
            "confidence_definition": "Evidence strength rubric: failed state alone is a weak initiating-cause hypothesis (35/100); related journal evidence raises confidence to moderate (60/100), not causal proof.",
            "evidence": evidence,
            "alternatives": ["The service may have been stopped intentionally.", "A dependency or host-level condition may have caused the state."],
            "diagnostics": [f"Inspect journal entries for {name}.", "Review Requires/BindsTo relationships and the service unit's recent state transitions."],
            "related_incidents": [item["id"] for item in incidents if item.get("component") == name],
            "affected_services": affected, "observed_at": service.get("checked_at"),
        })

    if not findings:
        findings.append({
            "hypothesis": "The available evidence does not identify a likely root cause.",
            "component": "host", "confidence": 0,
            "confidence_definition": "Zero means the current stored evidence did not meet any documented correlation rule; it is not evidence that the host is healthy.",
            "evidence": ["No current metric threshold, high-resource process, or failed systemd service matched the analysis rules."],
            "alternatives": ["The issue may be intermittent, outside the collected metrics, or not yet represented in stored data."],
            "diagnostics": ["Collect more history and inspect related service logs and dependencies."],
            "related_incidents": [], "observed_at": metric.get("timestamp") if metric else None,
        })
    return findings

"""SQLAlchemy ORM schema shared by the API and Alembic migrations."""

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Float, Integer, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class SystemMetric(Base):
    __tablename__ = "system_metrics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    cpu_usage: Mapped[float] = mapped_column(Float, nullable=False)
    memory_usage: Mapped[float] = mapped_column(Float, nullable=False)
    disk_usage: Mapped[float] = mapped_column(Float, nullable=False)
    network_received: Mapped[int] = mapped_column(BigInteger, nullable=False)
    network_sent: Mapped[int] = mapped_column(BigInteger, nullable=False)
    load_average: Mapped[float] = mapped_column(Float, nullable=False)
    memory_available: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    disk_total_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    disk_used_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    disk_read_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    disk_write_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    network_received_rate: Mapped[float] = mapped_column(Float, nullable=False, server_default="0")
    network_sent_rate: Mapped[float] = mapped_column(Float, nullable=False, server_default="0")
    interface_stats: Mapped[str] = mapped_column(Text, nullable=False, server_default="{}")
    process_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    availability_json: Mapped[str] = mapped_column(Text, nullable=False, server_default="{}")


class ProcessSnapshot(Base):
    __tablename__ = "processes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    pid: Mapped[int] = mapped_column(Integer, nullable=False)
    process_name: Mapped[str] = mapped_column(Text, nullable=False)
    cpu_usage: Mapped[float] = mapped_column(Float, nullable=False)
    memory_usage: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    username: Mapped[str | None] = mapped_column(Text)
    start_time: Mapped[str | None] = mapped_column(Text)
    command: Mapped[str | None] = mapped_column(Text)
    memory_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")


class Service(Base):
    __tablename__ = "services"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False)
    checked_at: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[str] = mapped_column(Text, nullable=False, server_default="unknown")
    load: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    unit_file_state: Mapped[str | None] = mapped_column(Text)


class SystemLog(Base):
    __tablename__ = "logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str | None] = mapped_column(Text)
    journal_cursor: Mapped[str | None] = mapped_column(Text)


Index("idx_logs_journal_cursor", SystemLog.journal_cursor, unique=True, postgresql_where=SystemLog.journal_cursor.is_not(None), sqlite_where=SystemLog.journal_cursor.is_not(None))


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[str] = mapped_column(Text, nullable=False)
    alert_type: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (Index("idx_alerts_status_timestamp", "status", "timestamp"),)


class Incident(Base):
    __tablename__ = "incidents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    component: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="open")
    linked_alert_id: Mapped[int | None] = mapped_column(ForeignKey("alerts.id"))
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    resolution_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    resolved_at: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (Index("idx_incidents_status_created", "status", "created_at"),)


class Action(Base):
    __tablename__ = "actions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    target: Mapped[str] = mapped_column(Text, nullable=False)
    requested_at: Mapped[str] = mapped_column(Text, nullable=False)
    executed_at: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str] = mapped_column(Text, nullable=False, server_default="PENDING_APPROVAL")
    impact_json: Mapped[str | None] = mapped_column(Text)
    risk_json: Mapped[str | None] = mapped_column(Text)
    requested_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[str | None] = mapped_column(Text)
    before_state: Mapped[str | None] = mapped_column(Text)
    fingerprint: Mapped[str | None] = mapped_column(Text)
    incident_id: Mapped[int | None] = mapped_column(ForeignKey("incidents.id"))
    __table_args__ = (Index("idx_actions_state_requested", "state", "requested_at"),)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    target: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[str] = mapped_column(Text, nullable=False)


class Session(Base):
    __tablename__ = "sessions"
    token_hash: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[str] = mapped_column(Text, nullable=False)


class ServiceDependency(Base):
    __tablename__ = "service_dependencies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_service: Mapped[str] = mapped_column(Text, nullable=False)
    target_service: Mapped[str] = mapped_column(Text, nullable=False)
    relationship: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    observed_at: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (UniqueConstraint("source_service", "target_service", "relationship"),)


class ServiceSnapshot(Base):
    __tablename__ = "service_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_name: Mapped[str] = mapped_column(Text, nullable=False)
    active: Mapped[str] = mapped_column(Text, nullable=False)
    sub_state: Mapped[str | None] = mapped_column(Text)
    load_state: Mapped[str | None] = mapped_column(Text)
    enabled_state: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    observed_at: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (UniqueConstraint("service_name", "observed_at"), Index("idx_service_snapshots_name_observed", "service_name", "observed_at"))


class AnomalyFinding(Base):
    __tablename__ = "anomaly_findings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    metric_id: Mapped[int] = mapped_column(ForeignKey("system_metrics.id", ondelete="CASCADE"), nullable=False)
    metric: Mapped[str] = mapped_column(Text, nullable=False)
    component: Mapped[str] = mapped_column(Text, nullable=False)
    observed_value: Mapped[float] = mapped_column(Float, nullable=False)
    baseline: Mapped[float | None] = mapped_column(Float)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    detection_method: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float | None] = mapped_column(Float)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="open")
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    resolved_at: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (UniqueConstraint("metric_id", "detection_method"), Index("idx_anomalies_status_created", "status", "created_at"))


class Prediction(Base):
    __tablename__ = "predictions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    metric: Mapped[str] = mapped_column(Text, nullable=False)
    method: Mapped[str] = mapped_column(Text, nullable=False)
    model_version: Mapped[str] = mapped_column(Text, nullable=False)
    observed_at: Mapped[str] = mapped_column(Text, nullable=False)
    forecast_at: Mapped[str] = mapped_column(Text, nullable=False)
    horizon_hours: Mapped[float] = mapped_column(Float, nullable=False)
    observed_value: Mapped[float] = mapped_column(Float, nullable=False)
    predicted_value: Mapped[float] = mapped_column(Float, nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_hours_to_threshold: Mapped[float | None] = mapped_column(Float)
    walk_forward_mae: Mapped[float | None] = mapped_column(Float)
    baseline_mae: Mapped[float | None] = mapped_column(Float)
    evaluation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (Index("idx_predictions_metric_created", "metric", "created_at"),)


class ModelVersion(Base):
    __tablename__ = "model_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(Text, nullable=False)
    method: Mapped[str] = mapped_column(Text, nullable=False)
    training_window_start: Mapped[str | None] = mapped_column(Text)
    training_window_end: Mapped[str | None] = mapped_column(Text)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    parameters_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (UniqueConstraint("name", "version"),)


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    model_version: Mapped[str] = mapped_column(Text, nullable=False)
    evaluation_method: Mapped[str] = mapped_column(Text, nullable=False)
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class RootCauseFinding(Base):
    __tablename__ = "root_cause_findings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int | None] = mapped_column(ForeignKey("incidents.id"))
    component: Mapped[str] = mapped_column(Text, nullable=False)
    hypothesis: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence_definition: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False)
    alternatives_json: Mapped[str] = mapped_column(Text, nullable=False)
    diagnostics_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class ImpactAssessment(Base):
    __tablename__ = "impact_assessments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action_id: Mapped[int | None] = mapped_column(ForeignKey("actions.id"))
    incident_id: Mapped[int | None] = mapped_column(ForeignKey("incidents.id"))
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    operation: Mapped[str] = mapped_column(Text, nullable=False)
    target: Mapped[str] = mapped_column(Text, nullable=False)
    report_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (Index("idx_impact_target_created", "target", "created_at"),)


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action_id: Mapped[int | None] = mapped_column(ForeignKey("actions.id"))
    incident_id: Mapped[int | None] = mapped_column(ForeignKey("incidents.id"))
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    score: Mapped[int] = mapped_column(Integer, CheckConstraint("score BETWEEN 0 AND 100"), nullable=False)
    band: Mapped[str] = mapped_column(Text, nullable=False)
    factors_json: Mapped[str] = mapped_column(Text, nullable=False)
    policy_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (Index("idx_risk_score_created", "score", "created_at"),)


class Recommendation(Base):
    __tablename__ = "recommendations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recommendation_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    problem: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_action: Mapped[str] = mapped_column(Text, nullable=False)
    expected_benefit: Mapped[str] = mapped_column(Text, nullable=False)
    potential_impact: Mapped[str] = mapped_column(Text, nullable=False)
    risk_score: Mapped[int | None] = mapped_column(Integer)
    risk_factors_json: Mapped[str] = mapped_column(Text, nullable=False, server_default="{}")
    requires_approval: Mapped[int] = mapped_column(Integer, nullable=False)
    verification: Mapped[str] = mapped_column(Text, nullable=False)
    do_not_follow_when: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    action_id: Mapped[int] = mapped_column(ForeignKey("actions.id"), nullable=False)
    approver_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    approved_at: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[str] = mapped_column(Text, nullable=False)


class IncidentAction(Base):
    __tablename__ = "incident_actions"
    incident_id: Mapped[int] = mapped_column(ForeignKey("incidents.id"), primary_key=True)
    action_id: Mapped[int] = mapped_column(ForeignKey("actions.id"), primary_key=True)


class CollectorState(Base):
    __tablename__ = "collector_state"
    id: Mapped[int] = mapped_column(Integer, CheckConstraint("id=1"), primary_key=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    last_attempt_at: Mapped[str | None] = mapped_column(Text)
    last_success_at: Mapped[str | None] = mapped_column(Text)
    last_error: Mapped[str | None] = mapped_column(Text)
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)


class AppConfig(Base):
    __tablename__ = "app_config"
    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

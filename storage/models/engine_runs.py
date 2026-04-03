"""Engine run storage: runs, M1 results, M2 requests, M3 plan versions/stops/items.

Includes traceability fields for audit, debugging, and rollout comparison.
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from storage.models.base import Base, IdMixin, TimestampMixin


class EngineRun(Base, IdMixin, TimestampMixin):
    """Record of a single engine execution."""

    __tablename__ = "engine_runs"

    engine_type: Mapped[str] = mapped_column(
        String(10), nullable=False, comment="m1, m2, or m3"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="running",
        comment="running, completed, failed"
    )
    planning_start_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Day 1 of the 48-hour planning horizon for this execution",
    )
    input_snapshot_ids: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True,
        comment="JSON map of snapshot type -> snapshot id used as input"
    )

    # ── Traceability fields ──────────────────────────────────────────
    engine_mode: Mapped[Optional[str]] = mapped_column(
        String(10), nullable=True, comment="stub or real"
    )
    engine_impl: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment="Implementation label: stub, m2_xgboost_v1, m3_ortools_v1, etc."
    )
    engine_version: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, comment="Model/build version string"
    )
    engine_trace: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True,
        comment="JSON metadata about feature generation / solver execution"
    )

    __table_args__ = (
        Index("ix_engine_run_type", "engine_type"),
        Index("ix_engine_run_status", "status"),
        Index("ix_engine_run_started", "started_at"),
        Index("ix_engine_run_planning_start", "planning_start_date"),
    )


class M1Result(Base, IdMixin, TimestampMixin):
    """M1 priority scoring result per manifest line."""

    __tablename__ = "m1_results"

    engine_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("engine_runs.id"), nullable=False
    )
    manifest_line_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("manifest_lines.id"), nullable=False
    )
    sku_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skus.id"), nullable=False
    )
    priority_score: Mapped[float] = mapped_column(Float, nullable=False)
    priority_band: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="critical, high, medium, low"
    )
    reefer_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # ── Traceability fields ──────────────────────────────────────────
    score_breakdown: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="Human-readable score component breakdown"
    )
    raw_features: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="JSON snapshot of derived M1 features used at run time"
    )

    sku: Mapped["SKU"] = relationship("SKU")
    manifest_line: Mapped["ManifestLine"] = relationship("ManifestLine")

    __table_args__ = (
        Index("ix_m1_result_run", "engine_run_id"),
        Index("ix_m1_result_sku", "sku_id"),
        Index("ix_m1_result_band", "priority_band"),
    )


class M2Request(Base, IdMixin, TimestampMixin):
    """M2 generated DC replenishment request."""

    __tablename__ = "m2_requests"

    engine_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("engine_runs.id"), nullable=False
    )
    dc_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dcs.id"), nullable=False
    )
    sku_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skus.id"), nullable=False
    )
    requested_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    urgency: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="critical, high, medium, low"
    )
    required_by: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # ── Traceability fields ──────────────────────────────────────────
    urgency_score: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Raw urgency score from real M2 model (0-100)"
    )
    shortage_probability: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Probability of shortage from classifier (0-1)"
    )
    hours_until_shortage: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Predicted hours until shortage (0-48)"
    )
    effective_stock_at_run: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Effective stock at time of inference"
    )
    projected_48h_sales: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Projected 48h sales used in inference"
    )
    safety_stock: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Safety stock level used in inference"
    )
    raw_features: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="JSON snapshot of all M2 features used at run time"
    )

    dc: Mapped["DC"] = relationship("DC")
    sku: Mapped["SKU"] = relationship("SKU")

    __table_args__ = (
        Index("ix_m2_req_run", "engine_run_id"),
        Index("ix_m2_req_dc", "dc_id"),
        Index("ix_m2_req_sku", "sku_id"),
        Index("ix_m2_req_urgency", "urgency"),
    )


class M3PlanVersion(Base, IdMixin, TimestampMixin):
    """M3 candidate dispatch plan version."""

    __tablename__ = "m3_plan_versions"

    engine_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("engine_runs.id"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    plan_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft",
        comment="draft, approved, rejected"
    )
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_best: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    approved_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # ── Traceability fields ──────────────────────────────────────────
    plan_name: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True, comment="Human-readable plan variant name"
    )
    generation_strategy: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True,
        comment="urgency_max, balanced, cost_aware"
    )
    objective_value: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, comment="Solver objective function value"
    )
    solver_trace: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True, comment="JSON summary of solver execution"
    )

    engine_run: Mapped["EngineRun"] = relationship("EngineRun")
    runs = relationship("M3PlanRun", back_populates="plan_version", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_m3_plan_run", "engine_run_id"),
        Index("ix_m3_plan_status", "plan_status"),
        Index("ix_m3_plan_is_best", "is_best"),
    )

    @property
    def stops(self):
        flattened = []
        for run in sorted(self.runs, key=lambda current: (current.dispatch_day, current.id or 0)):
            flattened.extend(sorted(run.stops, key=lambda current: (current.stop_sequence, current.id or 0)))
        return flattened


class M3PlanRun(Base, IdMixin, TimestampMixin):
    """One lorry trip assigned to a specific dispatch day within a plan version."""

    __tablename__ = "m3_plan_runs"

    plan_version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("m3_plan_versions.id"), nullable=False
    )
    lorry_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("lorries.id"), nullable=False
    )
    dispatch_day: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="1 or 2 within the 48-hour planning horizon"
    )

    plan_version = relationship("M3PlanVersion", back_populates="runs")
    lorry: Mapped["Lorry"] = relationship("Lorry")
    stops = relationship("M3PlanStop", back_populates="run", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_m3_run_plan", "plan_version_id"),
        Index("ix_m3_run_lorry", "lorry_id"),
        Index("ix_m3_run_day", "dispatch_day"),
    )


class M3PlanStop(Base, IdMixin, TimestampMixin):
    """A stop in an M3 dispatch plan (lorry visiting a DC)."""

    __tablename__ = "m3_plan_stops"

    plan_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("m3_plan_runs.id"), nullable=False
    )
    stop_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    dc_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dcs.id"), nullable=False
    )
    arrival_time_est: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    run = relationship("M3PlanRun", back_populates="stops")
    dc: Mapped["DC"] = relationship("DC")
    items = relationship("M3PlanItem", back_populates="stop", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_m3_stop_run", "plan_run_id"),
        Index("ix_m3_stop_dc", "dc_id"),
    )

    @property
    def lorry_id(self):
        return self.run.lorry_id if self.run else None

    @property
    def dispatch_day(self):
        return self.run.dispatch_day if self.run else None


class M3PlanItem(Base, IdMixin, TimestampMixin):
    """SKU quantity loaded at a specific stop."""

    __tablename__ = "m3_plan_items"

    plan_stop_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("m3_plan_stops.id"), nullable=False
    )
    sku_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skus.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    stop = relationship("M3PlanStop", back_populates="items")
    sku: Mapped["SKU"] = relationship("SKU")

    __table_args__ = (
        Index("ix_m3_item_stop", "plan_stop_id"),
        Index("ix_m3_item_sku", "sku_id"),
    )

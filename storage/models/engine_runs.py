"""Engine run storage: runs, M1 results, M2 requests, M3 plan versions/stops/items."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
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
    input_snapshot_ids: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True,
        comment="JSON map of snapshot type -> snapshot id used as input"
    )

    __table_args__ = (
        Index("ix_engine_run_type", "engine_type"),
        Index("ix_engine_run_status", "status"),
        Index("ix_engine_run_started", "started_at"),
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

    stops = relationship("M3PlanStop", back_populates="plan_version", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_m3_plan_run", "engine_run_id"),
        Index("ix_m3_plan_status", "plan_status"),
        Index("ix_m3_plan_is_best", "is_best"),
    )


class M3PlanStop(Base, IdMixin, TimestampMixin):
    """A stop in an M3 dispatch plan (lorry visiting a DC)."""

    __tablename__ = "m3_plan_stops"

    plan_version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("m3_plan_versions.id"), nullable=False
    )
    lorry_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("lorries.id"), nullable=False
    )
    stop_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    dc_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dcs.id"), nullable=False
    )
    arrival_time_est: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    plan_version = relationship("M3PlanVersion", back_populates="stops")
    items = relationship("M3PlanItem", back_populates="stop", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_m3_stop_plan", "plan_version_id"),
        Index("ix_m3_stop_lorry", "lorry_id"),
        Index("ix_m3_stop_dc", "dc_id"),
    )


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

    __table_args__ = (
        Index("ix_m3_item_stop", "plan_stop_id"),
        Index("ix_m3_item_sku", "sku_id"),
    )

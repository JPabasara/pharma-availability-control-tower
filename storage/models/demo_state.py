"""Demo-state storage: reservations, transfers, arrival events, stock projections."""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column

from storage.models.base import Base, IdMixin, TimestampMixin


class DemoReservation(Base, IdMixin, TimestampMixin):
    """Warehouse stock reservation created on plan approval."""

    __tablename__ = "demo_reservations"

    plan_version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("m3_plan_versions.id"), nullable=False
    )
    plan_stop_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("m3_plan_stops.id"), nullable=True
    )
    sku_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skus.id"), nullable=False
    )
    quantity_reserved: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active",
        comment="active or released"
    )

    __table_args__ = (
        Index("ix_demo_res_plan", "plan_version_id"),
        Index("ix_demo_res_stop", "plan_stop_id"),
        Index("ix_demo_res_sku", "sku_id"),
        Index("ix_demo_res_status", "status"),
    )


class DemoTransfer(Base, IdMixin, TimestampMixin):
    """Simulated warehouse → DC transfer for demo stock movement."""

    __tablename__ = "demo_transfers"

    plan_version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("m3_plan_versions.id"), nullable=False
    )
    plan_stop_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("m3_plan_stops.id"), nullable=True
    )
    lorry_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("lorries.id"), nullable=False
    )
    dc_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dcs.id"), nullable=False
    )
    sku_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skus.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending",
        comment="pending, in_transit, arrived"
    )
    dispatched_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    arrived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_demo_xfer_plan", "plan_version_id"),
        Index("ix_demo_xfer_stop", "plan_stop_id"),
        Index("ix_demo_xfer_lorry", "lorry_id"),
        Index("ix_demo_xfer_dc", "dc_id"),
        Index("ix_demo_xfer_sku", "sku_id"),
        Index("ix_demo_xfer_status", "status"),
    )


class DemoArrivalEvent(Base, IdMixin, TimestampMixin):
    """Record of a simulated arrival event (vessel or lorry)."""

    __tablename__ = "demo_arrival_events"

    event_type: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="vessel_arrival, lorry_arrival, manifest_upload, or dc_sale"
    )
    reference_id: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="manifest_snapshot_id for vessel, demo_transfer_id for lorry"
    )
    event_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    details: Mapped[Optional[dict]] = mapped_column(
        JSON, nullable=True
    )

    __table_args__ = (
        Index("ix_demo_arrival_type", "event_type"),
        Index("ix_demo_arrival_time", "event_time"),
    )


class DemoStockProjection(Base, IdMixin, TimestampMixin):
    """Point-in-time stock projection for dashboard views."""

    __tablename__ = "demo_stock_projections"

    location_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="warehouse or dc"
    )
    location_id: Mapped[int] = mapped_column(Integer, nullable=False)
    sku_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skus.id"), nullable=False
    )
    projected_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    projection_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        Index("ix_demo_proj_location", "location_type", "location_id"),
        Index("ix_demo_proj_sku", "sku_id"),
        Index("ix_demo_proj_time", "projection_time"),
    )


class DemoLorryDayState(Base, IdMixin, TimestampMixin):
    """Effective lorry state for a specific business day in the 48-hour horizon."""

    __tablename__ = "demo_lorry_day_states"

    lorry_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("lorries.id"), nullable=False
    )
    business_date: Mapped[date] = mapped_column(
        Date, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="available, unavailable, or assigned"
    )
    source: Mapped[str] = mapped_column(
        String(30), nullable=False, default="manual", comment="manual or plan_approval"
    )

    __table_args__ = (
        Index("ix_demo_lorry_day_lorry", "lorry_id"),
        Index("ix_demo_lorry_day_date", "business_date"),
        Index("ix_demo_lorry_day_status", "status"),
    )

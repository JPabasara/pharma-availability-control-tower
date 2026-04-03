"""Snapshot tables: manifests, warehouse stock, DC stock, sales history, lorry state, ETA."""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from storage.models.base import Base, IdMixin, TimestampMixin


# ---------------------------------------------------------------------------
# Manifest Snapshots
# ---------------------------------------------------------------------------


class ManifestSnapshot(Base, IdMixin, TimestampMixin):
    """Header for a vessel manifest fetch."""

    __tablename__ = "manifest_snapshots"

    manifest_name: Mapped[str] = mapped_column(
        String(200), nullable=False, default="Unnamed Manifest"
    )
    vessel_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("vessels.id"), nullable=False
    )
    snapshot_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="active",
        comment="active, arrived, cancelled"
    )

    lines = relationship("ManifestLine", back_populates="snapshot", cascade="all, delete-orphan")
    vessel = relationship("Vessel")

    __table_args__ = (
        Index("ix_manifest_snap_vessel", "vessel_id"),
        Index("ix_manifest_snap_time", "snapshot_time"),
        Index("ix_manifest_snap_status", "status"),
    )


class ManifestLine(Base, IdMixin, TimestampMixin):
    """Individual manifest line item."""

    __tablename__ = "manifest_lines"

    manifest_snapshot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("manifest_snapshots.id"), nullable=False
    )
    sku_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skus.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reefer_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    snapshot = relationship("ManifestSnapshot", back_populates="lines")

    __table_args__ = (
        Index("ix_manifest_line_snap", "manifest_snapshot_id"),
        Index("ix_manifest_line_sku", "sku_id"),
    )


# ---------------------------------------------------------------------------
# Warehouse Stock Snapshots
# ---------------------------------------------------------------------------


class WarehouseStockSnapshot(Base, IdMixin, TimestampMixin):
    """Header for a warehouse stock snapshot."""

    __tablename__ = "warehouse_stock_snapshots"

    snapshot_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    items = relationship(
        "WarehouseStockItem", back_populates="snapshot", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_wh_stock_snap_time", "snapshot_time"),
    )


class WarehouseStockItem(Base, IdMixin, TimestampMixin):
    """Per-SKU warehouse stock within a snapshot."""

    __tablename__ = "warehouse_stock_items"

    snapshot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("warehouse_stock_snapshots.id"), nullable=False
    )
    sku_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skus.id"), nullable=False
    )
    physical_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reserved_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    effective_quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="physical - reserved"
    )

    snapshot = relationship("WarehouseStockSnapshot", back_populates="items")

    __table_args__ = (
        Index("ix_wh_stock_item_snap", "snapshot_id"),
        Index("ix_wh_stock_item_sku", "sku_id"),
    )


# ---------------------------------------------------------------------------
# DC Stock Snapshots
# ---------------------------------------------------------------------------


class DCStockSnapshot(Base, IdMixin, TimestampMixin):
    """Header for a DC stock snapshot."""

    __tablename__ = "dc_stock_snapshots"

    dc_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dcs.id"), nullable=False
    )
    snapshot_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    items = relationship(
        "DCStockItem", back_populates="snapshot", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_dc_stock_snap_dc", "dc_id"),
        Index("ix_dc_stock_snap_time", "snapshot_time"),
    )


class DCStockItem(Base, IdMixin, TimestampMixin):
    """Per-SKU stock at a specific DC within a snapshot."""

    __tablename__ = "dc_stock_items"

    snapshot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dc_stock_snapshots.id"), nullable=False
    )
    sku_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skus.id"), nullable=False
    )
    physical_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    in_transit_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    effective_quantity: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="physical + in_transit"
    )

    snapshot = relationship("DCStockSnapshot", back_populates="items")

    __table_args__ = (
        Index("ix_dc_stock_item_snap", "snapshot_id"),
        Index("ix_dc_stock_item_sku", "sku_id"),
    )


# ---------------------------------------------------------------------------
# Sales History
# ---------------------------------------------------------------------------


class SalesHistoryRecord(Base, IdMixin, TimestampMixin):
    """Daily sales record per SKU per DC."""

    __tablename__ = "sales_history_records"

    dc_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("dcs.id"), nullable=False
    )
    sku_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("skus.id"), nullable=False
    )
    sale_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    quantity_sold: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("ix_sales_dc", "dc_id"),
        Index("ix_sales_sku", "sku_id"),
        Index("ix_sales_date", "sale_date"),
        Index("ix_sales_dc_sku_date", "dc_id", "sku_id", "sale_date"),
    )


# ---------------------------------------------------------------------------
# Lorry State Snapshots
# ---------------------------------------------------------------------------


class LorryStateSnapshot(Base, IdMixin, TimestampMixin):
    """Header for a lorry state snapshot."""

    __tablename__ = "lorry_state_snapshots"

    snapshot_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    items = relationship(
        "LorryStateItem", back_populates="snapshot", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_lorry_state_snap_time", "snapshot_time"),
    )


class LorryStateItem(Base, IdMixin, TimestampMixin):
    """Binary lorry availability per snapshot."""

    __tablename__ = "lorry_state_items"

    snapshot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("lorry_state_snapshots.id"), nullable=False
    )
    lorry_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("lorries.id"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="available",
        comment="available or unavailable"
    )

    snapshot = relationship("LorryStateSnapshot", back_populates="items")

    __table_args__ = (
        Index("ix_lorry_state_item_snap", "snapshot_id"),
        Index("ix_lorry_state_item_lorry", "lorry_id"),
    )


# ---------------------------------------------------------------------------
# ETA Snapshots
# ---------------------------------------------------------------------------


class ETASnapshot(Base, IdMixin, TimestampMixin):
    """Vessel ETA data point from mock API."""

    __tablename__ = "eta_snapshots"

    vessel_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("vessels.id"), nullable=False
    )
    eta_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source: Mapped[str] = mapped_column(
        String(50), nullable=False, default="mock_api"
    )

    __table_args__ = (
        Index("ix_eta_vessel", "vessel_id"),
        Index("ix_eta_fetched", "fetched_at"),
    )

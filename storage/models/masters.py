"""Master reference tables: SKUs, DCs, Lorries, Route Edges, Vessels."""

from sqlalchemy import Boolean, Float, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from storage.models.base import Base, IdMixin, TimestampMixin


class SKU(Base, IdMixin, TimestampMixin):
    """Pharmaceutical SKU master data."""

    __tablename__ = "skus"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    reefer_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    unit_weight_kg: Mapped[float] = mapped_column(Float, nullable=False)
    unit_volume_m3: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        Index("ix_skus_code", "code"),
        Index("ix_skus_category", "category"),
    )


class DC(Base, IdMixin, TimestampMixin):
    """Distribution Center master data."""

    __tablename__ = "dcs"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    region: Mapped[str] = mapped_column(String(100), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=True)
    longitude: Mapped[float] = mapped_column(Float, nullable=True)

    __table_args__ = (
        Index("ix_dcs_code", "code"),
        Index("ix_dcs_region", "region"),
    )


class Lorry(Base, IdMixin, TimestampMixin):
    """Lorry / vehicle master data."""

    __tablename__ = "lorries"

    registration: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    lorry_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="normal or reefer"
    )
    capacity_units: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="available",
        comment="available or unavailable"
    )

    __table_args__ = (
        Index("ix_lorries_registration", "registration"),
        Index("ix_lorries_lorry_type", "lorry_type"),
        Index("ix_lorries_status", "status"),
    )


class RouteEdge(Base, IdMixin, TimestampMixin):
    """Fixed route graph edge (warehouse → DC, or DC → DC)."""

    __tablename__ = "route_edges"

    origin_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="warehouse or dc"
    )
    origin_id: Mapped[int] = mapped_column(Integer, nullable=False)
    destination_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="dc"
    )
    destination_id: Mapped[int] = mapped_column(Integer, nullable=False)
    travel_time_hours: Mapped[float] = mapped_column(Float, nullable=False)
    cost: Mapped[float] = mapped_column(Float, nullable=False)

    __table_args__ = (
        Index("ix_route_origin", "origin_type", "origin_id"),
        Index("ix_route_destination", "destination_type", "destination_id"),
    )


class Vessel(Base, IdMixin, TimestampMixin):
    """Vessel master data."""

    __tablename__ = "vessels"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    vessel_type: Mapped[str] = mapped_column(String(50), nullable=True)

    __table_args__ = (
        Index("ix_vessels_code", "code"),
    )

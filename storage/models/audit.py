"""Audit log table for cross-cutting traceability."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column

from storage.models.base import Base, IdMixin, TimestampMixin


class AuditLog(Base, IdMixin, TimestampMixin):
    """Cross-cutting audit record for any entity change."""

    __tablename__ = "audit_logs"

    entity_type: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="e.g. plan_version, reservation, transfer, snapshot"
    )
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="e.g. created, approved, rejected, overridden, arrived"
    )
    actor: Mapped[str] = mapped_column(String(100), nullable=False, default="system")
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index("ix_audit_entity", "entity_type", "entity_id"),
        Index("ix_audit_action", "action"),
        Index("ix_audit_timestamp", "timestamp"),
        Index("ix_audit_actor", "actor"),
    )

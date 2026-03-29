"""Planner flow storage: decisions and override reasons."""

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from storage.models.base import Base, IdMixin, TimestampMixin


class PlannerDecision(Base, IdMixin, TimestampMixin):
    """Record of a planner approve, reject, or override action."""

    __tablename__ = "planner_decisions"

    plan_version_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("m3_plan_versions.id"), nullable=False
    )
    decision_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="approve, reject, override"
    )
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    decided_by: Mapped[str] = mapped_column(String(100), nullable=False, default="planner")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    overrides = relationship(
        "OverrideReason", back_populates="decision", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_planner_dec_plan", "plan_version_id"),
        Index("ix_planner_dec_type", "decision_type"),
        Index("ix_planner_dec_time", "decided_at"),
    )


class OverrideReason(Base, IdMixin, TimestampMixin):
    """Detail of a single field change in a planner override."""

    __tablename__ = "override_reasons"

    decision_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("planner_decisions.id"), nullable=False
    )
    field_changed: Mapped[str] = mapped_column(String(100), nullable=False)
    old_value: Mapped[str] = mapped_column(String(500), nullable=False)
    new_value: Mapped[str] = mapped_column(String(500), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    decision = relationship("PlannerDecision", back_populates="overrides")

    __table_args__ = (
        Index("ix_override_decision", "decision_id"),
    )

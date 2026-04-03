"""add planning_start_date to engine_runs

Revision ID: c4f7e2a1b9d0
Revises: a1b2c3d4e5f6
Create Date: 2026-04-03 13:10:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "c4f7e2a1b9d0"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "engine_runs",
        sa.Column(
            "planning_start_date",
            sa.Date(),
            nullable=True,
            comment="Day 1 of the 48-hour planning horizon for this execution",
        ),
    )
    op.create_index(
        "ix_engine_run_planning_start",
        "engine_runs",
        ["planning_start_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_engine_run_planning_start", table_name="engine_runs")
    op.drop_column("engine_runs", "planning_start_date")

"""demo_operations_extension

Revision ID: 7d3f1b8c2a11
Revises: 366ba6a32c1d
Create Date: 2026-04-01 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7d3f1b8c2a11"
down_revision: Union[str, None] = "366ba6a32c1d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_foreign_keys_for_columns(table_name: str, columns: list[str]) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    fks = inspector.get_foreign_keys(table_name)
    for fk in fks:
        if any(col in columns for col in fk['constrained_columns']):
            op.drop_constraint(fk['name'], table_name, type_="foreignkey")


def upgrade() -> None:
    op.add_column(
        "manifest_snapshots",
        sa.Column(
            "manifest_name",
            sa.String(length=200),
            nullable=False,
            server_default="Unnamed Manifest",
        ),
    )

    op.create_table(
        "m3_plan_runs",
        sa.Column("plan_version_id", sa.Integer(), nullable=False),
        sa.Column("lorry_id", sa.Integer(), nullable=False),
        sa.Column("dispatch_day", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["lorry_id"], ["lorries.id"]),
        sa.ForeignKeyConstraint(["plan_version_id"], ["m3_plan_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_m3_run_day", "m3_plan_runs", ["dispatch_day"], unique=False)
    op.create_index("ix_m3_run_lorry", "m3_plan_runs", ["lorry_id"], unique=False)
    op.create_index("ix_m3_run_plan", "m3_plan_runs", ["plan_version_id"], unique=False)

    op.add_column("m3_plan_stops", sa.Column("plan_run_id", sa.Integer(), nullable=True))
    op.create_foreign_key(None, "m3_plan_stops", "m3_plan_runs", ["plan_run_id"], ["id"])

    op.execute(
        """
        INSERT INTO m3_plan_runs (plan_version_id, lorry_id, dispatch_day, created_at, updated_at)
        SELECT DISTINCT plan_version_id, lorry_id, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM m3_plan_stops
        """
    )
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            UPDATE m3_plan_stops
            SET plan_run_id = r.id
            FROM m3_plan_runs r
            WHERE r.plan_version_id = m3_plan_stops.plan_version_id
              AND r.lorry_id = m3_plan_stops.lorry_id
            """
        )
    else:
        op.execute(
            """
            UPDATE m3_plan_stops s
            JOIN m3_plan_runs r
              ON r.plan_version_id = s.plan_version_id
             AND r.lorry_id = s.lorry_id
            SET s.plan_run_id = r.id
            """
        )

    _drop_foreign_keys_for_columns("m3_plan_stops", ["plan_version_id", "lorry_id"])
    with op.batch_alter_table("m3_plan_stops") as batch_op:
        batch_op.alter_column("plan_run_id", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_index("ix_m3_stop_plan")
        batch_op.drop_index("ix_m3_stop_lorry")
        batch_op.create_index("ix_m3_stop_run", ["plan_run_id"], unique=False)
        batch_op.drop_column("plan_version_id")
        batch_op.drop_column("lorry_id")

    op.add_column("demo_reservations", sa.Column("plan_stop_id", sa.Integer(), nullable=True))
    op.create_foreign_key(None, "demo_reservations", "m3_plan_stops", ["plan_stop_id"], ["id"])
    op.create_index("ix_demo_res_stop", "demo_reservations", ["plan_stop_id"], unique=False)

    op.add_column("demo_transfers", sa.Column("plan_stop_id", sa.Integer(), nullable=True))
    op.create_foreign_key(None, "demo_transfers", "m3_plan_stops", ["plan_stop_id"], ["id"])
    op.create_index("ix_demo_xfer_stop", "demo_transfers", ["plan_stop_id"], unique=False)

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            UPDATE demo_transfers
            SET plan_stop_id = s.id
            FROM m3_plan_runs r
            JOIN m3_plan_stops s ON s.plan_run_id = r.id
            WHERE r.plan_version_id = demo_transfers.plan_version_id
              AND r.lorry_id = demo_transfers.lorry_id
              AND s.dc_id = demo_transfers.dc_id
              AND demo_transfers.plan_stop_id IS NULL
            """
        )
    else:
        op.execute(
            """
            UPDATE demo_transfers t
            JOIN m3_plan_runs r
              ON r.plan_version_id = t.plan_version_id
             AND r.lorry_id = t.lorry_id
            JOIN m3_plan_stops s
              ON s.plan_run_id = r.id
             AND s.dc_id = t.dc_id
            SET t.plan_stop_id = s.id
            WHERE t.plan_stop_id IS NULL
            """
        )

    op.create_table(
        "demo_lorry_day_states",
        sa.Column("lorry_id", sa.Integer(), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False, server_default="manual"),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["lorry_id"], ["lorries.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_demo_lorry_day_date", "demo_lorry_day_states", ["business_date"], unique=False)
    op.create_index("ix_demo_lorry_day_lorry", "demo_lorry_day_states", ["lorry_id"], unique=False)
    op.create_index("ix_demo_lorry_day_status", "demo_lorry_day_states", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_demo_lorry_day_status", table_name="demo_lorry_day_states")
    op.drop_index("ix_demo_lorry_day_lorry", table_name="demo_lorry_day_states")
    op.drop_index("ix_demo_lorry_day_date", table_name="demo_lorry_day_states")
    op.drop_table("demo_lorry_day_states")

    op.drop_index("ix_demo_xfer_stop", table_name="demo_transfers")
    _drop_foreign_keys_for_columns("demo_transfers", ["plan_stop_id"])
    with op.batch_alter_table("demo_transfers") as batch_op:
        batch_op.drop_column("plan_stop_id")

    op.drop_index("ix_demo_res_stop", table_name="demo_reservations")
    _drop_foreign_keys_for_columns("demo_reservations", ["plan_stop_id"])
    with op.batch_alter_table("demo_reservations") as batch_op:
        batch_op.drop_column("plan_stop_id")

    with op.batch_alter_table("m3_plan_stops") as batch_op:
        batch_op.add_column(sa.Column("plan_version_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("lorry_id", sa.Integer(), nullable=True))

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            UPDATE m3_plan_stops
            SET plan_version_id = r.plan_version_id,
                lorry_id = r.lorry_id
            FROM m3_plan_runs r
            WHERE r.id = m3_plan_stops.plan_run_id
            """
        )
    else:
        op.execute(
            """
            UPDATE m3_plan_stops s
            JOIN m3_plan_runs r ON r.id = s.plan_run_id
            SET s.plan_version_id = r.plan_version_id,
                s.lorry_id = r.lorry_id
            """
        )

    _drop_foreign_keys_for_columns("m3_plan_stops", ["plan_run_id"])
    with op.batch_alter_table("m3_plan_stops") as batch_op:
        batch_op.alter_column("plan_version_id", existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column("lorry_id", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_index("ix_m3_stop_run")
        batch_op.create_index("ix_m3_stop_plan", ["plan_version_id"], unique=False)
        batch_op.create_index("ix_m3_stop_lorry", ["lorry_id"], unique=False)
        batch_op.create_foreign_key(None, "m3_plan_versions", ["plan_version_id"], ["id"])
        batch_op.create_foreign_key(None, "lorries", ["lorry_id"], ["id"])
        batch_op.drop_column("plan_run_id")

    op.drop_index("ix_m3_run_plan", table_name="m3_plan_runs")
    op.drop_index("ix_m3_run_lorry", table_name="m3_plan_runs")
    op.drop_index("ix_m3_run_day", table_name="m3_plan_runs")
    op.drop_table("m3_plan_runs")

    with op.batch_alter_table("manifest_snapshots") as batch_op:
        batch_op.drop_column("manifest_name")

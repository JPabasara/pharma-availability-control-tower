"""demo_operations_extension

Revision ID: 7d3f1b8c2a11
Revises: 366ba6a32c1d
Create Date: 2026-04-01 12:00:00.000000

"""

from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7d3f1b8c2a11"
down_revision: Union[str, None] = "366ba6a32c1d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_shapes() -> dict[str, sa.Table]:
    metadata = sa.MetaData()
    return {
        "m3_plan_runs": sa.Table(
            "m3_plan_runs",
            metadata,
            sa.Column("id", sa.Integer()),
            sa.Column("plan_version_id", sa.Integer()),
            sa.Column("lorry_id", sa.Integer()),
            sa.Column("dispatch_day", sa.Integer()),
            sa.Column("created_at", sa.DateTime(timezone=True)),
            sa.Column("updated_at", sa.DateTime(timezone=True)),
        ),
        "m3_plan_stops": sa.Table(
            "m3_plan_stops",
            metadata,
            sa.Column("id", sa.Integer()),
            sa.Column("plan_version_id", sa.Integer()),
            sa.Column("lorry_id", sa.Integer()),
            sa.Column("plan_run_id", sa.Integer()),
            sa.Column("dc_id", sa.Integer()),
            sa.Column("stop_sequence", sa.Integer()),
        ),
        "demo_transfers": sa.Table(
            "demo_transfers",
            metadata,
            sa.Column("id", sa.Integer()),
            sa.Column("plan_version_id", sa.Integer()),
            sa.Column("lorry_id", sa.Integer()),
            sa.Column("dc_id", sa.Integer()),
            sa.Column("plan_stop_id", sa.Integer()),
        ),
    }


def _drop_foreign_keys_for_columns(table_name: str, columns: list[str]) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    target_columns = set(columns)

    for foreign_key in inspector.get_foreign_keys(table_name):
        constraint_name = foreign_key.get("name")
        constrained_columns = set(foreign_key.get("constrained_columns") or [])
        if constraint_name and constrained_columns.intersection(target_columns):
            op.drop_constraint(constraint_name, table_name, type_="foreignkey")


def _backfill_plan_runs() -> None:
    bind = op.get_bind()
    tables = _table_shapes()
    plan_runs = tables["m3_plan_runs"]
    stops = tables["m3_plan_stops"]
    now = datetime.now(timezone.utc)

    distinct_pairs = bind.execute(
        sa.select(stops.c.plan_version_id, stops.c.lorry_id).distinct()
    ).fetchall()

    if distinct_pairs:
        bind.execute(
            sa.insert(plan_runs),
            [
                {
                    "plan_version_id": row.plan_version_id,
                    "lorry_id": row.lorry_id,
                    "dispatch_day": 1,
                    "created_at": now,
                    "updated_at": now,
                }
                for row in distinct_pairs
            ],
        )

    run_lookup = {
        (row.plan_version_id, row.lorry_id): row.id
        for row in bind.execute(
            sa.select(plan_runs.c.id, plan_runs.c.plan_version_id, plan_runs.c.lorry_id)
        ).fetchall()
    }

    stop_rows = bind.execute(
        sa.select(stops.c.id, stops.c.plan_version_id, stops.c.lorry_id)
    ).fetchall()
    for row in stop_rows:
        plan_run_id = run_lookup.get((row.plan_version_id, row.lorry_id))
        if plan_run_id is None:
            continue
        bind.execute(
            sa.update(stops)
            .where(stops.c.id == row.id)
            .values(plan_run_id=plan_run_id)
        )


def _backfill_transfer_stop_links() -> None:
    bind = op.get_bind()
    tables = _table_shapes()
    plan_runs = tables["m3_plan_runs"]
    stops = tables["m3_plan_stops"]
    transfers = tables["demo_transfers"]

    run_lookup = {
        (row.plan_version_id, row.lorry_id): row.id
        for row in bind.execute(
            sa.select(plan_runs.c.id, plan_runs.c.plan_version_id, plan_runs.c.lorry_id)
        ).fetchall()
    }

    stop_lookup: dict[tuple[int, int], int] = {}
    stop_rows = bind.execute(
        sa.select(stops.c.id, stops.c.plan_run_id, stops.c.dc_id)
        .order_by(stops.c.plan_run_id, stops.c.stop_sequence, stops.c.id)
    ).fetchall()
    for row in stop_rows:
        stop_lookup.setdefault((row.plan_run_id, row.dc_id), row.id)

    transfer_rows = bind.execute(
        sa.select(
            transfers.c.id,
            transfers.c.plan_version_id,
            transfers.c.lorry_id,
            transfers.c.dc_id,
        ).where(transfers.c.plan_stop_id.is_(None))
    ).fetchall()
    for row in transfer_rows:
        run_id = run_lookup.get((row.plan_version_id, row.lorry_id))
        if run_id is None:
            continue
        plan_stop_id = stop_lookup.get((run_id, row.dc_id))
        if plan_stop_id is None:
            continue
        bind.execute(
            sa.update(transfers)
            .where(transfers.c.id == row.id)
            .values(plan_stop_id=plan_stop_id)
        )


def _restore_stop_columns_from_runs() -> None:
    bind = op.get_bind()
    tables = _table_shapes()
    plan_runs = tables["m3_plan_runs"]
    stops = tables["m3_plan_stops"]

    run_lookup = {
        row.id: (row.plan_version_id, row.lorry_id)
        for row in bind.execute(
            sa.select(plan_runs.c.id, plan_runs.c.plan_version_id, plan_runs.c.lorry_id)
        ).fetchall()
    }

    stop_rows = bind.execute(sa.select(stops.c.id, stops.c.plan_run_id)).fetchall()
    for row in stop_rows:
        restored = run_lookup.get(row.plan_run_id)
        if restored is None:
            continue
        bind.execute(
            sa.update(stops)
            .where(stops.c.id == row.id)
            .values(plan_version_id=restored[0], lorry_id=restored[1])
        )


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

    _backfill_plan_runs()

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

    _backfill_transfer_stop_links()

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

    _restore_stop_columns_from_runs()

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

"""add ml traceability columns

Revision ID: a1b2c3d4e5f6
Revises: 7d3f1b8c2a11
Create Date: 2026-04-02 23:30:00.000000

Adds traceability columns for ML model integration:
- engine_runs: engine_mode, engine_impl, engine_version, engine_trace
- m1_results: score_breakdown, raw_features
- m2_requests: urgency_score, shortage_probability, hours_until_shortage,
               effective_stock_at_run, projected_48h_sales, safety_stock, raw_features
- m3_plan_versions: plan_name, generation_strategy, objective_value, solver_trace

All columns are nullable and additive — no data migration required.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers
revision = 'a1b2c3d4e5f6'
down_revision = '7d3f1b8c2a11'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── engine_runs ─────────────────────────────────────────────────
    op.add_column('engine_runs', sa.Column('engine_mode', sa.String(10), nullable=True,
                                           comment='stub or real'))
    op.add_column('engine_runs', sa.Column('engine_impl', sa.String(50), nullable=True,
                                           comment='Implementation label'))
    op.add_column('engine_runs', sa.Column('engine_version', sa.String(50), nullable=True,
                                           comment='Model/build version string'))
    op.add_column('engine_runs', sa.Column('engine_trace', sa.JSON(), nullable=True,
                                           comment='JSON metadata about execution'))

    # ── m1_results ──────────────────────────────────────────────────
    op.add_column('m1_results', sa.Column('score_breakdown', sa.Text(), nullable=True,
                                          comment='Human-readable score breakdown'))
    op.add_column('m1_results', sa.Column('raw_features', sa.JSON(), nullable=True,
                                          comment='JSON snapshot of derived M1 features'))

    # ── m2_requests ─────────────────────────────────────────────────
    op.add_column('m2_requests', sa.Column('urgency_score', sa.Float(), nullable=True,
                                           comment='Raw urgency score from M2 (0-100)'))
    op.add_column('m2_requests', sa.Column('shortage_probability', sa.Float(), nullable=True,
                                           comment='Shortage probability from classifier'))
    op.add_column('m2_requests', sa.Column('hours_until_shortage', sa.Float(), nullable=True,
                                           comment='Predicted hours until shortage (0-48)'))
    op.add_column('m2_requests', sa.Column('effective_stock_at_run', sa.Float(), nullable=True,
                                           comment='Effective stock at inference time'))
    op.add_column('m2_requests', sa.Column('projected_48h_sales', sa.Float(), nullable=True,
                                           comment='Projected 48h sales'))
    op.add_column('m2_requests', sa.Column('safety_stock', sa.Float(), nullable=True,
                                           comment='Safety stock level'))
    op.add_column('m2_requests', sa.Column('raw_features', sa.JSON(), nullable=True,
                                           comment='JSON snapshot of M2 features'))

    # ── m3_plan_versions ────────────────────────────────────────────
    op.add_column('m3_plan_versions', sa.Column('plan_name', sa.String(100), nullable=True,
                                                 comment='Human-readable plan variant name'))
    op.add_column('m3_plan_versions', sa.Column('generation_strategy', sa.String(50), nullable=True,
                                                 comment='urgency_max, balanced, cost_aware'))
    op.add_column('m3_plan_versions', sa.Column('objective_value', sa.Float(), nullable=True,
                                                 comment='Solver objective function value'))
    op.add_column('m3_plan_versions', sa.Column('solver_trace', sa.JSON(), nullable=True,
                                                 comment='JSON summary of solver execution'))


def downgrade() -> None:
    # ── m3_plan_versions ────────────────────────────────────────────
    op.drop_column('m3_plan_versions', 'solver_trace')
    op.drop_column('m3_plan_versions', 'objective_value')
    op.drop_column('m3_plan_versions', 'generation_strategy')
    op.drop_column('m3_plan_versions', 'plan_name')

    # ── m2_requests ─────────────────────────────────────────────────
    op.drop_column('m2_requests', 'raw_features')
    op.drop_column('m2_requests', 'safety_stock')
    op.drop_column('m2_requests', 'projected_48h_sales')
    op.drop_column('m2_requests', 'effective_stock_at_run')
    op.drop_column('m2_requests', 'hours_until_shortage')
    op.drop_column('m2_requests', 'shortage_probability')
    op.drop_column('m2_requests', 'urgency_score')

    # ── m1_results ──────────────────────────────────────────────────
    op.drop_column('m1_results', 'raw_features')
    op.drop_column('m1_results', 'score_breakdown')

    # ── engine_runs ─────────────────────────────────────────────────
    op.drop_column('engine_runs', 'engine_trace')
    op.drop_column('engine_runs', 'engine_version')
    op.drop_column('engine_runs', 'engine_impl')
    op.drop_column('engine_runs', 'engine_mode')

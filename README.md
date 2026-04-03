# Pharma Availability Control Tower

Pharma Availability Control Tower is a planner-facing control tower for pharma replenishment and dispatch coordination. It brings shortage forecasting, inbound shipment prioritization, dispatch planning, planner approval, and execution-state updates into one product so a planner can move from signal to action in a single workflow.

The current repository is a working MVP and competition submission codebase, not a future architecture draft. The implemented product includes a FastAPI backend, a Next.js planner console, database-backed state and audit trails, seeded demo data, and ML-backed `M1`, `M2`, and `M3` adapters under `apps/api/app/orchestration/real`.

## Problem

Pharma distribution planning gets difficult when multiple operational pressures overlap:

- DCs can move toward shortage at different speeds.
- Vessel manifests can arrive at the same time and compete for clearance attention.
- Cold-chain items need reefer-compatible dispatch.
- Lorry capacity and day-level availability constrain what can actually be shipped.
- Approval decisions and physical stock movement should not be treated as the same event.

Without a control tower, the planner has to stitch together spreadsheets, stock snapshots, and transport constraints manually.

## Solution

This product turns the workflow into one planner-operated system:

1. Inputs are refreshed from manifests, warehouse stock, DC stock, sales history, lorry state, and ETAs.
2. `M2` forecasts 48-hour replenishment pressure and produces DC request lines.
3. `M1` prioritizes inbound manifest shipments for clearance review.
4. `M3` generates candidate two-day dispatch plans.
5. The planner reviews, overrides, approves, or rejects the draft plan.
6. Demo Operations advance real business state through controlled events such as manifest arrival, DC sale posting, lorry availability changes, and stop arrival.
7. History and Reports preserve the decision trail and exportable outputs.

The planner is the only end user in the current version.

## Product Scope

The seeded demo environment is intentionally compact but operationally meaningful:

- 15 SKUs
- 1 warehouse
- 5 distribution centers
- 8 lorries
- 48-hour planning horizon
- run-based `M3` plans with `dispatch_day`
- maximum 2 DC stops per run
- day-specific lorry assignment across Day 1 and Day 2

## What Makes The Product Different

The key product decision is the separation between planning state and physical execution state.

- Approval does not directly mutate physical warehouse or DC stock.
- Approval creates stop-scoped reservations, in-transit transfers, and lorry-day assignments.
- Physical stock changes only when explicit business events are posted.
- Effective stock is derived from physical stock plus active planning overlays.

This keeps the planner workflow auditable and avoids ghost inventory.

## Planner Console

The implemented planner console includes these views:

- `Dashboard`
- `Inputs`
- `Forecaster`
- `Prioritizer`
- `Optimizer`
- `History`
- `Demo Operations`
- `Reports`

The UI label is `Demo Operations`. For route compatibility, the frontend route remains `/demo-state`.

## Runtime Architecture

The active runtime in this cleaned repository is centered on these areas:

- `apps/api/app`
  - FastAPI application, route groups, orchestration, planner flow, demo operations, and dependencies
- `apps/web`
  - Next.js App Router planner console
- `apps/api/app/orchestration/real`
  - real `M1`, `M2`, and `M3` adapters used for the ML-backed demo path
- `apps/api/app/orchestration/stubs`
  - compatibility stubs kept for runtime safety and fallback
- `ml/`
  - model code, synthetic dataset generation, and committed model artifacts
- `storage/`
  - SQLAlchemy models and persistence layer
- `db/`
  - Alembic migrations and seed entrypoints
- `data/seed/`
  - deterministic business seed data for the MVP scenario

## Tech Stack

- Backend: FastAPI
- Frontend: Next.js App Router
- Persistence: SQLAlchemy + Alembic
- Local database: MySQL 8 via Docker
- Hosted database: configured through `DATABASE_URL`
- ML and optimization:
  - `M1`: mathematical priority scoring
  - `M2`: XGBoost-based shortage request generation
  - `M3`: OR-Tools candidate dispatch planning

## Hosted And Local Access

The documentation is written with a hosted demo first and local run second.

- Hosted deployment and reviewer flow: [host_workflow.md](host_workflow.md)
- Local setup and commands: [HOW_TO_RUN.md](HOW_TO_RUN.md)
- Reviewer click path: [docs/submission/EXECUTABLE_WALKTHROUGH.md](docs/submission/EXECUTABLE_WALKTHROUGH.md)

For the competition story, the intended demo path is the ML-backed adapter flow under `apps/api/app/orchestration/real`. Stub bridge code remains in the repository for compatibility, but the submission documents focus on the implemented planning workflow rather than an unfinished-engine roadmap.

## Submission Notes

This repository should be packaged as source code plus required data and documentation. Local runtime folders such as `.git/`, `.venv/`, `apps/web/node_modules/`, `apps/web/.next/`, and other transient caches should be excluded from the final ZIP bundle.

See [docs/submission/SUBMISSION_CONTENT_MAP.md](docs/submission/SUBMISSION_CONTENT_MAP.md) for the packaging checklist.
See [docs/submission/DATA_AND_DB_READINESS.md](docs/submission/DATA_AND_DB_READINESS.md) for the canonical reset/reseed guidance used before screenshots, recording, and final submission packaging.

## Related Docs

- [PROJECT_PLAN.md](PROJECT_PLAN.md)
- [REPO_STRUCTURE.md](REPO_STRUCTURE.md)
- [HOW_TO_RUN.md](HOW_TO_RUN.md)
- [host_workflow.md](host_workflow.md)
- [docs/submission/CODE_DOCUMENTATION.md](docs/submission/CODE_DOCUMENTATION.md)
- [docs/submission/EXECUTABLE_WALKTHROUGH.md](docs/submission/EXECUTABLE_WALKTHROUGH.md)
- [docs/submission/DATA_AND_DB_READINESS.md](docs/submission/DATA_AND_DB_READINESS.md)
- [docs/submission/SUBMISSION_CONTENT_MAP.md](docs/submission/SUBMISSION_CONTENT_MAP.md)

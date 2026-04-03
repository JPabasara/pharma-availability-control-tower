# Code Documentation

## System Overview

This repository implements a planner-facing pharma availability control tower. The product combines source-data refresh, shortage forecasting, manifest prioritization, dispatch plan generation, planner decisions, and execution-state updates.

The planner workflow is:

1. refresh inputs
2. generate `M2` requests
3. generate `M1` shipment priorities
4. generate `M3` candidate dispatch plans
5. override, approve, or reject the plan
6. advance business state through Demo Operations
7. review immutable history and export reports

## Backend Structure

Main backend code lives in `apps/api/app/`.

### Application Entry

- `main.py`
  - creates the FastAPI app
  - wires CORS
  - registers all route groups

### Route Groups

- `api/v1/inputs.py`
  - read-only input snapshots and refresh surface
- `api/v1/orchestration.py`
  - refresh `M2`, refresh `M1`, and generate the full planning run
- `api/v1/planner.py`
  - current `M1`, `M2`, and `M3` views
  - plan detail
  - approve, reject, and override endpoints
- `api/v1/demo_state.py`
  - reservations, transfers, stock summary, and arrival-event views
- `api/v1/demo_operations.py`
  - manifest upload and arrival
  - DC sale posting
  - lorry day-state control
  - stop-arrival execution
- `api/v1/reports.py`
  - approved-plan and audit reporting
- `api/v1/dashboard.py`
  - dashboard summary metrics and alerts
- `api/v1/mock_eta.py`
  - ETA access for the seeded demo scenario

### Core Services

- `orchestration/service.py`
  - coordinates `M2`, `M1`, and `M3`
  - manages current planning horizon
  - persists engine runs and current draft plan sets
- `planner_flow/service.py`
  - enforces planner actions
  - handles override validation, approval, rejection, and audit creation
- `demo_operations/service.py`
  - applies operational business events to the database-backed demo state
- `input_refresh/service.py`
  - refreshes input families and latest snapshots

### Engine Adapters

- `orchestration/engine_bridge.py`
  - switches between stub and real execution paths
- `orchestration/real/`
  - `m1_real.py`
  - `m2_real.py`
  - `m3_real.py`
- `orchestration/stubs/`
  - fallback-compatible stub implementations kept in the repo for safety

The submission story is centered on the real adapters.

## Frontend Structure

Main frontend code lives in `apps/web/`.

### Planner Pages

- `app/dashboard/page.tsx`
  - current status, lock state, alerts, and fleet summary
- `app/inputs/page.tsx`
  - read-only input families and targeted refresh actions
- `app/requests/page.tsx`
  - `M2` request lines, urgency mix, and timing
- `app/priorities/page.tsx`
  - `M1` shipment ranking with per-shipment expansion
- `app/dispatch/page.tsx`
  - `M3` candidate plan comparison, override editor, approval, and rejection
- `app/history/page.tsx`
  - immutable approved plans and decision trail
- `app/demo-state/page.tsx`
  - Demo Operations workspace and state view
- `app/reports/page.tsx`
  - approved-plan JSON export and audit CSV export

### Shared Frontend Modules

- `components/`
  - reusable cards, tables, shells, and editors
- `lib/api.ts`
  - frontend API client
- `lib/types.ts`
  - frontend data contracts
- `lib/format.ts`
  - display formatting and export helpers

## ML Models And Artifacts

The model code is under `ml/models/`.

### `M1`

- `m1_model.py`
  - mathematical scoring model for inbound manifest prioritization

### `M2`

- `m2_model.py`
  - XGBoost shortage classification and timing regression
- committed artifacts:
  - `artifacts/m2_classifier.json`
  - `artifacts/m2_regressor.json`

### `M3`

- `m3_model.py`
  - OR-Tools based dispatch planning

### Supporting Data

- `ml/datasets/`
  - synthetic datasets and generation scripts used to support model development

## Database, Seed Data, And Persistence

### Schema And Setup

- `db/migrations/`
  - Alembic migrations for the application schema
- `db/seeds/seed_all.py`
  - deterministic seed process for the demo scenario
- `scripts/reset_db.py`
  - local reset entrypoint that drops, migrates, and reseeds

### Seed Data

- `data/seed/`
  - SKUs
  - DCs
  - lorries
  - manifests
  - route edges
  - warehouse stock
  - DC stock
  - vessels
  - sales history

### Persistence Models

`storage/models/` defines the SQLAlchemy entities for:

- master data
- input snapshots
- engine runs and outputs
- plan versions, runs, stops, and items
- planner decisions
- demo reservations and transfers
- lorry day state
- arrival events
- audit logs

## Demo Operations And Auditability

The most important behavior is the split between planner approval and physical execution:

- planner approval creates reservations, transfers, and day assignments
- planner approval does not mutate physical stock directly
- physical stock changes only when explicit business events are posted

This is what makes the history, reports, and demo-state views meaningful. Reviewers can see exactly how planning overlays differ from real stock movement.

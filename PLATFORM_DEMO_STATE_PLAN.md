# Platform Demo State Plan

## Purpose

This document now serves as the current platform-status reference for everything around the engines:

- MySQL persistence
- snapshot readers
- ETA mock integration
- orchestration
- planner backend flow
- demo-state and demo-operations behavior
- planner frontend wiring
- seeded demo environment
- engine stub bridge

`M1`, `M2`, and `M3` are still treated as separate decision engines. The platform owns the data contracts, planner workflow, operational state transitions, and demo execution surface around them.

## Current Platform Status

The platform baseline is implemented and working locally.

Completed subsystems:

- Docker-based local MySQL setup
- SQLAlchemy models and Alembic migrations
- seeded demo dataset
- input readers for manifests, warehouse stock, DC stock, sales history, lorry state, and ETAs
- orchestration and engine-run persistence
- planner APIs for generate, review, override, approve, reject, history, and reports
- planner frontend console
- hosted demo operations UI and backend APIs
- demo-state read models for reservations, transfers, stock summary, and event history

## Current Persistence Model

The database now stores both planning overlays and physical demo-state changes.

Important current entities include:

- master/reference data:
  - `skus`
  - `dcs`
  - `lorries`
  - `route_edges`
  - `vessels`
- snapshots and inputs:
  - `manifest_snapshots` with `manifest_name`
  - `manifest_lines`
  - `warehouse_stock_snapshots`, `warehouse_stock_items`
  - `dc_stock_snapshots`, `dc_stock_items`
  - `sales_history_records`
  - `lorry_state_snapshots`, `lorry_state_items`
  - `eta_snapshots`
- engine and planning storage:
  - `engine_runs`
  - `m1_results`
  - `m2_requests`
  - `m3_plan_versions`
  - `m3_plan_runs`
  - `m3_plan_stops`
  - `m3_plan_items`
- planner and execution overlays:
  - `planner_decisions`
  - `override_reasons`
  - `demo_reservations`
  - `demo_transfers`
  - `demo_lorry_day_states`
  - `demo_arrival_events`
  - `audit_logs`

The important change from the older design is that reservations and transfers are now stop-scoped, and lorry availability is tracked over business dates rather than as a purely binary current-state concept.

## Current Operational Model

The platform now uses a clearer split between planner decisions and physical business events.

- **Planner actions**
  - generate plan
  - override draft
  - approve draft
  - reject draft
- **Demo operations**
  - upload a manifest
  - mark a manifest arrived
  - post a DC sale
  - toggle lorry availability for the next 2 planning days
  - mark a plan stop arrived at a DC

Current rules:

- approval creates reservations, in-transit transfers, and lorry day assignments
- approval does not change physical warehouse or DC stock
- physical stock changes only when explicit business events are posted
- CLI scripts still exist, but they now call the same backend service logic used by the demo-operations API

## Current Input / Read Model Behavior

- `manifest_reader` exposes active manifests with `manifest_name`
- `warehouse_stock_reader` calculates effective stock using active reservations
- `dc_stock_reader` calculates effective stock using active in-transit transfers
- `sales_history_reader` now works on trailing 30-day sales history
- `lorry_state_reader` exposes a 2-day horizon with day-specific states
- business-day logic uses a configurable business timezone, defaulting to `Asia/Colombo`

## Current Planner / Frontend Status

The planner console is implemented and wired to the backend.

Current pages:

- `Dashboard`
- `Inputs`
- `M1 Priorities`
- `M2 Requests`
- `M3 Dispatch`
- `History`
- `Demo Operations`
- `Reports`

Important UI/platform behavior:

- `Demo Operations` is the menu/page label
- `/demo-state` remains the route for compatibility
- Dispatch uses run-based M3 detail and override payloads
- Demo Operations is dropdown-driven and includes:
  - `State View`
  - `Manifest Control`
  - `DC Control`
  - `Lorry Control`
  - `Execution`

## Current API Surface

The main route groups are stable:

- `/api/v1/inputs/*`
- `/api/v1/orchestration/*`
- `/api/v1/planner/*`
- `/api/v1/demo-state/*`
- `/api/v1/demo-operations/*`
- `/api/v1/reports/*`
- `/api/v1/mock/eta/*`

The new hosted operations route group is now part of the current platform, not a future plan.

## Runtime Notes

Important current runtime details:

- `python-multipart` is required for manifest upload endpoints
- `tzdata` is required where system timezone data is unavailable
- local MySQL + reset/seed is still the default development/demo workflow

## Remaining Platform Work

The main platform work still remaining is no longer the planner console itself. It is:

1. connect real `M1`, `M2`, and `M3` behind the existing platform contracts
2. harden production config for deployment and hosted environments
3. set up CI/CD and deployment flow

The intended next deployment path is:

- Vercel for the frontend
- Railway for backend and MySQL
- GitHub Actions plus auto-deploy for CI/CD

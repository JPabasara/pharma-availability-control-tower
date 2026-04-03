# Pharma Availability Control Tower

## Overview

This repository contains the current planner-facing control tower for a pharma dispatch demo environment. The platform is built around four separated layers:

1. **Inputs and readers**
   - vessel manifests
   - warehouse stock
   - DC stock
   - sales history
   - lorry state
   - ETA snapshots
2. **Decision engines**
   - `M1` (Prioritizer) for shipment-level priority ranking — scores and ranks incoming manifests to help the clearance team decide which shipment to clear first when multiple arrive simultaneously
   - `M2` (Forecaster) for DC request generation from 48-hour forecast need
   - `M3` (Optimizer) for candidate dispatch planning over the next 2 planning days
3. **Planner console**
   - dashboard, inputs, priorities, requests, dispatch, history, demo operations, and reports
4. **Demo operations**
   - planner approval creates operational overlays
   - hosted business actions advance physical state through backend APIs and UI controls

The planner is the only end user in the current version.

## Current Product Shape

- 15 SKUs
- 1 warehouse
- 5 DCs
- 8 lorries total
  - 5 normal
  - 3 reefer
- 48-hour planning horizon
- run-based M3 plans with `dispatch_day`
- maximum 2 DC stops per run
- one lorry can be assigned once on Day 1 and once on Day 2
- local MySQL 8 as the default persistence layer
- contract-compatible stub engines still supported until real `M1`, `M2`, and `M3` are plugged in

## Core Rules

- `M1`, `M2`, and `M3` are pure decision layers and do not mutate physical business stock directly.
- `M2` reads trailing 30-day sales history and produces 48-hour request output.
- `M3` plans are expressed as `runs -> stops -> items`, where each run has a `lorry_id` and `dispatch_day`.
- Reefer lorries carry reefer cargo only.
- Planner overrides must pass backend validation for capacity, stock feasibility, lorry-day conflicts, and reefer compatibility.
- Approval does not change physical warehouse or DC stock.
- Approval creates:
  - stop-scoped warehouse reservations
  - stop-scoped DC in-transit transfers
  - date-based lorry day assignments
- Physical stock changes only when business events happen through demo operations:
  - manifest arrival
  - DC sale posting
  - stop arrival at a DC

## Effective State Model

The platform keeps planning state and physical state separate.

- **Warehouse effective stock** is derived from physical stock and active reservations.
- **DC effective stock** is derived from physical stock and active in-transit transfers.
- **Lorry availability** is evaluated over the next 2 planning days, not as a single timeless flag.
- **Demo operations** move the business state forward without turning the planner console into a raw database editor.

This is what prevents ghost inventory and keeps the engines stateless.

## Planner Console

The frontend is a planner-only console with these views:

- `Dashboard`
- `Inputs`
- `Prioritizer`
- `Forecaster`
- `Optimizer`
- `History`
- `Demo Operations`
- `Reports`

The UI label is now **Demo Operations**. For route compatibility, the frontend route remains `/demo-state`.

## Demo Operations

The current hosted demo no longer depends on CLI-only business progression. The platform now supports operational actions through backend APIs and the frontend workspace on `/demo-state`.

Implemented demo operations include:

- manifest CSV upload with `manifest_name`, `vessel_id`, `sku_code`, `quantity`
- manifest arrival to increase warehouse physical stock
- DC sale posting to reduce DC physical stock and extend sales history
- lorry availability toggle for the next 2 planning days
- execution stop arrival to move stop-level transfer quantity into DC physical stock and release matching reservations

The existing CLI scripts are still available, but they now act as thin wrappers over the same service layer rather than being the primary product path.

## Backend API Shape

The main route groups are:

- `/api/v1/inputs/*`
- `/api/v1/orchestration/*`
- `/api/v1/planner/*`
- `/api/v1/demo-state/*`
- `/api/v1/demo-operations/*`
- `/api/v1/reports/*`
- `/api/v1/mock/eta/*`

## Runtime Notes

- Backend: FastAPI
- Frontend: Next.js App Router
- Database: MySQL 8
- Migrations: Alembic + SQLAlchemy
- Important backend runtime dependencies now include:
  - `python-multipart` for manifest upload
  - `tzdata` for business-timezone support on Windows and other environments without system tz data

## Run Locally

Use [HOW_TO_RUN.md](HOW_TO_RUN.md) for the exact local commands.

At a high level:

1. start MySQL with Docker
2. reset/seed the database
3. run the FastAPI backend
4. run the Next.js frontend with `NEXT_PUBLIC_API_BASE_URL`

Main local entry points:

- frontend: `http://127.0.0.1:3000/dashboard`
- API docs: `http://127.0.0.1:8000/docs`

## Current Gaps / Next Step

The platform and planner console are now implemented as the current baseline. The main remaining work is:

1. replace stub `M1`, `M2`, and `M3` with real engines
2. deploy the frontend and backend
3. add CI/CD for automatic integration on merge to `main`

The current hosting direction is:

- frontend on Vercel
- backend and MySQL on Railway
- CI/CD through GitHub Actions plus platform auto-deploy

## Related Docs

- [HOW_TO_RUN.md](HOW_TO_RUN.md)
- [PLATFORM_DEMO_STATE_PLAN.md](PLATFORM_DEMO_STATE_PLAN.md)
- [PROJECT_PLAN.md](PROJECT_PLAN.md)
- [STRATEGY.md](STRATEGY.md)
- [REPO_STRUCTURE.md](REPO_STRUCTURE.md)

# Pharma Availability Control Tower - MVP

## Overview

This repository contains a 7-day MVP for a planner-facing pharma dispatch control tower with four clearly separated concerns:

1. **Snapshot ingestion**
   - fetches vessel manifests from a database snapshot reader
   - fetches warehouse stock, DC stock, sales history, and lorry state from database readers
   - fetches vessel ETA from a mock API
2. **Decision engines (User-Triggered)**
   - `M1` scores shipment-SKU priority
   - `M2` generates DC requests analyzing 48-hour sales forecasts against *Effective DC Stock* (physical + in-transit)
   - `M3` builds candidate 48-hour dispatch plans restricted to 1 trip per available lorry
3. **Planner console**
   - shows read-only inputs, engine outputs, plan comparison, approval, rejection, and overrides
4. **Demo state simulation**
   - creates reservation state on approval
   - simulates warehouse-to-DC stock movement on arrival for the demo only

The planner is the only end user in this MVP.

Until the real engines are connected, the platform layer may use contract-compatible stub outputs for `M1`, `M2`, and `M3` so the planner flow and frontend can be developed end to end.

## Locked MVP Scope

- 15 SKUs
- 1 warehouse
- 5 DCs
- 8 lorries total (Binary state: `available` or `unavailable`)
  - 5 normal
  - 3 reefer
- single trip per lorry per 48-hour planning horizon
- maximum 2 stops per lorry trip
- fixed route time and cost graph
- manifest, stock, sales, and lorry inputs come from snapshot readers
- models run on-demand via planner UI (no background polling)
- approved plan versions are immutable

## Core Rules

- Reefer lorries carry reefer cargo only.
- Normal lorries carry normal cargo only.
- `quantity` stays on manifest lines, stock snapshots, requests, and plan items.
- `capacity_unit` is used for lorry capacity and load feasibility.
- M1 scores per shipment-SKU line, and the UI also shows an aggregated SKU summary.
- The planner may change lorry choice, stop order, and quantities.
- **Overrides** must pass a strict math-bound API validation (capacity, effective warehouse stock, reefer compatibility) before they can be frozen.
- After approval, that plan version is frozen permanently and directly updates the DB with Warehouse reservations and DC in-transit records.

## Engine Contracts

### M1 - Medicine Priority Tracker
**Inputs**
- manifest lines
- warehouse stock snapshot
- active M2 requests
- SKU metadata
- ETA-derived timing

**Outputs**
- `priority_score`
- `priority_band`
- `reefer_required`
- aggregated SKU summary for the dashboard

### M2 - DC Request Generator
**Inputs**
- Effective DC stock (Physical + In-Transit)
- 48-hour sales forecast

**Outputs**
- `dc_request`
- `urgency`
- `required_by`

### M3 - Dispatch Planner
**Inputs**
- M1 output
- M2 output
- warehouse stock snapshot
- lorry state snapshot
- route graph

**Outputs**
- candidate dispatch plans
- ranked best plan
- planner-editable draft plan

## Planner Frontend

The frontend is a planner-only console with these views:

- `Dashboard` for alerts, latest engine runs, and pending approvals
- `Inputs` for read-only manifests, ETA, warehouse stock, DC stock, sales, and lorry snapshots
- `M1 Priorities` for shipment-line scores and aggregated SKU view
- `M2 Requests` for generated request and urgency views
- `M3 Dispatch` for plan comparison, editing, approval, rejection, and overrides
- `History` for immutable approved versions and override trail
- `Demo State` for reservation, in-transit, and simulated stock updates
- `Reports` for approved plan exports and audit views

## Ghost Inventory & Demo State

`M1`, `M2`, and `M3` are stateless and never mutate business stock directly. They rely entirely on **Effective Stock** calculated by the platform layer.

- **Option A (Effective Stock):** When a plan is approved, the database directly logs `demo_reservations` (Warehouse) and `demo_transfers` (DC). Future snapshot reads calculate `Effective WH Stock = Physical - Reserved` and `Effective DC Stock = Physical + In-Transit`.

To simulate physical movement without building complex UIs, physical increments are handled via **Backend Scripts**:
1. `simulate_vessel_arrival.py` -> Converts manifest lines into physical warehouse stock increments.
2. `simulate_lorry_arrival.py` -> Closes an active transfer, removes warehouse reservations, and increments physical DC stock.

## High-Level Flow (User-Triggered)

1. Planner clicks "Generate Plan" in the UI.
2. Readers fetch Effective Warehouse stock, Effective DC stock, sales forecasts, and binary lorry availability.
3. `M2` generates 48-hour DC shortage requests.
4. `M1` scores shipment-line priority.
5. `M3` generates 48-hour candidate dispatch plans (1 trip per lorry).
6. Planner reviews, overrides (triggering math-bound validation check), and approves.
7. System updates DB tables with reserved/in-transit states and freezes the plan.
8. (For Demo) CLI scripts simulate real-world arrival events, updating physical stocks.

## Tech Stack

- Frontend: Next.js
- Backend: FastAPI
- Database: MySQL 8 (Docker local default)
- ML: Python, XGBoost, scikit-learn
- Optimization: Google OR-Tools

## Run Locally

### Backend

1. Start MySQL: `docker compose up -d mysql`
2. Reset and seed the database: `python scripts/reset_db.py`
3. Run the API: `.venv\Scripts\python -m uvicorn apps.api.app.main:app --reload --port 8000`

### Frontend

1. Install dependencies: `cd apps\web && npm install`
2. Set `NEXT_PUBLIC_API_BASE_URL` if needed
   - default local value: `http://127.0.0.1:8000`
   - see `apps/web/.env.example`
3. Start the planner console: `cd apps\web && npm run dev`

### Demo Flow

1. Open `http://127.0.0.1:3000/dashboard`
2. Generate a plan from `M3 Dispatch`
3. Review `M1 Priorities` and `M2 Requests`
4. Override, approve, or reject from `M3 Dispatch`
5. Inspect `History`, `Demo State`, and `Reports`
6. Simulate arrivals with:
   - `python scripts/simulate_vessel_arrival.py`
   - `python scripts/simulate_lorry_arrival.py`

## Platform Delivery Note

- Outside-engine platform work, local MySQL setup, integration readers, ETA mock API, planner flow, demo-state simulation, and engine stubs are planned in `PLATFORM_DEMO_STATE_PLAN.md`.

## Repository Note

The repo structure intentionally keeps `engines/` and `demo_state/` separate. See `REPO_STRUCTURE.md` for the generated tree.

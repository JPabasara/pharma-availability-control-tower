# Pharma Availability Control Tower - MVP

## Overview

This repository contains a 7-day MVP for a planner-facing pharma dispatch control tower with four clearly separated concerns:

1. **Snapshot ingestion**
   - fetches vessel manifests from a database snapshot reader
   - fetches warehouse stock, DC stock, sales history, and lorry state from database readers
   - fetches vessel ETA from a mock API
2. **Decision engines**
   - `M1` scores shipment-SKU priority
   - `M2` generates DC requests from stock and sales snapshots
   - `M3` builds and ranks candidate dispatch plans
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
- 8 lorries total
  - 5 normal
  - 3 reefer
- maximum 2 stops per lorry
- fixed route time and cost graph
- ETA refresh every 2 hours from the mock API
- manifest, stock, sales, and lorry inputs come from snapshot readers
- approved plan versions are immutable

## Core Rules

- Reefer lorries carry reefer cargo only.
- Normal lorries carry normal cargo only.
- `quantity` stays on manifest lines, stock snapshots, requests, and plan items.
- `capacity_unit` is used for lorry capacity and load feasibility.
- M1 scores per shipment-SKU line, and the UI also shows an aggregated SKU summary.
- The planner may change lorry choice, stop order, and quantities before approval.
- After approval, that plan version is frozen permanently.
- Any later change requires a new plan version.

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
- DC stock snapshot
- sales history snapshot

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

## Demo State Boundary

`M1`, `M2`, and `M3` never mutate business stock. They only read snapshots and produce outputs.

The separate `demo_state` module exists only so the demo can show state progression:

1. planner approves a plan
2. demo reservation state is created
3. simulated arrival applies warehouse decrement and DC increment
4. later engine runs consume the updated snapshots

This is local demo behavior, not enterprise transaction ownership.

## High-Level Flow

1. Readers fetch manifest, warehouse stock, DC stock, sales history, and lorry snapshots.
2. ETA provider refreshes vessel ETA from the mock API.
3. `M2` generates daily DC requests.
4. `M1` scores shipment-line priority.
5. `M3` generates and ranks candidate dispatch plans.
6. Planner reviews, edits, approves, rejects, or overrides a draft plan.
7. `demo_state` creates reservation state on approval.
8. `demo_state` simulates arrival and updates demo warehouse/DC stock.

## Tech Stack

- Frontend: Next.js
- Backend: FastAPI
- Database: MySQL 8 (Docker local default)
- ML: Python, XGBoost, scikit-learn
- Optimization: Google OR-Tools

## Platform Delivery Note

- Outside-engine platform work, local MySQL setup, integration readers, ETA mock API, planner flow, demo-state simulation, and engine stubs are planned in `PLATFORM_DEMO_STATE_PLAN.md`.

## Repository Note

The repo structure intentionally keeps `engines/` and `demo_state/` separate. See `REPO_STRUCTURE.md` for the generated tree.

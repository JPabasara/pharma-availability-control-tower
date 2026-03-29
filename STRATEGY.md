# Strategy

## Strategic Intent

Build a credible planner-facing decision layer in 7 days without turning the repo into an ERP clone.

The core idea is simple:

- snapshots come in from readers
- `M1`, `M2`, and `M3` reason over those snapshots
- the planner reviews and decides
- a separate demo-only module simulates stock movement for the demo

## Strategy 1 - Keep Boundaries Hard

The most important decision is architectural separation.

### Engines
- consume snapshots
- produce scores, requests, plans, and reports
- never mutate stock

### Demo state
- reacts only after approval
- creates reservation state
- simulates arrival and stock movement for the demo

### Why this matters
- engine logic stays reusable
- transaction behavior does not leak into model code
- the demo can still show end-to-end state progression

## Strategy 2 - Treat Inputs as "Effective" Snapshots

Use stable readers for operational inputs, executed *only on-demand* via user UI triggers:

- `manifest_reader`
- `warehouse_stock_reader` (Calculates Effective = Physical - Reserved)
- `dc_stock_reader` (Calculates Effective = Physical + In-Transit)
- `sales_history_reader` (Projects 48-hour forecast)
- `lorry_state_reader` (Binary: Available or Unavailable)

This keeps ingest simple and solves the "Ghost Inventory" double-allocation problem.

## Strategy 3 - Keep M3 Explainable

`M3` must stay split internally:

- optimizer generates feasible plans
- ranker scores likely planner acceptance

This keeps plan generation explainable and easier to debug.

## Strategy 4 - Narrow the MVP

The MVP stays intentionally narrow to keep the math solvable:

- 5 DCs
- 8 lorries total (Binary lorry availability: Available / Unavailable)
- 48-hour planning horizon
- 1 guaranteed trip per lorry per plan (no complex multi-shift reuse)
- maximum 2 stops per lorry route
- planner-only UI triggered on-demand

Smaller scope makes the dispatch output easier to trust and demo.

## Strategy 5 - Lock User Behavior

The planner can:

- review input snapshots
- request model execution ("Generate Plan")
- review M1, M2, and M3 outputs
- override lorry choice, stop order, and quantities
- **NEW**: Any override is subject to a strict Math-Bound Validation Engine (checking capacities, effective stock limits, and reefer rules) before it can be frozen.
- approve or reject a plan

Once approved, that plan version is immutable.

## Strategy 6 - Keep Shared Semantics Simple

- use `quantity` for manifest, stock, requests, and plan items
- use `capacity_unit` for lorry capacity and feasibility
- show M1 line-level output and aggregated SKU summary
- keep later runs dependent on new snapshots, not hidden state inside engines

## Strategy 7 - Preserve Demo Credibility via Scripts

The demo must visibly show state progression without models polling databases.

We handle physical movement via backend CLI scripts (e.g., `simulate_vessel_arrival.py`) that naturally update the underlying physical stock tables. When the planner next generates a plan, the M2/M3 algorithms organically react to these script-injected physical realities.

## Strategy 8 - Use Contract Stubs To Unblock Platform

Outside-engine work should be able to move before the real engines are integrated.

- return contract-compatible stub outputs for `M1`, `M2`, and `M3` where needed
- keep API shapes stable so real engines can replace stubs without rewriting frontend or planner flow
- treat stubs as temporary platform scaffolding, not engine logic

## Technical Posture

- FastAPI orchestrates readers, engines, planner flow, and reporting
- Next.js provides the planner console
- MySQL 8 stores snapshots, decisions, audit, and demo-state data
- Docker-based local MySQL is the default MVP setup
- XGBoost supports M1 and the M3 ranker
- OR-Tools supports dispatch optimization

## Final Position

This MVP should feel modular, honest, and easy to explain:

- inputs are snapshots
- engines are pure
- planner is in control
- demo-state handles demo-only stock progression

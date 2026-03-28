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

## Strategy 2 - Treat Inputs as Snapshots

Use stable readers for operational inputs:

- `manifest_reader`
- `warehouse_stock_reader`
- `dc_stock_reader`
- `sales_history_reader`
- `lorry_state_reader`

Use `eta_provider` as the only mock API feed.

This keeps ingest simple and consistent: manifest is fetched the same way as warehouse and DC stock.

## Strategy 3 - Keep M3 Explainable

`M3` must stay split internally:

- optimizer generates feasible plans
- ranker scores likely planner acceptance

This keeps plan generation explainable and easier to debug.

## Strategy 4 - Narrow the MVP

The MVP stays intentionally small:

- 5 DCs
- 8 lorries
- maximum 2 stops per lorry
- fixed route graph
- planner-only UI

Smaller scope makes the dispatch output easier to trust and demo.

## Strategy 5 - Lock User Behavior

The planner can:

- review input snapshots
- review M1, M2, and M3 outputs
- edit lorry choice, stop order, and quantities before approval
- approve, reject, or override a plan

Once approved, that plan version is immutable.

## Strategy 6 - Keep Shared Semantics Simple

- use `quantity` for manifest, stock, requests, and plan items
- use `capacity_unit` for lorry capacity and feasibility
- show M1 line-level output and aggregated SKU summary
- keep later runs dependent on new snapshots, not hidden state inside engines

## Strategy 7 - Preserve Demo Credibility

The demo must visibly show:

1. ETA refresh
2. shortage/request generation
3. ranked plan candidates
4. planner approval
5. reservation creation
6. simulated warehouse-to-DC movement

The important rule is that only the demo-state module owns steps 5 and 6.

## Technical Posture

- FastAPI orchestrates readers, engines, planner flow, and reporting
- Next.js provides the planner console
- PostgreSQL stores snapshots, decisions, audit, and demo-state data
- XGBoost supports M1 and the M3 ranker
- OR-Tools supports dispatch optimization

## Final Position

This MVP should feel modular, honest, and easy to explain:

- inputs are snapshots
- engines are pure
- planner is in control
- demo-state handles demo-only stock progression

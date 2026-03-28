# Repository Structure

## Generated Layout

```text
pharma-availability-control-tower/
|-- README.md
|-- PROJECT_PLAN.md
|-- STRATEGY.md
|-- REPO_STRUCTURE.md
|-- PROGRESS.md
|-- apps/
|   |-- api/
|   |   |-- app/
|   |   |   |-- api/v1/
|   |   |   |-- orchestration/
|   |   |   |-- planner_flow/
|   |   |   |-- reporting/
|   |   |   `-- dependencies/
|   |   `-- tests/
|   `-- web/
|       |-- app/
|       |   |-- dashboard/
|       |   |-- inputs/
|       |   |-- priorities/
|       |   |-- requests/
|       |   |-- dispatch/
|       |   |-- history/
|       |   |-- demo-state/
|       |   `-- reports/
|       |-- components/
|       `-- lib/
|-- engines/
|   |-- m1_priority/
|   |   |-- contracts/
|   |   |-- features/
|   |   |-- training/
|   |   |-- inference/
|   |   `-- synthetic/
|   |-- m2_request/
|   |   |-- contracts/
|   |   |-- features/
|   |   |-- forecasting/
|   |   |-- inference/
|   |   `-- jobs/
|   `-- m3_dispatch/
|       |-- contracts/
|       |-- optimizer/
|       |   |-- model/
|       |   |-- solver/
|       |   `-- serializers/
|       |-- ranker/
|       |   |-- features/
|       |   |-- training/
|       |   |-- inference/
|       |   `-- synthetic/
|       `-- policies/
|-- demo_state/
|   |-- contracts/
|   |-- reservations/
|   |-- transfers/
|   |-- arrival_simulator/
|   |-- projections/
|   `-- audit/
|-- domain/
|   |-- entities/
|   |-- value_objects/
|   |-- enums/
|   |-- policies/
|   `-- events/
|-- integrations/
|   |-- inbound/
|   |   |-- manifest_reader/
|   |   |-- warehouse_stock_reader/
|   |   |-- dc_stock_reader/
|   |   |-- sales_history_reader/
|   |   |-- lorry_state_reader/
|   |   `-- eta_provider/
|   `-- outbound/
|       |-- approved_plan_export/
|       `-- demo_report_export/
|-- storage/
|   |-- snapshots/
|   |-- planner_decisions/
|   |-- engine_runs/
|   |-- demo_state/
|   `-- audit/
|-- data/
|   |-- seed/
|   `-- synthetic/
|       |-- m1/
|       `-- m3/
|-- db/
|   |-- migrations/
|   |-- seeds/
|   `-- queries/
|-- docs/
|   |-- uml/
|   |-- srs/
|   |-- architecture/
|   `-- demo/
|-- scripts/
`-- tests/
    |-- contract/
    |-- integration/
    `-- e2e/
```

## Why This Structure

- `engines/` contains pure M1, M2, and M3 logic only.
- `demo_state/` is the only place where demo reservation and stock-transfer simulation lives.
- `integrations/inbound/` makes manifest fetching look the same as warehouse/DC stock fetching.
- `apps/web/` stays planner-only.
- `apps/api/` orchestrates readers, engines, planner flow, and reporting without mixing engine logic into the API shell.

## Boundary Rules

- `engines/` read snapshots and emit outputs.
- `demo_state/` reacts to approved plans and updates demo projections.
- `storage/` keeps local snapshots, plan versions, audit data, and demo-state data.
- `integrations/outbound/` exports approved plans and demo reports without pretending to own enterprise workflows.

## Important Separation Inside M3

Keep these two parts separate:

- `engines/m3_dispatch/optimizer/` for feasible plan generation
- `engines/m3_dispatch/ranker/` for planner-acceptance or ranking logic

This is required for explainability and easier debugging.

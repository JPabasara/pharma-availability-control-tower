# Repository Structure

## Generated Layout

```text
pharma-availability-control-tower/
|-- README.md                   # project overview and product boundary
|-- PROJECT_PLAN.md             # MVP delivery plan and team split
|-- PLATFORM_DEMO_STATE_PLAN.md # detailed plan for all non-engine platform work
|-- STRATEGY.md                 # architecture and product strategy
|-- REPO_STRUCTURE.md           # repo map and folder responsibilities
|-- PROGRESS.md                 # current status and frozen decisions
|-- apps/                       # user-facing applications
|   |-- api/                    # FastAPI backend entry point
|   |   |-- app/                # backend application source
|   |   |   |-- api/v1/         # versioned HTTP routes
|   |   |   |-- orchestration/  # coordinates readers, stubs, engines, and outputs
|   |   |   |-- planner_flow/   # approval, rejection, override, and history flow
|   |   |   |-- reporting/      # report and export assembly
|   |   |   `-- dependencies/   # shared backend wiring helpers
|   |   `-- tests/              # backend-focused tests
|   `-- web/                    # planner console frontend
|       |-- app/                # frontend routes and pages
|       |   |-- dashboard/      # summary, alerts, and pending decisions
|       |   |-- inputs/         # read-only snapshot views
|       |   |-- priorities/     # M1 line scores and SKU summary
|       |   |-- requests/       # M2 request and urgency views
|       |   |-- dispatch/       # M3 plan comparison and draft editing
|       |   |-- history/        # approved versions and override trail
|       |   |-- demo-state/     # reservation and simulated transfer views
|       |   `-- reports/        # export and audit screens
|       |-- components/         # reusable UI pieces
|       `-- lib/                # frontend helpers and shared utilities
|-- engines/                    # pure decision engines only
|   |-- m1_priority/            # medicine priority scoring engine
|   |   |-- contracts/          # M1 input and output shapes
|   |   |-- features/           # M1 feature building logic
|   |   |-- training/           # M1 model training pipeline
|   |   |-- inference/          # M1 runtime scoring logic
|   |   `-- synthetic/          # M1 synthetic data generation
|   |-- m2_request/             # DC request generation engine
|   |   |-- contracts/          # M2 input and output shapes
|   |   |-- features/           # M2 feature preparation logic
|   |   |-- forecasting/        # demand and stock-out calculations
|   |   |-- inference/          # M2 runtime request generation
|   |   `-- jobs/               # scheduled M2 execution logic
|   `-- m3_dispatch/            # dispatch planning engine
|       |-- contracts/          # M3 input and output shapes
|       |-- optimizer/          # feasible plan generation from constraints
|       |   |-- model/          # decision variables and constraints
|       |   |-- solver/         # solver execution logic
|       |   `-- serializers/    # converts solver output into plans
|       |-- ranker/             # scores and orders candidate plans
|       |   |-- features/       # ranker feature building
|       |   |-- training/       # ranker training pipeline
|       |   |-- inference/      # ranker runtime scoring
|       |   `-- synthetic/      # synthetic plan feedback generation
|       `-- policies/           # dispatch rules shared inside M3
|-- demo_state/                 # demo-only stock movement simulation
|   |-- contracts/              # demo-state input and output shapes
|   |-- reservations/           # reservation state created on approval
|   |-- transfers/              # simulated warehouse-to-DC transfer logic
|   |-- arrival_simulator/      # deterministic arrival progression
|   |-- projections/            # post-approval stock and status views
|   `-- audit/                  # demo-state audit records
|-- domain/                     # shared business language
|   |-- entities/               # core business objects
|   |-- value_objects/          # constrained reusable domain values
|   |-- enums/                  # shared statuses and categories
|   |-- policies/               # business rules shared across modules
|   `-- events/                 # event names and payload concepts
|-- integrations/               # boundaries to external and mock sources
|   |-- inbound/                # reads inputs into the system
|   |   |-- manifest_reader/    # fetches vessel manifest snapshots
|   |   |-- warehouse_stock_reader/ # fetches warehouse stock snapshots
|   |   |-- dc_stock_reader/    # fetches DC stock snapshots
|   |   |-- sales_history_reader/ # fetches sales history snapshots
|   |   |-- lorry_state_reader/ # fetches lorry availability snapshots
|   |   `-- eta_provider/       # fetches vessel ETA from the mock API
|   `-- outbound/               # publishes outputs to downstream consumers
|       |-- approved_plan_export/ # exports approved plans
|       `-- demo_report_export/ # exports demo-state reports
|-- storage/                    # local persistence owned by this repo
|   |-- snapshots/              # stored input snapshots for replay and runs
|   |-- planner_decisions/      # approvals, rejections, and overrides
|   |-- engine_runs/            # saved engine outputs and run metadata
|   |-- demo_state/             # stored reservation and transfer state
|   `-- audit/                  # cross-cutting audit records
|-- data/                       # seed and synthetic data files
|   |-- seed/                   # deterministic demo input data
|   `-- synthetic/              # generated data for cold-start models
|       |-- m1/                 # M1 synthetic scenarios
|       `-- m3/                 # M3 synthetic plan feedback scenarios
|-- db/                         # MySQL setup assets
|   |-- migrations/             # schema changes for local MySQL persistence
|   |-- seeds/                  # database seed loaders or seed SQL
|   `-- queries/                # shared SQL queries and views
|-- docs/                       # supporting documentation
|   |-- uml/                    # UML diagrams
|   |-- srs/                    # software requirement specs
|   |-- architecture/           # architecture notes and decisions
|   `-- demo/                   # demo script and scenario notes
|-- scripts/                    # manual developer scripts and helpers
`-- tests/                      # cross-system test suites
    |-- contract/               # interface and schema tests
    |-- integration/            # multi-module integration tests
    `-- e2e/                    # full planner-flow scenario tests
```

## Boundary Rules

- `engines/` read snapshots and emit outputs; they never own stock mutation.
- `demo_state/` alone creates reservation state and simulates transfers for the demo.
- `integrations/inbound/` fetches manifests, stock, sales, lorry state, and ETA into the system.
- `apps/web/` is planner-only, and `apps/api/` orchestrates flows without containing engine logic.
- `apps/api/` may use contract-compatible stubs until the real engines are connected.

## Important Separation Inside M3

- `optimizer/` builds feasible dispatch plans from constraints.
- `ranker/` scores and orders those plans for planner review.
- Keeping them separate preserves explainability and easier debugging.

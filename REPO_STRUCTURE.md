# Repository Structure

This document reflects the cleaned, active repository layout. It is centered on the code paths that actually power the current product.

## Active Layout

```text
pharma-availability-control-tower/
|-- README.md
|-- PROJECT_PLAN.md
|-- REPO_STRUCTURE.md
|-- HOW_TO_RUN.md
|-- host_workflow.md
|-- Dockerfile
|-- docker-compose.yml
|-- render.yaml
|-- requirements.txt
|-- alembic.ini
|-- apps/
|   |-- api/
|   |   `-- app/
|   |       |-- api/v1/              # HTTP route groups
|   |       |-- dependencies/        # config, DB session, business time
|   |       |-- orchestration/       # M1/M2/M3 orchestration bridge and adapters
|   |       |   |-- real/            # ML-backed M1/M2/M3 adapters
|   |       |   `-- stubs/           # compatibility fallback adapters
|   |       |-- planner_flow/        # override, approve, reject, validation
|   |       |-- demo_operations/     # hosted operational actions
|   |       `-- input_refresh/       # input family refresh services
|   `-- web/
|       |-- app/                     # Next.js routes and pages
|       |-- components/              # reusable UI components
|       `-- lib/                     # API client, formatters, shared types
|-- integrations/
|   `-- inbound/                     # readers for manifests, stock, sales, ETAs, lorries
|-- storage/
|   |-- models/                      # SQLAlchemy models
|   |-- snapshots/
|   |-- planner_decisions/
|   |-- engine_runs/
|   |-- demo_state/
|   `-- audit/
|-- ml/
|   |-- datasets/                    # synthetic dataset generation and CSVs
|   `-- models/
|       |-- artifacts/               # committed model outputs and model files
|       |-- m1_model.py              # mathematical prioritization model
|       |-- m2_model.py              # XGBoost request generator
|       `-- m3_model.py              # OR-Tools dispatch planner
|-- data/
|   `-- seed/                        # deterministic business seed data
|-- db/
|   |-- migrations/                  # Alembic migrations
|   `-- seeds/                       # database seed entrypoints
|-- docs/
|   |-- submission/                  # submission-facing documentation
|   |-- srs/                         # preserved reference PDFs
|   `-- uml/                         # preserved UML PDFs
|-- scripts/
|   |-- reset_db.py                  # drop, migrate, reseed local DB
|   |-- drop_tables.py
|   |-- simulate_vessel_arrival.py
|   `-- simulate_lorry_arrival.py
`-- tests/
    |-- contract/
    |-- integration/
    |-- e2e/
    `-- csv/
```

## Runtime Boundaries

- `apps/api/app` owns the backend application and orchestration flow.
- `apps/web` owns the planner-facing frontend.
- `integrations/inbound` is responsible for reading source data into the platform.
- `storage/models` defines the database-backed business state and audit entities.
- `ml/models` contains the model logic and committed artifacts used by the real adapters.
- `db/migrations` and `db/seeds` define schema and demo data setup.

## Planner Routes

The planner console exposes these main pages:

- `/dashboard`
- `/inputs`
- `/requests`
- `/priorities`
- `/dispatch`
- `/history`
- `/demo-state`
- `/reports`

The `/demo-state` route is intentionally kept for compatibility, while the UI label is `Demo Operations`.

## API Route Groups

The backend is organized into these route families:

- `/api/v1/inputs/*`
- `/api/v1/orchestration/*`
- `/api/v1/planner/*`
- `/api/v1/demo-state/*`
- `/api/v1/demo-operations/*`
- `/api/v1/reports/*`
- `/api/v1/mock/eta/*`

## Notes On The Cleaned Repo

- Placeholder-only `engines/` and `domain/` folders were removed because they were not part of the active runtime.
- Stub bridge code remains inside `apps/api/app/orchestration/stubs` for compatibility, but the intended submission path is the ML-backed flow under `apps/api/app/orchestration/real`.

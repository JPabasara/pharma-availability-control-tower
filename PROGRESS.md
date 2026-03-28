# Progress

## Current Status

- scope and repo boundaries are frozen
- docs aligned to the engine-first architecture
- repo skeleton generated with empty tracked directories
- platform plan extended for local MySQL, integrations, demo-state, and engine stubs

## Locked Decisions

- manifests are fetched through `manifest_reader`
- warehouse, DC, sales, and lorry data are fetched through snapshot readers
- ETA comes from the mock API
- MySQL 8 is the local MVP database, with Docker as the default setup
- `M1`, `M2`, and `M3` are pure engines
- contract-compatible stubs may be used until the real engines are connected
- `demo_state` alone handles demo reservation and stock movement
- planner is the only frontend user
- approved plan versions are immutable

## Planning Docs

- `PLATFORM_DEMO_STATE_PLAN.md` owns the non-engine platform implementation plan


## Not Started Yet

- engine implementation
- frontend implementation
- demo-state implementation
- API contracts and persistence models

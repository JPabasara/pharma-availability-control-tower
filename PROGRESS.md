# Progress

## Current Status

- scope and repo boundaries are frozen
- docs aligned to the engine-first architecture
- repo skeleton generated with empty tracked directories

## Locked Decisions

- manifests are fetched through `manifest_reader`
- warehouse, DC, sales, and lorry data are fetched through snapshot readers
- ETA comes from the mock API
- `M1`, `M2`, and `M3` are pure engines
- `demo_state` alone handles demo reservation and stock movement
- planner is the only frontend user
- approved plan versions are immutable

## Not Started Yet

- engine implementation
- frontend implementation
- demo-state implementation
- API contracts and persistence models

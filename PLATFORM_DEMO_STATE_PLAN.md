# Platform Demo State Plan

## Purpose

This plan covers everything outside `M1`, `M2`, and `M3`:

- local MySQL setup
- snapshot storage
- integration readers
- ETA mock API
- planner backend flow
- demo-state simulation
- planner frontend pages
- seeded demo data
- contract stubs for engine outputs

`M1`, `M2`, and `M3` remain separate pure engines. This plan prepares their inputs, stores their outputs, and keeps the planner workflow usable before the real engines are plugged in.

## Platform Defaults

- Database: `MySQL 8`
- Local database mode: Docker-first on the developer laptop
- ORM and migrations: `SQLAlchemy 2.x`, `Alembic`, `PyMySQL`
- Database shape: one local database named `control_tower_mvp`
- Storage rules:
  - inputs are read on-demand
  - approved plan versions are immutable
  - effective stock perfectly reconciles physical DB inventory with approved plan reservations/in-transit records
- Bridge rule: contract-compatible stubs may stand in for `M1`, `M2`, and `M3` until the real engines are connected

## Sequential Delivery Steps

### 1. Freeze the platform boundary
- keep `M1`, `M2`, and `M3` outside this workstream
- own only integrations, persistence, orchestration, planner flow, demo-state, and frontend
- replace all remaining PostgreSQL assumptions with MySQL

### 2. Set up local MySQL
- create `docker-compose.yml` with one `mysql` service
- use image `mysql:8`
- expose port `3306`
- create database `control_tower_mvp`
- create one app user and one root password
- mount a named Docker volume for persistence
- standardize on `utf8mb4`, `InnoDB`, and UTC timestamps

### 3. Add environment and backend DB wiring
- define `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD`, and `MYSQL_ROOT_PASSWORD`
- define an application DSN using `mysql+pymysql://`
- put engine and session wiring inside `apps/api/app/dependencies/`
- make the same session wiring reusable for integrations, planner flow, reporting, and demo-state services

### 4. Create the persistence model
- create master tables: `skus`, `dcs`, `lorries`, `route_edges`, `vessels`
- create snapshot tables:
  - `manifest_snapshots`, `manifest_lines`
  - `warehouse_stock_snapshots`, `warehouse_stock_items`
  - `dc_stock_snapshots`, `dc_stock_items`
  - `sales_history_records`
  - `lorry_state_snapshots`, `lorry_state_items`
  - `eta_snapshots`
- create engine run storage:
  - `engine_runs`
  - `m1_results`
  - `m2_requests`
  - `m3_plan_versions`, `m3_plan_stops`, `m3_plan_items`
- create planner-flow storage:
  - `planner_decisions`
  - `override_reasons`
- create demo-state storage:
  - `demo_reservations`
  - `demo_transfers`
  - `demo_arrival_events`
  - `demo_stock_projections`
- create `audit_logs`
- add indexes on timestamps, vessel IDs, SKU IDs, DC IDs, lorry IDs, plan version IDs, and approval status

### 5. Add migrations and seed flow
- initialize Alembic for MySQL
- create an initial migration that builds the full schema
- add repeatable seed scripts for master data and demo scenarios
- make reset and reseed possible for laptop demos

### 6. Seed deterministic demo data
- seed 15 SKUs, 5 DCs, 8 lorries, route graph, vessel master data, warehouse stock, DC stock, and sales history
- seed at least 2 vessel manifests
- prepare 3 deterministic scenarios:
  - overlapping vessels
  - urgent DC shortage
  - fleet limitation with reefer pressure

### 7. Build inbound snapshot readers ("Effective" Engine)
- implement `manifest_reader`
- implement `warehouse_stock_reader` (Calculates: Physical - Reserved)
- implement `dc_stock_reader` (Calculates: Physical + In-Transit)
- implement `sales_history_reader` (Calculates 48-hour shortage forecast)
- implement `lorry_state_reader` (Exposes simple binary Available/Unavailable states)
- each reader must support:
  - executing immediately on planner "Generate Plan" clicks
  - returning normalized engine-ready contracts
  - normalize raw storage rows into engine-ready contracts

### 8. Build the ETA mock API and provider
- implement `eta_provider` as the only mock API feed
- keep its boundary separate even if it lives inside the same FastAPI app for MVP simplicity
- store every ETA fetch in `eta_snapshots`
- support repeated refresh for demo use through a manual endpoint or scheduled trigger

### 9. Build orchestration for engine-ready inputs
- assemble exact input contracts for `M1`, `M2`, and `M3` from stored snapshots
- persist every run with source snapshot IDs for traceability
- keep route graph as local reference data
- expose orchestration services that the planner API can call directly

### 10. Add engine stubs
- create contract-compatible stub providers for `M1`, `M2`, and `M3`
- make stubs return the same shapes the real engines will return later
- back stubs with deterministic fixtures so frontend and planner flow can be built immediately
- keep a clean switch so stubs can be replaced by real engines without changing API routes or frontend screens

### 11. Build planner backend APIs
- add read APIs for:
  - dashboard summary
  - input snapshots
  - M1 result views
  - M2 request views
  - M3 candidate plans
  - history
  - demo-state views
  - reports
- add planner actions for:
  - approve plan version
  - reject plan version
  - override and validate (runs strict Math-Bound Check: capacity <= lorry.capacity, quantity <= effective_wh_stock)
- enforce immutability strictly on approved plans

### 12. Build Demo CLI Simulation Scripts
Instead of complex UIs, physical time moves forward via developer CLI running against local DB:
- `python scripts/simulate_vessel_arrival.py` -> reads active manifests, increments physical WH DB, drops manifest.
- `python scripts/simulate_lorry_arrival.py` -> finds active "In Transit", increments physical DC DB, drops WH reservation.
This cleanly separates engine planning logic from physical inventory updates.

### 13. Build the planner frontend sequentially
- build `Dashboard` first
- build `Inputs` second
- build `M1 Priorities`, `M2 Requests`, and `M3 Dispatch` against stub outputs
- add dispatch actions for compare, approve, reject, and override
- build `History`
- build `Demo State`
- build `Reports` last

### 14. Add reporting and exports
- add approved-plan export views
- add demo-state report views
- add audit views tying together snapshots, engine runs, plan versions, decisions, and demo-state events

### 15. Harden the developer workflow
- add commands or scripts to:
  - start MySQL
  - run migrations
  - seed demo data
  - run API
  - run frontend
  - refresh ETA
  - simulate arrivals
- make full reset and replay fast for live demo use

### 16. Update and keep docs aligned
- replace PostgreSQL references with MySQL in current planning docs
- note Docker-based local MySQL as the default setup
- note that platform work includes engine stubs until real engines are connected

## MySQL Implementation Guide

### Local runtime
- run MySQL in Docker for the default MVP workflow
- use one persistent named volume so data survives container restarts
- keep the app and MySQL on the same Docker network when containerized together

### Application connection
- use `PyMySQL` with SQLAlchemy
- use a DSN in this pattern:
  - `mysql+pymysql://<user>:<password>@<host>:3306/control_tower_mvp?charset=utf8mb4`
- create sessions in the backend dependency layer, not inside route handlers

### Migrations
- use Alembic from day 1
- keep one baseline migration for the initial schema, then incremental migrations for changes
- make migration names match business intent, not only timestamps

### Table design rules
- prefer surrogate integer or UUID primary keys consistently
- use foreign keys between snapshots, plan versions, planner decisions, and demo-state tables
- store created timestamps in UTC
- use explicit status columns for plan state, transfer state, and reservation state
- add indexes for every common lookup path used by readers and planner screens

### Local operations
- start DB: `docker compose up -d mysql`
- run migrations after DB boot
- seed data after migrations
- use reset/reseed scripts so the same scenarios can be replayed reliably on your laptop

## Interfaces To Lock

### Snapshot readers
- fetch latest snapshot
- fetch snapshot by id or time
- normalize into engine-ready contract

### ETA provider
- fetch latest ETA for vessel
- persist ETA snapshot

### Engine bridge
- call stub provider now
- call real engine later
- keep API response shapes unchanged

### Planner actions
- approve
- reject
- override into new draft version

### Demo-state services
- create reservations
- create transfers
- simulate arrival
- return stock projections

## Planner API Groups

- `/api/v1/inputs/*`
- `/api/v1/orchestration/*`
- `/api/v1/planner/*`
- `/api/v1/demo-state/*`
- `/api/v1/reports/*`
- `/api/v1/mock/eta/*`

## Acceptance Checklist

- [ ] MySQL boots locally from Docker and the app connects via env vars
- [ ] migrations create the full schema in a fresh database
- [ ] seeds populate the deterministic MVP scenarios
- [ ] each snapshot reader supports latest and historical fetches
- [ ] ETA refresh stores new ETA snapshots
- [ ] orchestration builds correct input contracts for `M1`, `M2`, and `M3`
- [ ] stub outputs match the intended engine contracts
- [ ] planner approval freezes a plan version
- [ ] override creates a new draft version
- [ ] approval creates demo reservations and transfers
- [ ] arrival simulation updates projected warehouse and DC stock
- [ ] dashboard, inputs, dispatch, history, demo-state, and reports all work against local MySQL-backed data
- [ ] the demo can be reset and replayed on one laptop

Full Platform Build — Implementation Plan
Goal
Build the entire outer system (steps 7–15 from PLATFORM_DEMO_STATE_PLAN.md) with M1/M2/M3 as contract-compatible stubs. After this, the real engines can replace stubs without touching APIs or frontend.

Completed previously: Docker MySQL, SQLAlchemy models (28 tables), Alembic migration, seed data, reset scripts.

User Review Required
IMPORTANT

Frontend Approach: The plan specifies Next.js. Given this is a single-planner internal tool, I recommend using Next.js App Router with the API calls going to FastAPI at localhost:8000. This gives us server components and a clean page layout. Confirm this is acceptable.

IMPORTANT

Scope Prioritization: This is a large build. I plan to execute in 4 macro-phases in this order:

Backend Services (readers, stubs, orchestration, planner flow, demo-state)
FastAPI Routes (all /api/v1/* endpoints)
Demo CLI Scripts (simulate_vessel_arrival, simulate_lorry_arrival)
Next.js Frontend (all 8 planner pages)
Each phase is independently usable. Approve this order?

Architecture Overview
┌─────────────────────────────────────────────────────────────┐
│                 Next.js Frontend (port 3000)                │
│  Dashboard │ Inputs │ M1 │ M2 │ M3 │ History │ Demo │ Rpts │
└─────────────────────────┬──────────────────────~─────────────┘
                          │ HTTP
┌─────────────────────────▼───────────────────────────────────┐
│              FastAPI Backend (port 8000)                     │
│  /api/v1/inputs/*  /api/v1/orchestration/*                  │
│  /api/v1/planner/* /api/v1/demo-state/*                     │
│  /api/v1/reports/* /api/v1/mock/eta/*                       │
├─────────────────────────────────────────────────────────────┤
│  Orchestration Layer                                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐                    │
│  │ M1 Stub  │ │ M2 Stub  │ │ M3 Stub  │  (swappable)      │
│  └──────────┘ └──────────┘ └──────────┘                    │
│  Snapshot Readers │ ETA Provider │ Planner Flow │ Demo State│
├─────────────────────────────────────────────────────────────┤
│              MySQL 8 (port 3307)                            │
│  28 tables: masters, snapshots, engine_runs, planner, demo  │
└─────────────────────────────────────────────────────────────┘
Proposed Changes
Macro-Phase A — Backend Services (~20 files)
Component 1: Snapshot Readers
5 readers under integrations/inbound/, each with the same pattern:

get_latest() — fetches most recent snapshot
get_by_id(snapshot_id) — fetches specific snapshot
to_contract() — normalizes into engine-ready dict
[NEW] integrations/inbound/manifest_reader/reader.py
Reads manifest_snapshots + joined manifest_lines + skus
Returns {vessel_id, vessel_name, status, lines: [{sku_id, sku_code, quantity, reefer_required}]}
[NEW] integrations/inbound/warehouse_stock_reader/reader.py
Reads warehouse_stock_items from latest snapshot
Computes Effective = Physical − Reserved (sums active demo_reservations)
Returns {snapshot_id, snapshot_time, items: [{sku_id, sku_code, physical, reserved, effective}]}
[NEW] integrations/inbound/dc_stock_reader/reader.py
Reads dc_stock_items from latest snapshot per DC
Computes Effective = Physical + In-Transit (sums active demo_transfers)
Returns {dc_id, dc_code, items: [{sku_id, sku_code, physical, in_transit, effective}]}
[NEW] integrations/inbound/sales_history_reader/reader.py
Reads sales_history_records for last 7 days
Computes 48-hour forecast per DC per SKU (avg daily × 2)
Returns {dc_id, sku_id, daily_avg, forecast_48h}
[NEW] integrations/inbound/lorry_state_reader/reader.py
Reads lorry_state_items from latest snapshot + lorries master
Returns {lorries: [{id, registration, type, capacity, status}]}
Component 2: ETA Mock Provider
[NEW] integrations/inbound/eta_provider/provider.py
get_latest_eta(vessel_id) — returns latest ETA snapshot
refresh_eta(vessel_id) — generates mock ETA (current time + random 4-48h offset), persists to eta_snapshots
get_all_active_etas() — returns ETAs for all active vessels
Component 3: Engine Stubs (Contract-Compatible)
Each stub lives under apps/api/app/orchestration/stubs/ with an interface that the real engine will implement.

[NEW] apps/api/app/orchestration/stubs/init.py
[NEW] apps/api/app/orchestration/stubs/m1_stub.py
Input: manifest lines, warehouse stock, M2 requests, SKU metadata, ETA
Output: deterministic priority scores based on simple heuristics:
reefer SKUs get +30 score bonus
low WH stock (< 1000) → critical
medium WH stock (< 3000) → high
else medium/low based on ETA proximity
Returns list of {manifest_line_id, sku_id, priority_score, priority_band, reefer_required}
[NEW] apps/api/app/orchestration/stubs/m2_stub.py
Input: effective DC stock, 48h sales forecast
Output: deterministic requests:
If forecast_48h > effective_dc_stock → generate request
Urgency: critical if stock covers < 12h, high if < 24h, medium if < 36h, low otherwise
Returns list of {dc_id, sku_id, requested_quantity, urgency, required_by}
[NEW] apps/api/app/orchestration/stubs/m3_stub.py
Input: M1 output, M2 output, WH stock, lorry state, route graph
Output: 3 candidate plans, each assigning available lorries to DCs:
Plan A: prioritize critical DCs (best plan, marked is_best)
Plan B: balanced distribution
Plan C: minimize travel cost
Each plan: {version_number, score, is_best, stops: [{lorry_id, dc_id, stop_sequence, items: [{sku_id, quantity}]}]}
Respects: 1 trip per lorry, max 2 stops, reefer lorries → reefer SKUs only, normal → normal only
[NEW] apps/api/app/orchestration/engine_bridge.py
Abstract interface: run_m1(), run_m2(), run_m3()
Config switch: ENGINE_MODE=stub or ENGINE_MODE=real (env var)
Currently routes to stubs; later swappable to real engines
Component 4: Orchestration Service
[NEW] apps/api/app/orchestration/service.py
generate_plan(session) — the main flow triggered by "Generate Plan":
Snapshot all inputs (readers)
Run M2 stub → persist engine_run + m2_requests
Run M1 stub → persist engine_run + m1_results
Run M3 stub → persist engine_run + m3_plan_versions/stops/items
Return orchestration result with all run IDs
Component 5: Planner Flow Service
[NEW] apps/api/app/planner_flow/service.py
approve_plan(plan_version_id):
Validate plan is draft
Freeze as approved, set approved_at
Create demo_reservations for all plan items (WH side)
Create demo_transfers for all plan stops (DC side, status=in_transit)
Log planner_decision + audit_log
reject_plan(plan_version_id, notes):
Mark as rejected
Log decision
override_plan(plan_version_id, changes):
Run math-bound validation
Create new draft version with changes applied
Log override_reasons
[NEW] apps/api/app/planner_flow/validation/math_bound.py
Validates overrides:
total_load ≤ lorry.capacity_units for each lorry
quantity ≤ effective_wh_stock for each SKU
Reefer lorry → only reefer SKUs, normal → only normal
Returns {valid: bool, errors: [...]}
Component 6: Demo State Service
[NEW] demo_state/services.py
get_reservations(plan_version_id?) — list active/all reservations
get_transfers(status?) — list transfers by status
get_stock_summary() — current effective stock view
Macro-Phase B — FastAPI Routes (~10 files)
[NEW] apps/api/app/main.py
FastAPI app with CORS middleware (allow localhost:3000)
Include all router groups
[NEW] apps/api/app/api/v1/inputs.py
GET /api/v1/inputs/manifests — all active manifests
GET /api/v1/inputs/manifests/{id} — specific manifest
GET /api/v1/inputs/warehouse-stock — latest effective WH stock
GET /api/v1/inputs/dc-stock — latest effective DC stock (all DCs)
GET /api/v1/inputs/dc-stock/{dc_id} — specific DC stock
GET /api/v1/inputs/sales-history — sales history with 48h forecasts
GET /api/v1/inputs/lorry-state — current lorry availability
GET /api/v1/inputs/etas — all active ETAs
[NEW] apps/api/app/api/v1/orchestration.py
POST /api/v1/orchestration/generate-plan — trigger full pipeline
GET /api/v1/orchestration/runs — list engine runs
GET /api/v1/orchestration/runs/{id} — specific run details
[NEW] apps/api/app/api/v1/planner.py
GET /api/v1/planner/m1-results/{run_id} — M1 line scores + SKU summary
GET /api/v1/planner/m2-requests/{run_id} — M2 requests
GET /api/v1/planner/m3-plans/{run_id} — M3 candidate plans
GET /api/v1/planner/m3-plans/{run_id}/{version_id} — specific plan detail
POST /api/v1/planner/approve/{plan_version_id} — approve plan
POST /api/v1/planner/reject/{plan_version_id} — reject plan
POST /api/v1/planner/override/{plan_version_id} — override + validate
[NEW] apps/api/app/api/v1/demo_state.py
GET /api/v1/demo-state/reservations — active reservations
GET /api/v1/demo-state/transfers — transfers by status
GET /api/v1/demo-state/stock-summary — aggregated stock view
[NEW] apps/api/app/api/v1/reports.py
GET /api/v1/reports/approved-plans — all approved plans with details
GET /api/v1/reports/audit-trail — audit log entries
[NEW] apps/api/app/api/v1/mock_eta.py
POST /api/v1/mock/eta/refresh/{vessel_id} — refresh ETA for vessel
GET /api/v1/mock/eta/latest — all latest ETAs
[NEW] apps/api/app/api/v1/dashboard.py
GET /api/v1/dashboard/summary — aggregated dashboard data:
pending approvals count
critical alerts (low stock DCs, reefer pressure)
latest engine run info
active manifests count
Macro-Phase C — Demo CLI Scripts (~2 files)
[NEW] scripts/simulate_vessel_arrival.py
Reads active manifests → increments physical WH stock → marks manifest as arrived
Creates demo_arrival_event
[NEW] scripts/simulate_lorry_arrival.py
Finds in_transit transfers → increments physical DC stock → releases WH reservations
Marks transfers as arrived, creates demo_arrival_event
Macro-Phase D — Next.js Frontend (~25 files)
Initialize a Next.js app under apps/web/ with App Router.

Shared Infrastructure
[NEW] apps/web/lib/api.ts — fetch wrapper for localhost:8000
[NEW] apps/web/components/Layout.tsx — sidebar nav + header
[NEW] apps/web/components/DataTable.tsx — reusable sortable table
[NEW] apps/web/components/StatusBadge.tsx — urgency/status pills
[NEW] apps/web/components/StatsCard.tsx — metric cards
[NEW] apps/web/app/globals.css — design system (dark mode, gradients, animations)
Pages (8 views from PLATFORM_DEMO_STATE_PLAN.md step 13)
[NEW] apps/web/app/page.tsx — redirects to dashboard
[NEW] apps/web/app/dashboard/page.tsx — alerts, pending approvals, latest runs, stock warnings
[NEW] apps/web/app/inputs/page.tsx — tabbed view: manifests, WH stock, DC stock, sales, lorries, ETAs
[NEW] apps/web/app/priorities/page.tsx — M1 line-level scores table + aggregated SKU summary
[NEW] apps/web/app/requests/page.tsx — M2 DC requests with urgency highlighting
[NEW] apps/web/app/dispatch/page.tsx — M3 plan comparison, "Generate Plan" button, approve/reject/override actions
[NEW] apps/web/app/history/page.tsx — immutable approved versions, override trail
[NEW] apps/web/app/demo-state/page.tsx — reservations, in-transit transfers, stock projections
[NEW] apps/web/app/reports/page.tsx — approved plan exports, audit trail
Open Questions
IMPORTANT

Frontend styling: Next.js with vanilla CSS dark theme — good approach? Or do you want Tailwind?
Engine mode switch: Should I support a simple env var (ENGINE_MODE=stub) to swap stubs for real engines later? (Recommended yes)
Execution order: Shall I start immediately after your approval, building backend first then frontend? The plan is large but each component is individually testable.
Verification Plan
Automated Tests
Start FastAPI: .venv\Scripts\uvicorn apps.api.app.main:app --reload --port 8000
Test all API endpoints via browser or curl
Test orchestration: POST /api/v1/orchestration/generate-plan → verify M1/M2/M3 results stored
Test planner flow: approve → verify reservations/transfers created, plan immutable
Test simulation scripts: run both CLI scripts → verify stock changes
Start Next.js: cd apps/web && npm run dev → verify all 8 pages render with data
Manual Verification
Full demo flow: Generate → Review → Override → Approve → Simulate → Verify stock
Reset: python scripts/reset_db.py → replay entire flow
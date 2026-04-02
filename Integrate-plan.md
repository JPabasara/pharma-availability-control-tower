# Integration Master Plan

## Goal
Integrate the real `M1`, `M2`, and `M3` model work from `branch_Jay` into the current main-based backend/platform without breaking the existing planner-facing API, frontend, planner flow, or demo-state behavior.

## Current Baseline
- The current planner system is already wired around stable stub contracts.
- The current orchestration path is `M2 -> M1 -> M3`.
- The current planner/API/frontend already consume:
  - `M1` line-level priority results plus SKU summary.
  - `M2` replenishment requests with categorical urgency.
  - `M3` candidate plan versions persisted as:
    - `m3_plan_versions`
    - `m3_plan_runs`
    - `m3_plan_stops`
    - `m3_plan_items`
- The current planner workflow for approve/reject/override depends on the run/day/stop schema and must not be broken.
- Deployment currently has a single global env switch: `ENGINE_MODE=stub`.

## Decisions Already Taken
1. The existing planner/API contract remains the source of truth.
   - We will adapt real models to the platform.
   - We will not redesign the frontend around model-native CSV outputs.

2. `M1` is planner-facing only.
   - `M1` must no longer feed `M3`.
   - `M3` should run from canonical operational inputs plus `M2`, not from `M1`.

3. `M3` must continue to return 3 candidate plan versions.
   - The planner UI and workflow depend on comparing alternatives.
   - The single-plan OR-Tools solver must be adapted into a 3-version strategy.

4. Runtime identifiers must match the backend/business system.
   - Canonical runtime identifiers will be:
     - SKU: backend SKU code / DB SKU row
     - DC: backend DC code / DB DC row
     - Lorry: backend registration / DB lorry row
   - Synthetic identifiers like `SKU-005`, `DC-03`, `L-01` will not remain the runtime contract.

5. Feature sourcing will be hybrid.
   - Derive features from current snapshots/readers where possible.
   - Add schema only for fields that must be persisted, audited, debugged, or reused.

6. Database persistence will keep both:
   - normalized planner-facing data
   - raw model trace / score metadata

7. Rollout must be per-engine, not global.
   - We need `M2` first, then `M1`, then `M3`.
   - Therefore we must replace the single global engine switch with per-engine mode flags.

## Key Mismatches Identified

### M1 Real Model vs Current Contract
Current contract expects:
- input:
  - manifest lines
  - warehouse stock
  - M2 requests
  - SKU metadata
  - ETA data
- output:
  - `manifest_line_id`
  - `sku_id`
  - `sku_code`
  - `priority_score`
  - `priority_band`
  - `reefer_required`

Real model currently expects a synthetic CSV with fields like:
- `category`
- `manifest_quantity`
- `wh_days_of_cover`
- `eta_delay_hours`
- `max_m2_urgency`
- `m2_fulfillment_ratio`

Real model currently outputs:
- synthetic/string manifest IDs
- synthetic/string SKU IDs
- uppercase bands (`HIGH`, `MEDIUM`, `LOW`)
- extra score explanation text

Conclusion:
- `M1` needs a runtime feature-builder adapter.
- `M1` needs output normalization back to planner contract.
- `M1` needs canonical backend identifiers, not synthetic ones.

### M2 Real Model vs Current Contract
Current contract expects:
- input:
  - effective DC stock
  - 48h forecast
- output:
  - `dc_id`
  - `dc_code`
  - `sku_id`
  - `sku_code`
  - `requested_quantity`
  - `urgency`
  - `required_by`

Real model currently expects many richer ML features:
- `physical_stock`
- `in_transit_stock`
- `effective_stock`
- `avg_daily_sales`
- `sales_trend_7d`
- `projected_daily_sales`
- `hourly_sales`
- `safety_stock`
- `stock_to_sales_ratio`
- `days_of_cover`
- `day_of_week`
- `is_weekend`
- `hour_of_day`
- `lead_time_hours`
- `category`

Real model currently outputs:
- synthetic/string DC and SKU identifiers
- `urgency_score`
- `shortage_probability`
- `hours_until_shortage`
- `requested_quantity`
- no categorical urgency band
- no `required_by`

Conclusion:
- `M2` needs a runtime inference wrapper around committed model artifacts.
- `M2` needs canonical feature generation from live DB/readers.
- `M2` needs normalized urgency band + `required_by`.
- `M2` should also persist raw prediction trace fields.

### M3 Real Model vs Current Contract
Current contract expects:
- 3 candidate plan versions
- persisted plan version -> run -> stop -> item hierarchy
- day-based lorry usage
- planner-editable structure
- compatibility with approve/reject/override/validation/demo-state

Real model currently:
- reads CSV files
- consumes synthetic identifiers
- solves one OR-Tools optimization output
- returns line-level dispatch allocations only
- does not produce:
  - candidate plan versions
  - run/day grouping contract
  - plan ranking metadata
  - planner workflow metadata

Conclusion:
- `M3` needs a runtime solver adapter.
- `M3` needs a candidate-plan generation strategy.
- `M3` must preserve current persistence and planner-flow shape.

## Target Integration Architecture

## Runtime Mode Switching
Replace the current single switch:
- `ENGINE_MODE=stub|real`

With per-engine switches:
- `M1_ENGINE_MODE=stub|real`
- `M2_ENGINE_MODE=stub|real`
- `M3_ENGINE_MODE=stub|real`

Compatibility rule:
- If per-engine flag is absent, fall back to `ENGINE_MODE`.
- This allows phased rollout without breaking existing environments.

## Engine Invocation Order
Target orchestration order:
1. Read canonical inputs.
2. Run `M2`.
3. Run `M1`.
4. Run `M3`.

Important dependency change:
- `M1` still uses `M2` output as an input.
- `M3` does not use `M1` output anymore.

## Canonical Runtime Data Model
At runtime, real engines must consume backend-normalized objects built from current readers and master data.

Canonical lookup sources:
- SKU master
- DC master
- lorry master
- route graph
- warehouse stock snapshot
- DC stock snapshots
- manifest snapshots
- ETA snapshots
- lorry day-state overlays

Canonicalization rule:
- The platform owns ID/code mapping.
- Real model code must adapt to platform identifiers, not the reverse.

## Adapter Layer Responsibilities
The adapter layer for each engine will do 4 things:
1. Build live runtime features from DB-backed contracts.
2. Convert live business IDs/codes into the exact shapes the model logic needs.
3. Normalize model-native outputs back into planner contract format.
4. Emit raw trace metadata for persistence/debugging.

## Database Changes

## Keep Existing Planner Tables
These remain the normalized planner-facing source for APIs:
- `m1_results`
- `m2_requests`
- `m3_plan_versions`
- `m3_plan_runs`
- `m3_plan_stops`
- `m3_plan_items`

## Add Traceability Fields
Recommended additive schema changes:

### `engine_runs`
Add:
- `engine_mode` - `stub` or `real`
- `engine_impl` - implementation label such as `stub`, `m2_xgboost_v1`, `m3_ortools_v1`
- `engine_version` - model/build version string
- `engine_trace` - JSON metadata about feature generation / solver execution

Purpose:
- audit
- debugging
- rollout comparison
- model version traceability

### `m1_results`
Add:
- `score_breakdown` - text or JSON
- `raw_features` - JSON snapshot of derived M1 features used at run time

Purpose:
- planner explainability
- debugging of score disputes
- future tuning without recomputing old runs

### `m2_requests`
Add:
- `urgency_score`
- `shortage_probability`
- `hours_until_shortage`
- `effective_stock_at_run`
- `projected_48h_sales`
- `safety_stock`
- `raw_features` - JSON

Purpose:
- preserve real-model signal
- keep current API contract intact
- allow future UI/reporting upgrades without re-running the model

### `m3_plan_versions`
Add:
- `plan_name`
- `generation_strategy`
- `objective_value`
- `solver_trace` - JSON summary

Purpose:
- preserve which variant produced each candidate
- support debugging of candidate-plan ranking

## Explicit Non-Goals
- No frontend redesign during integration.
- No planner API breaking change during initial integration.
- No runtime dependence on synthetic CSV datasets.
- No runtime retraining inside orchestration.
- No replacement of current planner-flow approval/override mechanics.

## Assumptions
1. Committed model artifacts stay in-repo for this integration phase.
   - `M2` loads committed XGBoost JSON artifacts at runtime.
   - `M1` is a deterministic mathematical engine.
   - `M3` is a deterministic OR-Tools engine.

2. Synthetic datasets remain development-only.
   - They are not the production runtime source.
   - They may still be kept for local experimentation or model evolution.

3. `M1` band mapping must be normalized to current planner vocabulary:
   - assumed default:
     - `score >= 90` -> `critical`
     - `score >= 70` -> `high`
     - `score >= 40` -> `medium`
     - otherwise `low`

4. `M2` urgency normalization must produce current contract categories:
   - assumed default:
     - `urgency_score >= 75` -> `critical`
     - `urgency_score >= 50` -> `high`
     - `urgency_score >= 25` -> `medium`
     - otherwise `low`

5. `required_by` remains derived from urgency band:
   - `critical`: now + 12h
   - `high`: now + 24h
   - `medium`: now + 36h
   - `low`: now + 48h

6. `M3` candidate versions will be generated as:
   - Plan A: urgency-maximizing variant, marked `is_best`
   - Plan B: balanced coverage variant
   - Plan C: cost-aware / travel-aware variant

## Acceptance Criteria
- Existing planner endpoints remain response-compatible.
- The frontend pages continue to load without mandatory redesign.
- `M1` is visible to planners and no longer used as `M3` input.
- `M2` runs from live DB-backed inputs and persists normalized plus raw trace output.
- `M3` persists 3 candidate plans into the current version/run/stop/item schema.
- Planner approve/reject/override continues to work with real `M3` plans.
- Per-engine rollout and rollback can be done using environment variables only.

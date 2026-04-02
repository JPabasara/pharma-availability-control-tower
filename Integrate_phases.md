# Integration Phases and Deployment Plan

## Rollout Principle
This integration will be deployed engine-by-engine in this order:
1. Phase 0: shared preparation
2. Phase 1: `M2` real integration first
3. Phase 2: `M1` real integration second
4. Phase 3: `M3` real integration last
5. Phase 4: hardening and cleanup

This order is intentional:
- `M2` is the easiest real model to isolate and validate first.
- `M1` depends on `M2`, so it should come after `M2`.
- `M3` is the most contract-sensitive and planner-flow-sensitive, so it must be last.

## Shared Deployment Rule
Every phase follows the same deployment cycle:
1. Merge code with engine still disabled for production use.
2. Deploy migrations and code while the engine remains in `stub` mode.
3. Run validation on live-like data.
4. Flip only that engine to `real`.
5. Keep all later engines on `stub`.
6. If any issue appears, rollback is only an env change back to `stub`.

## Required New Env Flags
Add these to local env, Docker, and Render:
- `M1_ENGINE_MODE=stub`
- `M2_ENGINE_MODE=stub`
- `M3_ENGINE_MODE=stub`

Compatibility fallback:
- if any per-engine flag is absent, use `ENGINE_MODE`

This is mandatory for phased rollout.

---

## Phase 0 - Shared Preparation

## Purpose
Create the safe platform foundation for phased rollout without changing planner behavior yet.

## Scope
- Introduce per-engine mode switching.
- Add shared real-engine dependencies.
- Add additive traceability migrations.
- Freeze contract tests for current planner/API behavior.
- Refactor engine bridge so `M3` can stop depending on `M1`.
- Confirm the seeded route graph from `data/seed/route_edges.csv` is available through the `route_edges` master table for later `M3` optimization.
- Keep all engines in `stub` mode after deployment.

## Implementation Changes
- Add per-engine mode resolution in engine bridge.
- Introduce runtime adapter structure for real engines.
- Add runtime dependencies:
  - `numpy`
  - `pandas`
  - `scikit-learn`
  - `xgboost`
  - `ortools`
- Add schema columns for normalized + raw trace persistence.
- Keep `M2` synthetic dataset usage explicitly limited to offline bootstrap/training, not general orchestration runtime.
- Add tests that lock current response shapes for:
  - M1 planner results
  - M2 planner requests
  - M3 plan summaries/details
  - planner approve/reject/override flow

## Deployment Steps
1. Deploy code and DB migrations with:
   - `M1_ENGINE_MODE=stub`
   - `M2_ENGINE_MODE=stub`
   - `M3_ENGINE_MODE=stub`
2. Confirm app boots with new dependencies.
3. Confirm migrations are additive and existing data remains readable.
4. Confirm current stub behavior is unchanged.

## Exit Criteria
- No planner/API regression.
- No migration issues.
- Per-engine toggles available in all environments.

## Rollback
- No special rollback expected beyond standard deploy rollback, since all engines remain stubbed.

---

## Phase 1 - M2 Real Integration First

## Purpose
Replace stub `M2` with the real XGBoost-backed inference flow while keeping `M1` and `M3` on stubs.

## Scope
- Build live runtime feature generation for `M2`.
- Load committed classifier/regressor artifacts at runtime.
- Normalize `M2` real output to existing planner contract.
- Persist raw model trace fields in `m2_requests`.
- Allow the first deployment to rely on the existing synthetic `M2` training dataset only for artifact bootstrap/regeneration if needed.

## Inputs to Build from Live Data
- DC stock snapshots:
  - `physical`
  - `in_transit`
  - `effective`
- sales history forecast data:
  - `daily_avg`
  - `forecast_48h`
- SKU metadata:
  - `category`
- derived runtime features:
  - `hourly_sales`
  - `projected_daily_sales`
  - `stock_to_sales_ratio`
  - `days_of_cover`
  - `safety_stock`
  - `day_of_week`
  - `is_weekend`
  - `hour_of_day`
  - `lead_time_hours` proxy

## Key Decisions in This Phase
- Real `M2` runtime must use backend canonical DC/SKU identities.
- Synthetic `M2` CSV data is acceptable only for first-deployment artifact bootstrap, not as the planner orchestration input source.
- No runtime CSV reading for production orchestration after the adapter path is in place.
- Output normalization will preserve current fields:
  - `dc_id`
  - `sku_id`
  - `requested_quantity`
  - `urgency`
  - `required_by`
- Extra model-native values will be persisted in trace fields, not exposed as required API changes.

## Database Work in This Phase
- Add `m2_requests` trace columns.
- Add `engine_runs` implementation/version/trace columns.

## Test Plan
- Unit tests for feature builder and urgency normalization.
- Contract test for `/api/v1/planner/m2-requests/{run_id}`.
- Integration test for orchestration with:
  - `M2=real`
  - `M1=stub`
  - `M3=stub`

## Deployment Steps
1. Merge `M2` real code with all env flags still set to `stub`.
2. Deploy migrations and dependency updates.
3. Run validation locally/staging against current seeded database.
4. Flip only:
   - `M2_ENGINE_MODE=real`
5. Keep:
   - `M1_ENGINE_MODE=stub`
   - `M3_ENGINE_MODE=stub`
6. Generate plans and compare:
   - DB persistence
   - planner request page load
   - counts/urgency sanity
   - approve/reject flow still stable downstream

## Exit Criteria
- `M2` planner page works with real output.
- `M1` stub still consumes `M2` output without breaking.
- No planner-flow regression.
- Rollback can be done by env only.

## Rollback
- Set `M2_ENGINE_MODE=stub`
- No DB rollback required because schema changes are additive.

---

## Phase 2 - M1 Real Integration Second

## Purpose
Replace stub `M1` with the real planner-only scoring engine after real `M2` is stable.

## Scope
- Build live runtime feature generation for `M1`.
- Remove `M1` as an input to `M3` in orchestration and engine bridge.
- Normalize `M1` real output back to current planner contract.
- Persist score breakdown / raw feature trace for auditability.
- Keep `M1` synthetic datasets out of deployment runtime and use them only as development fixtures if needed.

## Inputs to Build from Live Data
- manifest lines
- warehouse effective stock
- real `M2` output aggregated by SKU
- SKU metadata
- ETA-derived timing
- derived runtime features:
  - `wh_days_of_cover`
  - `max_m2_urgency`
  - `num_dcs_requesting`
  - `m2_fulfillment_ratio`
  - `eta_delay_hours` or equivalent ETA urgency proxy

## Key Decisions in This Phase
- `M1` is planner-facing only.
- `M3` must be refactored now to run without `M1`.
- Real `M1` output bands will be normalized into lowercase planner vocabulary.
- `M1` does not require synthetic deployment data.

## Database Work in This Phase
- Add `m1_results` trace fields:
  - `score_breakdown`
  - `raw_features`

## Test Plan
- Unit tests for M1 feature builder and band normalization.
- Contract test for `/api/v1/planner/m1-results/{run_id}`.
- Integration test for orchestration with:
  - `M2=real`
  - `M1=real`
  - `M3=stub`

## Deployment Steps
1. Merge `M1` real code and the orchestration change removing `M1 -> M3`.
2. Deploy with:
   - `M1_ENGINE_MODE=stub`
   - `M2_ENGINE_MODE=real`
   - `M3_ENGINE_MODE=stub`
3. Validate in deployed environment that orchestration still works.
4. Flip only:
   - `M1_ENGINE_MODE=real`
5. Keep:
   - `M2_ENGINE_MODE=real`
   - `M3_ENGINE_MODE=stub`
6. Validate:
   - priorities page
   - planner result persistence
   - SKU summary generation
   - M3 stub still works with the new orchestration path

## Exit Criteria
- `M1` page works with real output.
- `M3` no longer depends on `M1`.
- Real `M2` + real `M1` coexist safely.
- Rollback remains env-only.

## Rollback
- Set `M1_ENGINE_MODE=stub`
- Keep `M2` real if stable

---

## Phase 3 - M3 Real Integration Last

## Purpose
Replace stub `M3` with the OR-Tools planner while preserving the current candidate-plan workflow and day/run persistence model.

## Scope
- Refactor OR-Tools model into runtime callable code.
- Stop using CSV-based synthetic runtime inputs.
- Convert live backend inputs into solver inputs.
- Generate 3 candidate plan variants from the real solver.
- Persist into:
  - `m3_plan_versions`
  - `m3_plan_runs`
  - `m3_plan_stops`
  - `m3_plan_items`
- Preserve planner override, approval, validation, demo-state, and history/reporting behavior.

## Inputs to Build from Live Data
- real `M2` requests
- warehouse effective stock
- lorry day-state availability
- route graph loaded from the persisted `route_edges` master data seeded initially from `data/seed/route_edges.csv`
- SKU reefer requirements
- canonical lorry/DC/SKU identities

## Candidate Plan Strategy
Plan A:
- urgency-maximizing objective
- marked `is_best=true`

Plan B:
- balanced-coverage variant
- solver rerun or constrained alternate
- aims to spread service across more DCs

Plan C:
- cost-aware variant
- solver rerun with cost/travel penalty emphasis using `travel_time_hours` and `cost` from the seeded route graph

## Key Decisions in This Phase
- `M3` does not consume `M1`.
- The current planner candidate-version contract stays intact.
- The current run/day schema stays intact.
- Raw solver metadata is stored in plan version trace fields.
- `M3` does not require synthetic deployment data; the seeded route graph is the live optimization baseline for the first deployment.

## Database Work in This Phase
- Add `m3_plan_versions` metadata fields:
  - `plan_name`
  - `generation_strategy`
  - `objective_value`
  - `solver_trace`

## Test Plan
- Unit tests for canonical input normalization and candidate-plan packaging.
- Contract tests for:
  - `/api/v1/planner/m3-plans/{run_id}`
  - `/api/v1/planner/m3-plans/{run_id}/{version_id}`
- Planner-flow regression tests for:
  - approve
  - reject
  - override
  - lorry-day validation
  - demo reservations/transfers creation

## Deployment Steps
1. Merge real `M3` runtime and candidate-plan generator.
2. Deploy with:
   - `M1_ENGINE_MODE=real`
   - `M2_ENGINE_MODE=real`
   - `M3_ENGINE_MODE=stub`
3. Run DB + API + planner-flow validation.
4. Flip only:
   - `M3_ENGINE_MODE=real`
5. Validate:
   - dispatch page candidate plan comparison
   - plan detail page
   - approve/reject/override
   - demo-state effects
   - history/reporting consistency

## Exit Criteria
- Real `M3` produces 3 usable candidate versions.
- Planner workflow remains intact.
- Approve/override paths still enforce run/day physical constraints.
- Rollback remains env-only.

## Rollback
- Set `M3_ENGINE_MODE=stub`
- Keep `M1` and `M2` real if stable

---

## Phase 4 - Hardening and Cleanup

## Purpose
Stabilize the full real-mode platform after all 3 engines are live.

## Scope
- Add comparison tooling for stub vs real historical runs if needed.
- Improve monitoring/logging of engine trace metadata.
- Refresh docs and runbooks.
- Decide whether stub mode remains permanent fallback or only emergency fallback.

## Hardening Tasks
- Document exact environment configuration for Render/local.
- Document model artifact/version ownership.
- Add health verification for real-engine dependencies.
- Add timeout/performance thresholds for `generate-plan`.
- Add support notes for retraining/replacing future model artifacts.

## Final Runtime Target
- `M1_ENGINE_MODE=real`
- `M2_ENGINE_MODE=real`
- `M3_ENGINE_MODE=real`

## Final Acceptance Criteria
- Full real orchestration works end-to-end on the seeded/live local database.
- Planner pages load normally.
- Planner decisions remain safe and auditable.
- Engine rollbacks remain possible per engine.
- No required frontend rewrite was introduced.

## Deployment Summary
- Phase 0: prepare platform, still all stubs
- Phase 1: enable `M2` real only
- Phase 2: enable `M1` real, keep `M3` stub
- Phase 3: enable `M3` real
- Phase 4: harden, document, monitor

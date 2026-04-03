# Executable Walkthrough

This walkthrough is written for judges and reviewers. Use the hosted demo first. Local run is the fallback path.

## Hosted Demo First

Open the hosted frontend URL and start at:

- `/dashboard`

## Recommended Click Path

### 1. Dashboard

What to do:

- open `Dashboard`
- review latest `M1`, `M2`, and `M3` timestamps
- review fleet status and alerts

What to expect:

- summary cards for Prioritizer, Forecaster, and Optimizer
- current Optimizer lock/open status
- fleet breakdown and planner alerts

### 2. Inputs

What to do:

- open `Inputs`
- switch through the input-family tabs

What to expect:

- active manifests
- warehouse effective stock
- DC effective stock
- sales-history forecasts
- lorry day-state snapshots
- ETA records

This page shows the data the planning flow works from.

### 3. Forecaster

What to do:

- open `Forecaster`
- review urgency mix and request lines

What to expect:

- request count, critical-request count, impacted DCs, and total requested units
- per-line output with DC, SKU, requested quantity, urgency, and required-by timing

This page shows the shortage pressure that drives the rest of the workflow.

### 4. Prioritizer

What to do:

- open `Prioritizer`
- expand the ranked shipments

What to expect:

- shipment-level ranking for manifest clearance
- shipment score and priority band
- per-SKU line details for each shipment
- cold-chain visibility where relevant

This page shows which inbound supply should be cleared first.

### 5. Optimizer

What to do:

- open `Optimizer`
- review candidate plans
- inspect the selected plan detail
- if the environment is prepared for interaction, generate a plan and approve the preferred draft

What to expect:

- candidate plans with scores, runs, and stops
- detailed run -> stop -> item hierarchy
- structured override editor
- planner actions for override, approve, and reject

This is the central planning workspace.

### 6. Demo Operations

What to do:

- open `Demo Operations`
- review `State View`
- review `Execution`
- if the environment contains an approved in-transit stop, mark the stop as arrived

What to expect:

- reservations created by approval
- in-transit transfers created by approval
- business events such as manifest arrivals and DC sales
- execution actions that convert transfer state into physical DC stock

Important note:

- the route is `/demo-state`
- the visible menu label is `Demo Operations`

This page demonstrates the product's core differentiator: approval and physical execution are separate.

### 7. History

What to do:

- open `History`

What to expect:

- immutable approved versions
- stop-level approved content
- planner decisions
- recent audit trail

This page proves traceability and decision preservation.

### 8. Reports

What to do:

- open `Reports`

What to expect:

- approved-plan reporting snapshot
- audit-trail reporting snapshot
- browser-side export actions for JSON and CSV

This page closes the reviewer journey with export and reporting capability.

## Local Fallback

If the hosted demo is unavailable, run the product locally using [HOW_TO_RUN.md](../../HOW_TO_RUN.md).

After local startup, use the same route order:

1. `/dashboard`
2. `/inputs`
3. `/requests`
4. `/priorities`
5. `/dispatch`
6. `/demo-state`
7. `/history`
8. `/reports`

## What The Reviewer Should Understand

By the end of the walkthrough, the reviewer should understand that the product:

- detects shortage pressure
- prioritizes incoming supply
- generates constrained dispatch plans
- allows planner oversight and manual intervention
- separates planning overlays from physical stock movement
- preserves the decision trail for later reporting

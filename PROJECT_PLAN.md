# Project Plan - 7-Day MVP

## Goal

Deliver a working planner-facing MVP that:

- fetches manifests, stock, sales, and lorry state as snapshots
- fetches ETA from a mock API
- runs `M1`, `M2`, and `M3` as pure engines
- lets the planner review, edit, approve, reject, and override plans
- simulates reservation and stock movement in a separate demo-only state module

## Success Criteria

By the end of day 7, the demo must show:

1. manifest snapshots fetched from the source database reader
2. warehouse, DC, sales, and lorry snapshots fetched from readers
3. ETA updates from the mock API
4. M1 ranked shipment-line priorities and aggregated SKU summary
5. M2 generated DC requests
6. M3 candidate dispatch plans with one selected best plan
7. planner edit, approve, reject, and override flow
8. approval creating demo reservation state
9. simulated arrival updating demo warehouse and DC stock
10. immutable approved plan history and audit trail

## Locked Scope

- 15 SKUs
- 1 warehouse
- 5 DCs
- 8 lorries total
  - 5 normal
  - 3 reefer
- maximum 2 stops per lorry
- fixed route times and costs
- `capacity_unit` for lorry/load feasibility
- planner-only frontend

## Team Split

### Developer 1 - Demo State Only
- build local persistence for demo reservation and transfer simulation
- create reservation state on approval
- simulate arrival and warehouse/DC stock movement
- expose demo-state projections and audit views

### Developer 2 - Frontend and Planner Flow
- build planner dashboard and read-only input views
- build M1, M2, M3 result pages
- build plan comparison, edit, approval, rejection, and override UI
- wire API orchestration and reporting views

### Developer 3 - M1 and M2 Only
- implement `M1` training, inference, and score output
- implement `M2` request generation from stock and sales snapshots
- keep both engines isolated from planner flow and demo-state logic

### Developer 4 - M3 Only
- implement optimizer, ranker, and candidate-plan generation
- expose planner-editable draft-plan contract
- keep `M3` isolated from demo-state and transaction simulation

## Workstreams

### Stream A - Inputs and orchestration
- manifest snapshot reader
- warehouse stock reader
- DC stock reader
- sales history reader
- lorry state reader
- ETA provider
- API orchestration for planner views

### Stream B - Engines
- `M1` priority scoring
- `M2` request generation
- `M3` optimization and ranking

### Stream C - Planner console
- input pages
- engine result pages
- dispatch editing and approval flow
- history and report pages

### Stream D - Demo state simulation
- reservation state
- transfer state
- arrival simulator
- post-approval stock projections

## Delivery Sequence

### Day 1
- freeze docs, contracts, rules, and repo structure
- generate folder skeleton

### Day 2
- set up snapshot readers and ETA mock integration
- seed data and route graph

### Day 3
- implement `M1`
- start planner priority view

### Day 4
- implement `M2`
- connect request views

### Day 5
- implement `M3` optimizer and ranker
- expose candidate plans

### Day 6
- implement planner edit, approve, reject, and override flow
- implement demo reservation and simulated arrival flow

### Day 7
- harden demo scenarios
- finalize audit trail, reports, and documentation

## Acceptance Checklist

- [ ] manifest comes from `manifest_reader`, not manual upload
- [ ] ETA comes from the mock API
- [ ] `M1`, `M2`, and `M3` never mutate stock
- [ ] planner can edit draft plans before approval
- [ ] approved plan versions are immutable
- [ ] `demo_state` creates reservation on approval
- [ ] `demo_state` updates demo warehouse and DC stock on simulated arrival
- [ ] planner can view history and reports from the same console

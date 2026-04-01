# Project Plan

## Summary

The project has moved beyond the original 7-day MVP planning state. The platform, persistence layer, planner console, and demo operations baseline are now implemented locally and working together. This document now tracks current delivery status and the next milestones needed to finish the product.

## Current Delivery Status

### Platform baseline

Completed:

- local MySQL 8 setup through Docker
- Alembic migrations and reset/seed workflow
- deterministic demo data for SKUs, DCs, lorries, manifests, ETAs, and stock
- backend readers for manifests, warehouse stock, DC stock, sales history, lorry horizon, and ETAs
- orchestration and engine-run persistence

### Planner application

Completed:

- planner-only Next.js frontend
- dashboard, inputs, M1 priorities, M2 requests, M3 dispatch, history, demo operations, and reports
- plan comparison, run-based plan detail, override, approve, reject, and audit trail flows
- local run-context persistence across the planner workflow

### Demo operations and execution

Completed:

- stop-scoped reservations and transfers on approval
- date-based lorry day assignments
- manifest CSV upload and manifest arrival
- DC sale posting
- lorry availability control for the next 2 planning days
- stop arrival execution that releases matching reservations and moves stock physically

### Engine integration posture

Current state:

- platform contracts are in place
- stub-compatible `M1`, `M2`, and `M3` integration path exists
- real engine replacement is still pending

## Current Product Rules

- 48-hour planning horizon
- run-based M3 plans with `dispatch_day`
- one lorry may be assigned once on Day 1 and once on Day 2
- maximum 2 stops per run
- M2 uses trailing 30-day sales history for forecast input
- lorry availability is horizon-based, not binary-only across the whole plan
- planner approval creates overlays, not direct physical stock movement

## Remaining Milestones

### Milestone 1: Real engine integration

- replace stub `M1` with real scoring logic
- replace stub `M2` with real request-generation logic
- replace stub `M3` with the real optimizer/ranker
- keep the existing planner and API contracts stable while swapping implementations

### Milestone 2: Hosted environment

- deploy frontend
- deploy backend
- deploy cloud MySQL
- finalize production config such as CORS, environment variables, and hosted database wiring

### Milestone 3: CI/CD and release flow

- add GitHub Actions for backend checks and frontend build
- auto-deploy on merge to `main`
- protect `main`
- make real-engine merges flow through the same deployment pipeline

## Immediate Next Step

The next practical delivery sequence is:

1. plug in real `M1`, `M2`, and `M3`
2. deploy the system using Vercel + Railway
3. add CI/CD so merged engine changes auto-integrate into the hosted system

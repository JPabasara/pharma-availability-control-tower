# Strategy

## Strategic Intent

Build a planner-facing control tower that stays modular, explainable, and operationally credible without turning the product into a full ERP.

The current strategy is to keep planning, execution state, and physical stock progression separated while still making the hosted demo feel like a usable end-to-end system.

## Strategy 1 - Keep Boundaries Hard

The architecture depends on four clear layers:

- **inputs/readers**
- **pure decision engines**
- **planner decisions**
- **demo operations / execution events**

This is the most important strategic choice in the system. It keeps engine logic reusable, planner actions auditable, and demo-state progression understandable.

## Strategy 2 - Treat Effective State As A Platform Concern

The engines should never compute against raw physical stock alone.

The platform layer owns:

- warehouse effective stock
- DC effective stock
- lorry horizon state for Day 1 and Day 2

That means:

- approved reservations affect warehouse availability
- approved transfers affect DC effective availability
- lorry-day assignments affect future lorry feasibility

The engines remain clean because these rules live in readers and orchestration, not inside model code.

## Strategy 3 - Keep Approval And Physical Movement Separate

Planner approval is a planning event, not a physical stock movement event.

Approval creates:

- reservations
- in-transit transfers
- lorry day assignments

Physical stock changes only when business events are posted:

- manifest arrival
- DC sale
- stop arrival at a DC

This preserves auditability and keeps the business story coherent.

## Strategy 4 - Use Hosted Demo Operations, Not Raw DB Editing

The system now exposes backend commands through the frontend instead of relying on raw database edits or CLI-only progression.

That means the hosted demo can move forward through controlled operations:

- upload manifest
- mark manifest arrived
- post DC sale
- toggle lorry availability for the next 2 planning days
- mark stop arrival

This is strategically better than allowing planners to edit stock tables directly because it keeps state transitions intentional and traceable.

## Strategy 5 - Keep M3 Run-Based And Explainable

M3 should be thought of as a 2-day lorry schedule, not just a flat list of stops.

Current planning language should therefore stay:

- `runs -> stops -> items`
- each run has `lorry_id`
- each run has `dispatch_day`
- each run can contain at most 2 DC stops

This makes the dispatch output easier to reason about and aligns planner override behavior with actual lorry-day constraints.

## Strategy 6 - Keep Stubs As A Bridge, Not A Fork

The platform should continue to treat stub engines as temporary infrastructure, not as a separate product mode.

The important rule is:

- frontend contracts stay stable
- planner APIs stay stable
- real engines replace the stub bridge behind the same interfaces

That is what allows current platform work, hosting, and CI/CD to move forward before real-engine integration is complete.

## Strategy 7 - Stay Local-First, Then Host Cleanly

The current system is local-first and demo-ready:

- MySQL in Docker
- FastAPI backend
- Next.js frontend

The next hosting strategy is intentionally simple:

- frontend on Vercel
- backend and MySQL on Railway
- CI/CD through GitHub Actions and auto-deploy

This keeps the product moving without redesigning the architecture for deployment.

## Final Position

The current platform should be explained in one sentence like this:

inputs feed pure decision engines, planners make controlled decisions, and demo operations advance physical business state through auditable backend events.

That remains the core strategy for the next phase as real `M1`, `M2`, and `M3` are integrated and the system moves to hosted deployment.

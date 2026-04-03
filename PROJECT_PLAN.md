# Submission Readiness Roadmap

This document tracks the remaining preparation work after implementation. It is intentionally focused on submission readiness, not feature development.

## Current Position

The MVP is already implemented:

- planner-only frontend is in place
- backend APIs, persistence, seed data, and demo operations are in place
- `M1`, `M2`, and `M3` real adapters exist under `apps/api/app/orchestration/real`
- local setup, hosted deployment path, and validation checks already exist

The remaining work is packaging and presentation.

## Workstream 1: Repo Cleanup And Documentation Alignment

Goal: make the repository easy for judges and reviewers to understand.

- remove outdated planning markdown
- remove placeholder-only folders that are not part of the runtime
- rewrite the kept root docs around the implemented system
- add a dedicated `docs/submission/` set for review and packaging guidance

## Workstream 2: Demo Asset Preparation

Goal: make the product easy to demonstrate in a short video.

- reset and reseed the demo data before recording
- verify the hosted flow used in the demo
- capture stable screenshots from dashboard, inputs, requests, priorities, dispatch, and demo operations
- prepare a short walkthrough sequence that shows planning and execution clearly

## Workstream 3: Slide Deck Preparation

Goal: turn the technical implementation into a business-facing product story.

- summarize the problem and operational need
- explain the end-to-end workflow
- show the architecture and tech stack
- highlight planner control, auditability, and business impact
- keep the slide count within the submission limit

## Workstream 4: Packaging Readiness

Goal: produce one clean submission bundle.

- keep required code, data, migrations, and documentation in the final folder
- exclude local runtime clutter such as `.git/`, `.venv/`, `apps/web/node_modules/`, and `apps/web/.next/`
- include final slides and video in the final bundle
- perform one last smoke check before zipping

## Working Rule For This Track

Submission preparation should avoid unnecessary product changes. Unless a documentation pass reveals a blocking bug or a demo-breaking issue, this track should stay focused on cleanup, explanation, and packaging.

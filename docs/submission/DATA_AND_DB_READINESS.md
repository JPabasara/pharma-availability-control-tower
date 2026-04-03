# Data And Database Readiness

This document is the single source of truth for Phase 3 submission readiness.

## Non-Destructive Rule

This phase does **not** remove operational files and does **not** simplify schema.

Do not remove or rewrite:

- `scripts/reset_db.py`
- `db/seeds/seed_all.py`
- `db/migrations/**`
- `data/seed/*.csv`
- `ml/datasets/*.csv`
- `ml/models/artifacts/m2_classifier.json`
- `ml/models/artifacts/m2_regressor.json`

Database cleanup in this submission pass means:

- drop/reset through the existing reset flow
- run migrations
- reseed
- restore the clean demo scenario

It does **not** mean deleting tracked business tables, altering migration history, or removing runtime files.

## Artifact Classification

### Keep And Include In Final ZIP

- `data/seed/*.csv`
- `ml/datasets/*.csv`
- `db/migrations/**`
- `db/seeds/seed_all.py`
- `scripts/reset_db.py`
- `tests/csv/test_manifest.csv`
- `ml/models/artifacts/m2_classifier.json`
- `ml/models/artifacts/m2_regressor.json`

### Keep In Repo But Exclude From Final ZIP

- `ml/models/artifacts/m1_priority_output.csv`
- `ml/models/artifacts/m2_requests_output.csv`
- `ml/models/artifacts/m3_dispatch_plan.csv`
- `ml/models/m2_run_output.txt`

### Exclude From Final ZIP

- `.git/`
- `.venv/`
- `apps/web/node_modules/`
- `apps/web/.next/`
- `mysql_data/`
- `__pycache__/`
- `build/`
- `dist/`
- `out/`
- `.vscode/`
- `.idea/`
- other generated local runtime folders or transient caches

## Canonical Demo Baseline

Both the local and hosted demo should be restored to the same seeded scenario before recording and before final packaging.

The seed flow establishes a consistent planning story built around:

- overlapping inbound vessels
- urgent DC shortage pressure
- reefer-capacity pressure

The goal is for screenshots, walkthrough steps, video, and final judge review to all refer to one clean state.

## Local Reset And Reseed

The local canonical reset path is:

```powershell
docker compose up -d mysql
.\.venv\Scripts\python scripts\reset_db.py
```

Use this flow before:

- taking screenshots
- recording the local fallback demo
- validating the walkthrough against a clean environment
- building the final ZIP after local checks if the data has drifted

## Hosted Reset And Reseed

The hosted canonical reseed path is:

```powershell
$env:DATABASE_URL="<your hosted database url>"
.\.venv\Scripts\python db\seeds\seed_all.py
Remove-Item Env:\DATABASE_URL
```

Use this flow before:

- recording the hosted demo
- taking hosted screenshots for slides
- any final judge review if the hosted state has drifted

## Pre-Recording Checklist

- confirm the correct environment is targeted
- reset and reseed the chosen database
- verify the frontend loads the expected seeded state
- verify `Dashboard`, `Inputs`, `Forecaster`, `Prioritizer`, `Optimizer`, `Demo Operations`, `History`, and `Reports` all reflect the same clean scenario
- avoid capturing screens after ad hoc demo actions unless you intentionally reseed again

## Pre-Final-ZIP Checklist

- confirm all required seed, dataset, migration, reset, and M2 model files are present
- confirm non-runtime sample outputs are excluded from the final ZIP
- confirm local-only folders and caches are excluded from the final ZIP
- confirm docs describe reset/reseed consistently across local and hosted flows
- if local or hosted demo state drifted during prep, reseed again before final screenshots or recording references are frozen

## Operational Readiness Notes

- Local reset is performed through `scripts/reset_db.py`, which drops tables, runs Alembic migrations, and reseeds the database.
- Hosted reseeding is performed through `db/seeds/seed_all.py` against the target `DATABASE_URL`.
- Protecting operational files takes priority over bundle minimalism in this phase.

# Submission Content Map

This document lists what should go into the final competition submission bundle.

## Include In The Final ZIP

### Source Code

- `apps/`
- `integrations/`
- `storage/`
- `ml/`
- `db/`
- `data/`
- `scripts/`
- `tests/`

### Core Root Files

- `README.md`
- `PROJECT_PLAN.md`
- `REPO_STRUCTURE.md`
- `HOW_TO_RUN.md`
- `host_workflow.md`
- `requirements.txt`
- `Dockerfile`
- `docker-compose.yml`
- `render.yaml`
- `alembic.ini`

### Documentation

- `docs/submission/CODE_DOCUMENTATION.md`
- `docs/submission/EXECUTABLE_WALKTHROUGH.md`
- `docs/submission/SUBMISSION_CONTENT_MAP.md`

### Required Data And Runtime Support Files

- `data/seed/*.csv`
- `db/migrations/**`
- `db/seeds/seed_all.py`
- `scripts/reset_db.py`
- `ml/models/artifacts/m2_classifier.json`
- `ml/models/artifacts/m2_regressor.json`

### Reference Documents Kept In Repo

- `docs/uml/`
- `docs/srs/`

These reference PDFs are preserved in this pass. They can be kept or omitted in the final ZIP depending on folder-size constraints and mentor preference.

## Competition Deliverables To Add Before Final Packaging

These are not created in this pass, but they should be placed in the final submission bundle:

- slide deck
- video demonstration

Recommended future bundle targets:

- `submission_assets/slides/`
- `submission_assets/video/`

## Exclude From The Final ZIP

Do not include local runtime clutter or transient build output:

- `.git/`
- `.venv/`
- `apps/web/node_modules/`
- `apps/web/.next/`
- `mysql_data/`
- local IDE folders such as `.vscode/` or `.idea/`
- Python cache folders
- temporary build caches

If packaging is done manually, also omit transient files such as frontend build caches and other machine-generated artifacts that are not required to understand, run, or evaluate the product.

## Final Packaging Rule

The final ZIP should read like a clean submission bundle:

- source code and required data files
- code documentation
- executable and hosted walkthrough guidance
- final slides
- final video

It should not read like a developer workstation snapshot.

# Hosted Demo Workflow

This document describes the hosted-first path for the competition demo and reviewer access.

## Target Hosted Architecture

The intended hosted setup is:

- frontend on Vercel
- backend API on Render
- managed database provided through `DATABASE_URL`

Local development still uses Docker MySQL, but the hosted deployment should be treated as the primary review path.

## Backend Environment Variables

Set these on the hosted backend:

- `DATABASE_URL`
- `BUSINESS_TIMEZONE=Asia/Colombo`
- `ALLOWED_ORIGINS=<your frontend domain>` or `ALLOW_ORIGIN_REGEX=<your preview-domain regex>`
- `ENGINE_MODE=real`

Alternative engine configuration is also supported:

- `M1_ENGINE_MODE=real`
- `M2_ENGINE_MODE=real`
- `M3_ENGINE_MODE=real`

Use the per-engine flags only if you need split control. For the competition demo, a single `ENGINE_MODE=real` is simpler.

## Frontend Environment Variables

Set this on the hosted frontend:

- `NEXT_PUBLIC_API_BASE_URL=<your hosted backend URL>`

Do not include a trailing slash.

## Deployment Sequence

### 1. Provision the hosted database

Create the managed database and copy the connection string into `DATABASE_URL`.

### 2. Deploy the backend

Deploy the backend from this repository using the existing Render configuration as the baseline. Confirm:

- the service boots successfully
- migrations run successfully
- the health endpoint returns `ok`

### 3. Seed the hosted database

After migrations succeed, seed the hosted database from a trusted environment:

```powershell
$env:DATABASE_URL="<your hosted database url>"
.\.venv\Scripts\python db\seeds\seed_all.py
Remove-Item Env:\DATABASE_URL
```

If you need to return the hosted demo to a clean baseline before recording or judging, reseed the environment again.

### 4. Deploy the frontend

Deploy `apps/web` to Vercel and point it to the hosted backend through `NEXT_PUBLIC_API_BASE_URL`.

### 5. Run a hosted smoke check

Confirm these routes load correctly:

- `/dashboard`
- `/inputs`
- `/requests`
- `/priorities`
- `/dispatch`
- `/demo-state`
- `/history`
- `/reports`

## Reviewer And Judge Flow

The hosted reviewer experience should start from the frontend URL, not raw API docs.

Recommended path:

1. open the hosted frontend on `/dashboard`
2. review `/inputs`
3. review `/requests`
4. review `/priorities`
5. review `/dispatch`
6. review `/demo-state`
7. finish on `/history` or `/reports`

Use [docs/submission/EXECUTABLE_WALKTHROUGH.md](docs/submission/EXECUTABLE_WALKTHROUGH.md) as the reviewer script.

## Reset And Seeding Expectations

For a stable demo:

- seed the hosted database before recording
- reseed again before final judging if business state has drifted
- keep screenshots, slides, and video aligned to the same seeded scenario

## Route Naming Note

The UI label is `Demo Operations`, but the frontend route remains `/demo-state` for compatibility. This is expected and should be explained consistently in the video and slides.

# How To Run

This guide is for running the project locally from the repository root.

## Prerequisites

- Python environment already created at `.venv`
- Docker Desktop
- Node.js and npm
- PowerShell

Start from the project root:

```powershell
cd c:\Users\jpaba\Documents\GitHub\pharma-availability-control-tower
```

Open three PowerShell terminals in this directory.

## 1. Local Configuration

If you do not already have a working `.env`, start from `.env.example`.

Local development defaults to MySQL through Docker. For the ML-backed demo path, set one of these before starting the backend:

- `ENGINE_MODE=real`
- or `M1_ENGINE_MODE=real`, `M2_ENGINE_MODE=real`, `M3_ENGINE_MODE=real`

If you leave the engine mode in stub, the app still runs, but the competition demo story is written around the real adapters in `apps/api/app/orchestration/real`.

## 2. Database Terminal

Start MySQL:

```powershell
docker compose up -d mysql
```

If you want a clean local scenario before running the app, reset and reseed:

```powershell
.\.venv\Scripts\python scripts\reset_db.py
```

This will:

1. drop all tables
2. run Alembic migrations
3. seed the demo data from `data/seed/`

## 3. Backend Terminal

Start the FastAPI backend:

```powershell
.\.venv\Scripts\python -m uvicorn apps.api.app.main:app --reload --host 127.0.0.1 --port 8000
```

Useful local backend URL:

- API root: `http://127.0.0.1:8000/`
- API docs: `http://127.0.0.1:8000/docs`

## 4. Frontend Terminal

Install frontend dependencies the first time only:

```powershell
npm --prefix apps/web install
```

Then start the frontend:

```powershell
$env:NEXT_PUBLIC_API_BASE_URL='http://127.0.0.1:8000'
npm --prefix apps/web run dev
```

Useful local frontend URL:

- Planner console: `http://127.0.0.1:3000/dashboard`

## 5. Quick Verification

After all three services are up:

1. open `/dashboard`
2. confirm the planner shell loads
3. open `/inputs` and verify the seeded input families appear
4. open `/dispatch` and confirm the Optimizer workspace loads
5. open `/demo-state` and confirm Demo Operations loads

Optional non-mutating checks:

```powershell
.\.venv\Scripts\python -m unittest tests.integration.test_singleton_live_planning
npm --prefix apps/web run build
```

## Troubleshooting

### Frontend starts on the wrong port

The frontend should run on port `3000`. If Next.js starts on a different port, stop it, free port `3000`, and start it again.

### Local data looks inconsistent

Run the reset script again:

```powershell
.\.venv\Scripts\python scripts\reset_db.py
```

### Backend cannot connect to the database

Check:

- Docker MySQL is running
- your `.env` points to the expected local database
- port `3307` is available locally

### Real adapters are not being used

Check your backend environment variables and confirm either `ENGINE_MODE=real` or all three per-engine flags are set to `real`.

## Stop Everything

When you are done:

```powershell
docker compose down
```

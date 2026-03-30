# How To Run

Run everything from the project root:

```powershell
cd c:\Users\jpaba\Documents\GitHub\pharma-availability-control-tower
```

Open **3 PowerShell terminals** in that directory.

## Terminal 1: Database

Start MySQL with Docker:

```powershell
docker compose up -d mysql
```

If you want a clean seeded database before starting the app:

```powershell
.\.venv\Scripts\python scripts\reset_db.py
```

## Terminal 2: Backend API

Start the FastAPI server:

```powershell
.\.venv\Scripts\python -m uvicorn apps.api.app.main:app --reload --host 127.0.0.1 --port 8000
```

## Terminal 3: Frontend

First time only, install frontend dependencies:

```powershell
npm --prefix apps/web install
```

Then start the Next.js app:

```powershell
$env:NEXT_PUBLIC_API_BASE_URL='http://127.0.0.1:8000'
npm --prefix apps/web run dev
```

## Open In Browser

- Frontend: `http://127.0.0.1:3000/dashboard`
- API docs: `http://127.0.0.1:8000/docs`

## Important Note

The frontend should run on **port 3000**.

If Next.js starts on `3001` instead, the backend CORS config may block requests. In that case:

- stop the frontend
- free port `3000`
- start the frontend again

## Stop Everything

Stop Docker MySQL when you are done:

```powershell
docker compose down
```

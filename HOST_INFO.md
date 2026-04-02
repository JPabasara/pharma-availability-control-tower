# Hosting Configuration Info

This document explains the reasoning behind the architecture decisions and modifications made during the transition toward a production-ready Render + Postgres + Vercel deployment.

## 1. `render.yaml` (Infrastructure as Code)
**What it is:** A blueprint defining your entire backend infrastructure for Render natively.
**What it does:** Instead of manually configuring web services repeatedly over the dashboard, Render automatically reads this file to align environments. It controls:
- **Paths triggering builds (`buildFilter`)**: Tells Render to only redeploy the API if Python or Database code is updated, purposefully ignoring Next.js frontend code changes to save you pipeline minutes.
- **`preDeployCommand`**: Automatically executes `alembic upgrade head` before booting any new server images. This guarantees that your database schema perfectly matches your application code *before* new API traffic is actively accepted.

## 2. CORS (Cross-Origin Resource Sharing) Setup
**What it is:** A web-browser security standard restricting your frontend application from unknowingly extracting data retrieved from disparate backend domains.
**What it does:** Because your frontend originates from Vercel (`https://your-frontend.vercel.app`) but your API operates from Render (`https://your-api.onrender.com`), the user's browser proactively blocks this connection to prohibit injection attacks. 
- The config in `main.py` broadcasts to browsers, "We specifically trust this Vercel domain." 
- `ALLOWED_ORIGINS` allows you to inject the URL without hardcoding it natively.
- `ALLOW_ORIGIN_REGEX` secures subsequent preview domains created automatically by Vercel when establishing newer preview deployments dynamically.

## 3. Transitioning to PostgreSQL Frameworks
**What changed:** `pymysql` was replaced for `psycopg2-binary` (in `requirements.txt`) and MySQL-centric SQL execution patterns were completely excised out from the original Python backend codebase (like replacing manual foreign-key verification disables with sequential data truncation). 
**Why it was pursued:** 
- Top-tier Platform-as-a-Service (PaaS) providers almost completely bias fully-managed PostgreSQL due to its scalability limits. (Render, Supabase natively).
- The `SQLAlchemy` ORM manages automated SQL linguistic conversions internally, significantly minimizing total rewrite strain. 

## 4. Platform Separation Context
- **Vercel** represents the foremost architectural solution optimized exclusively for your `Next.js` frontend. Automatic edge-caching patterns, integrated CDN routing, out-of-the-box Image optimizations are highly performant components Render cannot replicate efficiently. 
- **Render** natively accommodates and prioritizes dedicated, long-running processes (in our case the continuous `uvicorn` FastAPI servers), delivering a generous and immediately usable PostgreSQL database natively. Serverless functions (like Vercel API routes) traditionally succumb to "cold-start" slowdowns fundamentally damaging heavy mathematical orchestration pipelines inherent to Python environments.

## 5. Continuous Integration / Deployment Status
**What it is:** The pipeline integrated directly within `.github/workflows/ci.yml`.
**What it does:** GitHub physically spins up a compartmentalized Ubuntu machine running a simulated Postgres Database environment immediately upon Pull Request generation. It verifies your Alembic integrations, database seeding executions, and ensures test coverage validation locally prior to facilitating backend Render deployment injections remotely. This guarantees production servers never encounter crippling syntax or data migration defects natively.

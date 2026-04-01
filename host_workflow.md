# Hosting Workflow (A to Z)

## Phase 1: Render Postgres Database
1. Go to your [Render Dashboard](https://dashboard.render.com/).
2. Click **New +** > **PostgreSQL**.
3. Fill your details:
   - **Name**: `pharma-control-tower-db`
   - **Database**: Leave default
   - **User**: Leave default
   - **Region**: Select a region close to your users (e.g., Singapore).
   - **Plan**: Free
4. Click **Create Database**.
5. Once created, copy the **Internal Database URL** (it should look like `postgresql://...`).

## Phase 2: Render Backend Web Service
1. In your Render Dashboard, click **New +** > **Web Service**.
2. Connect your GitHub repository.
3. Configure the following:
   - **Name**: `pharma-control-tower-api`
   - **Region**: Match the database region exactly (e.g., Singapore).
   - **Root Directory**: `.` (leave blank to default to repo root).
   - **Environment**: `Python`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python -m uvicorn apps.api.app.main:app --host 0.0.0.0 --port $PORT`
4. Expand **Advanced** and set Environment Variables:
   - `DATABASE_URL`: Setup exactly to match the Postgres **Internal Database URL**.
   - `ENGINE_MODE`: `stub`
   - `BUSINESS_TIMEZONE`: `Asia/Colombo`
   - `ALLOWED_ORIGINS`: We will fill this in Phase 4.
   - `ALLOW_ORIGIN_REGEX`: We will fill this in Phase 4.
5. Click **Create Web Service**. Wait for the build and deployment to succeed. 
   *(Note: The build will automatically run `alembic upgrade head` before starting to set up your database schema.)*
6. Once deployed, note down the deployed API URL (e.g., `https://pharma-control-tower-api.onrender.com`).

## Phase 3: Fresh Database Seeding
Because we use a fresh database on Render, you need to run the data seed once to populate SKUs, Lorries, Route Edges, etc so that the app works.
1. Render does not expose a UI button for one-off scripts, but you can do this securely by executing it **locally against your rendered database**.
   **Local execution method**: 
   - Get the **External Database URL** from the Render DB Dashboard.
   - Set it as your local OS Environment Variable: 
     ```powershell
     $env:DATABASE_URL="<your-external-database-url>"
     ```
   - From your project terminal run: 
     ```powershell
     .\.venv\Scripts\python db\seeds\seed_all.py
     ```
   - Remove the local `$env:DATABASE_URL` right after so you don't accidentally overwrite production data in the future!
     ```powershell
     Remove-Item Env:\DATABASE_URL
     ```
2. Your DB is now seeded securely.

## Phase 4: Vercel Frontend
1. Go to [Vercel](https://vercel.com/new) and click **Add New Project**.
2. Import the exact same GitHub repository.
3. **Crucial**: Set the **Root Directory** to `apps/web`. Vercel will automatically configure itself for Next.js.
4. Open the **Environment Variables** panel and add:
   - `NEXT_PUBLIC_API_BASE_URL`: The Render API Domain you noted in Phase 2 (e.g., `https://pharma-control-tower-api.onrender.com`).
5. Click **Deploy**. Vercel will build and launch your frontend.
6. Once live, note the Vercel Production Domain (e.g., `https://pharma-control-tower.vercel.app`).

## Phase 5: Finalizing CORS Security
We need to allow Vercel to fetch data from your Render backend securely.
1. Go back to your Render Dashboard > **Web Services** > **pharma-control-tower-api**.
2. Navigate to **Environment**.
3. Update the `ALLOWED_ORIGINS` variable:
   - Add your complete Vercel URL (e.g. `https://pharma-control-tower.vercel.app`). Do NOT include a trailing slash.
4. Update the `ALLOW_ORIGIN_REGEX` variable (Optional, for Preview Deployments):
   - Example `https://.*-yourvercelaccount\.vercel\.app`
5. Click **Save Changes**. Render will automatically redeploy the backend with the new CORS rules.

**Done!** Your system is strictly tied together, monitored by CI, hosted on scalable edge frontends, and backend Python rendering!

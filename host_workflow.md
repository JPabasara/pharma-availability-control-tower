# Hosting Workflow: Neon (DB) + Render (API) + Vercel (Web)

We are hosting the backend API on **Render**, which automatically detects and builds our `Dockerfile` and easily integrates the necessary configuration environment variables.

## Phase 1: Create the Database on Neon
1. Go to [Neon.tech](https://neon.tech/) and log in with GitHub. *(Neon is true free-tier serverless Postgres)*.
2. Click **Create Project**.
3. Fill in your project details:
   - **Name**: `pharma-control-tower-db`
   - **Version**: Postgres 17
   - **Region**: **Singapore (ap-southeast-1)** *(Crucial for low latency!)*
4. Click **Create Project**.
5. Once created, copy the **Connection String** (`postgresql://...`). Keep this safe.

## Phase 2: Render Web Service (Backend)
Render is an excellent host that automatically builds from our `Dockerfile`. Since your Neon Database is in Singapore, you should configure your Render Web Service to also run in the Singapore region (if available on the tier) for zero latency.

1. Go to the [Render Dashboard](https://dashboard.render.com/) and click **New+** > **Web Service**.
2. Connect your GitHub repository: `pharma-availability-control-tower`.
3. In the configuration:
   - **Name**: `pharma-control-api`
   - **Region**: `Singapore (ap-southeast-1)` (If unavailable on Free Tier, use closest possible or upgrade).
   - **Branch**: `main`
   - **Runtime**: `Docker` (Render automatically detects the Dockerfile in the repo).
   - **Instance Type**: Select the Free tier (or appropriate upgraded tier).
4. Scroll down to **Environment Variables** and add these exactly 5 variables:
   - `DATABASE_URL`: **Paste your Neon Postgres Connection String exactly.**
   - `ENGINE_MODE`: `real` *(We are now running the real engines)*
   - `BUSINESS_TIMEZONE`: `Asia/Colombo`
   - `ALLOWED_ORIGINS`: `*` *(We'll keep CORS open for the very first deployment)*
   - `PYTHON_VERSION`: `3.12.0` *(Sometimes required by Render just to be safe)*
5. Click **Deploy Web Service**. Render will securely build your Docker container. Wait until it shows the Green "Live" status, and copy the domain link (e.g., `https://pharma-...onrender.com`).

## Phase 3: Fresh Database Initialization & Seeding
If you are deploying for the first time, or if you need to wipe your database and start fresh with new demo data, follow these steps locally:

1. Copy your Neon **Connection String** again.
2. Open PowerShell locally in your project folder.
3. Set your local environment variable:
   ```powershell
   $env:DATABASE_URL="<your-neon-database-url>"
   ```
4. **Important for starting fresh:** Wipe the existing schema and rebuild it to ensure a clean slate:
   ```powershell
   .\.venv\Scripts\alembic downgrade base
   .\.venv\Scripts\alembic upgrade head
   ```
5. Run the seed script to populate the database:
   ```powershell
   .\.venv\Scripts\python db\seeds\seed_all.py
   ```
6. Once it finishes successfully, securely remove the local environment variable:
   ```powershell
   Remove-Item Env:\DATABASE_URL
   ```

## Phase 4: Vercel Frontend
1. Go to [Vercel](https://vercel.com/new) and click **Add New Project**.
2. Import the exact same GitHub repository.
3. **Crucial**: Set the **Root Directory** to `apps/web`. Vercel automatically configures itself for Next.js.
4. Open the **Environment Variables** panel and add:
   - `NEXT_PUBLIC_API_BASE_URL`: **Paste the Render API Domain you noted in Phase 2**. Make sure you do NOT leave a trailing slash `/` at the end of the URL.
5. Click **Deploy**. Vercel will build and launch your frontend.
6. Once live, note the Vercel Production Domain (e.g., `https://pharma-availability-control-tower.vercel.app`).

## Phase 5: Finalizing CORS Security (Optional)
If you want to lock down the backend so only your Vercel site can query it, you have two options in your Render **Environment** settings:

**Option A (Strict - Production Only):**
Edit `ALLOWED_ORIGINS` to perfectly match your new Vercel domain:
- `https://pharma-availability-control-tower.vercel.app`

**Option B (Flexible - Recommended by your friend):**
If you use Vercel's "Preview Deployments" (where every branch gets a random URL like `https://app-xyz123.vercel.app`), an exact match will break. Instead, delete `ALLOWED_ORIGINS` and add a new variable:
- `ALLOW_ORIGIN_REGEX`: `https://.*\.vercel\.app`
This regex securely tells the backend to accept requests from *any* Vercel domain.

3. Save changes. Render will auto-deploy the update, strictly locking access to Vercel.

**Done!** Your backend API is securely hosted on Render, your Database runs independently on Neon, and your Front-end connects flawlessly through Vercel.

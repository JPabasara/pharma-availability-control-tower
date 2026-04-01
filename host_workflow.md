# Hosting Workflow: Neon (DB) + Back4App (API) + Vercel (Web)

Since Render and Koyeb constantly block deployment without aggressive card authorizations, we are moving the backend API to **Back4App Containers**. 

Back4App provides incredibly generous, 100% free Docker container hosting with absolutely minimal blocks. We have just created a `Dockerfile` in your repository so Back4App will automatically recognize and host the backend.

## Phase 1: Create the Database on Neon
1. Go to [Neon.tech](https://neon.tech/) and log in with GitHub. *(Neon is true free-tier serverless Postgres)*.
2. Click **Create Project**.
3. Fill in your project details:
   - **Name**: `pharma-control-tower-db`
   - **Version**: Postgres 17
   - **Region**: US East (or whatever is default/closest to you).
4. Click **Create Project**.
5. Once created, copy the **Connection String** (`postgresql://...`). Keep this safe.

## Phase 2: Back4App Web Service
1. Go to the [Back4App Containers Dashboard](https://www.back4app.com/containers) and sign up/sign in with GitHub.
2. Click **Build new app**.
3. Allow Back4App access to your GitHub repositories, and search for `pharma-availability-control-tower` to connect it.
4. On the configuration screen:
   - **Name**: `pharma-control-api`
   - **Source directory**: Leave it as `/`
   - **Environment Variables**: Add these key-value pairs (vital for the API to boot):
     - `DATABASE_URL`: **Paste your Neon Postgres Connection String exactly.**
     - `ENGINE_MODE`: `stub`
     - `BUSINESS_TIMEZONE`: `Asia/Colombo`
     - `ALLOWED_ORIGINS`: `*` *(We'll keep CORS open for the very first deployment so Vercel can fetch data easily)*.
5. Hit **Deploy**. 
   - Back4App will automatically detect the `Dockerfile` I just created for you.
   - It will run `alembic upgrade head` inside the container dynamically to push the tables to Neon, and then boot the API.
6. Once the status turns green, you will receive a free public domain link (e.g., `https://pharma-api.back4app.io`). Save this link!

## Phase 3: Fresh Database Seeding
Your Neon database now has all the correct tables from Phase 2, but it is currently empty. We must push the demo data from your local machine.
1. Copy your Neon **Connection String** again.
2. Open PowerShell locally in your project folder.
3. Set your local environment variable:
   ```powershell
   $env:DATABASE_URL="<your-neon-database-url>"
   ```
4. Run the seed script:
   ```powershell
   .\.venv\Scripts\python db\seeds\seed_all.py
   ```
5. Once it finishes successfully, securely remove the local environment variable so you don't accidentally ruin production data in the future!
   ```powershell
   Remove-Item Env:\DATABASE_URL
   ```

## Phase 4: Vercel Frontend
1. Go to [Vercel](https://vercel.com/new) and click **Add New Project**.
2. Import the exact same GitHub repository.
3. **Crucial**: Set the **Root Directory** to `apps/web`. Vercel automatically configures itself for Next.js.
4. Open the **Environment Variables** panel and add:
   - `NEXT_PUBLIC_API_BASE_URL`: **Paste the Back4App API Domain you noted in Phase 2**. Make sure you do NOT leave a trailing slash `/` at the end of the URL.
5. Click **Deploy**. Vercel will build and launch your frontend.
6. Once live, note the Vercel Production Domain (e.g., `https://pharma-control-tower.vercel.app`).

## Phase 5: Finalizing CORS Security (Optional)
If you want to lock down the backend so only your Vercel site can query it:
1. Go back to your Back4App Dashboard > select your app > **App Settings** > **Environment Variables**.
2. Edit `ALLOWED_ORIGINS` to perfectly match your new Vercel domain:
   - `https://pharma-control-tower.vercel.app`
3. Click Save/Deploy. The backend will restart strictly locked to Vercel.

**Done!** Your backend API is securely hosted on Back4App Containers, your Database runs 24/7 independently on Neon, and your Front-end connects flawlessly through Vercel.

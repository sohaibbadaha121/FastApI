# FastAPI Deployment Plan (Render)

The goal of this plan is to migrate the database from SQLite to PostgreSQL (to prevent data loss) and set up the server configuration for our production environment.

## Phase 1: Code Preparation

### 1.1 Update Database Connection
* Modify `app/database.py` to support the `DATABASE_URL` environment variable.
* Add a fix for the PostgreSQL URL format (replacing `postgres://` with `postgresql://`).

### 1.2 Update `requirements.txt`
* Include `psycopg2-binary` for the PostgreSQL connection.
* Include `gunicorn` as the production process manager.

### 1.3 Update CORS Settings
* Tweak `app/main.py` to allow requests from our future frontend domain (or just use `*` for now).

---

## Phase 2: Render Dashboard Setup

### 2.1 Create the Database (Render PostgreSQL)
1. From the Render dashboard, click **New** -> **PostgreSQL**.
2. Name the database (e.g., `legal_db`).
3. After creation, Render will assign an "Internal Database URL" (we'll bind this to our web service).

### 2.2 Create the Web Service 
1. Click **New** -> **Web Service**.
2. Link the GitHub/GitLab account and select the repository.
3. Basic configuration:
    * **Environment**: `Python`
    * **Build Command**: `pip install -r requirements.txt`
    * **Start Command**: `gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app`

---

## Phase 3: Environment Variables Settings

The following keys need to be added in the **Environment** section on Render:
* `DATABASE_URL`: (Populates automatically when the DB is linked to the service).
* `GEMINI_API_KEY`: Google API key.
* `OPENROUTER_API_KEY`: OpenRouter API key.
* `PYTHON_VERSION`: `3.10.0` (or whichever version we prefer).

---

## Phase 4: Testing & Verification

* Make sure tables are successfully generated on the initial startup.
* Test the PDF upload flow and confirm that the extracted data is being saved correctly into PostgreSQL.

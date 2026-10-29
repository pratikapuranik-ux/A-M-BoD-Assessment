# NEXUS backend

FastAPI + LangGraph + SQLAlchemy 2.0 (SQLite by default, Postgres later). Python 3.12.
The HTTP API keeps the paths, methods and JSON shapes of the legacy `server/app.py` (`/api/health`, `/api/framework`,
`/api/companies`, `/api/companies/{id}/view`, `/api/companies/{id}/files/{key}`, `/api/companies/import`, `/api/research`,
`/api/companies/{id}/inside-out`, survey routes, `/api/jobs/{id}`, `DELETE /api/companies/{id}`), with the same error
format `{"error", "problems", job_id?}` and 409-with-`job_id` when a job is already running for a company.

## Run

From the project root, with the project venv (PowerShell):

    .venv\Scripts\python.exe -m pip install -r backend\requirements.txt
    cd backend
    ..\.venv\Scripts\python.exe -m alembic upgrade head      # optional: the app also creates missing tables at start
    ..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000

API docs at http://127.0.0.1:8000/docs. If `frontend/dist` exists it is served at `/` (SPA fallback); otherwise `/`
returns a JSON note. In development run the Vite dev server (port 5173, CORS allowed) against this API.

Tests (temp SQLite and storage, research mocked, no model calls):

    cd backend
    ..\.venv\Scripts\python.exe -m pytest

## Database

`NEXUS_DATABASE_URL` (default `sqlite:///./nexus.db`, relative to the working directory). Tables: `companies`,
`stage_runs` (outside-in / inside-out run JSON incl. computed grades), `prior_runs`, `survey_invites`,
`survey_responses` (anonymous, random position), `survey_hashes` (duplicate refusal), `deliverables` (built-file records).
Alembic: `alembic.ini`, `alembic/versions/0001_initial.py` (dialect-neutral). For Postgres set the URL and install a
driver (e.g. `psycopg[binary]`). Jobs stay in memory, as in the prototype.
Binary uploads and built files live under `NEXUS_STORAGE_DIR` (default `./storage`) as `<company id>/out/`.

## Environment

The project `.env` is read at start (values already set in the shell win; it is never printed). Set `NEXUS_SKIP_DOTENV=1` to skip it.

| Variable | Default | Purpose |
|---|---|---|
| `NEXUS_DATABASE_URL` | `sqlite:///./nexus.db` | SQLAlchemy URL |
| `NEXUS_STORAGE_DIR` | `./storage` | uploads and built deliverables |
| `NEXUS_FRONTEND_DIST` | `<root>/frontend/dist` | built frontend to serve |
| `NEXUS_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | allowed browser origins |
| `NEXUS_LOG_LEVEL`, `NEXUS_LOG_JSON` | `INFO`, off | structlog level / JSON output |
| `NEXUS_AUTO_CREATE_TABLES` | `1` | `0` to rely on Alembic only |
| `BOARD_MIN_RESPONSES` | `3` | anonymity guardrail: minimum self-assessment responses before an inside-out run (lower only for demos) |
| `BOARD_PUBLIC_URL` | request URL | base of survey links |
| `BOARD_ENV_FILE` | `<root>/.env` | alternative env file |

### Research (the LLM does all indicator scoring)

`POST /api/research` and `POST /api/companies/{id}/inside-out` call `app.agents.graph.run_outside_in` / `run_inside_out`
directly. There is no replay, stub or example-data path: if research is disabled or fails, the legacy error format is
returned (`503 "research is not available: <reason>"`, or the job fails with the `ResearchError` message and problems) and
nothing is stored. Stored scores are exactly what the model returned plus the deterministic `engine.grade()` arithmetic.
`GET /api/health` reports `{"research": {"enabled", "reason"}}`.

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` or `ANTHROPIC_FOUNDRY_*` | none | credentials / Foundry endpoint (set in `.env`; research is disabled without them) |
| `BOARD_MODEL` | `claude-opus-5` | model (deployment name on Foundry) |
| `BOARD_MODEL_B` | `claude-sonnet-5` | Run B's model (a deployment of this name must exist on Foundry; the run checks it first and stops with a clear message if not) |
| `BOARD_CONSISTENCY_RUNS` | `2` | `2` = Run A (`BOARD_MODEL`) and Run B (`BOARD_MODEL_B`) research independently, the model reconciles every indicator they scored differently and its recommendation is the final score; `1` = a single run |
| `BOARD_MIN_FETCHES`, `BOARD_MIN_FETCHES_PEER` | `20`, `12` | page reads below which a company / peer is sent back to read more before its scores are accepted |
| `BOARD_REVIEW_ROUNDS` | `2` | maximum retrieval-review rounds per subject (`0` = off) |
| `BOARD_EFFORT` | `high` | reasoning effort (both runs) |
| `BOARD_WEB_TOOLS` | `latest` (`basic` on Foundry) | web tool version; `latest` overrides the Foundry default |
| `BOARD_SEARCH_USES` | `60` | max web searches per subject |
| `BOARD_FETCH_USES` | `60` | max page fetches per subject |
| `BOARD_FETCH_TOKENS` | `30000` | token budget per fetched page |
| `NEXUS_SKILL_DIR` | `<root>/skill` | location of the skill references |

## Layout

`app/config.py log.py db.py models.py schemas.py main.py` core; `app/api/` routes (`assessments`, `survey`, `reference`,
`uploads`, `errors`); `app/services/repo.py` persistence (replaces `server/store.py`), `jobs.py`, `storage.py`,
`runs.py` (grade, history, build deliverables, job bodies; replaces `server/pipeline.py`).

# A&M BoD Assessment backend

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

`BOARD_DATABASE_URL` (default `sqlite:///./bod_assessment.db`, relative to the working directory). Tables: `companies`,
`stage_runs` (outside-in / inside-out run JSON incl. computed grades), `prior_runs`, `survey_invites`,
`survey_responses` (anonymous, random position), `survey_hashes` (duplicate refusal), `deliverables` (built-file records).
Alembic: `alembic.ini`, `alembic/versions/0001_initial.py` (dialect-neutral). For Postgres set the URL and install a
driver (e.g. `psycopg[binary]`). Jobs stay in memory, as in the prototype.
Binary uploads and built files live under `BOARD_STORAGE_DIR` (default `./storage`) as `<company id>/out/`.

## Environment

The project `.env` is read at start (values already set in the shell win; it is never printed). Set `BOARD_SKIP_DOTENV=1` to skip it.

| Variable | Default | Purpose |
|---|---|---|
| `BOARD_DATABASE_URL` | `sqlite:///./bod_assessment.db` | SQLAlchemy URL |
| `BOARD_STORAGE_DIR` | `./storage` | uploads and built deliverables |
| `BOARD_FRONTEND_DIST` | `<root>/frontend/dist` | built frontend to serve |
| `BOARD_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | allowed browser origins |
| `BOARD_LOG_LEVEL`, `BOARD_LOG_JSON` | `INFO`, off | structlog level / JSON output |
| `BOARD_AUTO_CREATE_TABLES` | `1` | `0` to rely on Alembic only |
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
| `BOARD_MODEL` | `claude-opus-5` | model for Run A, the reconciliation and the write-up (deployment name on Foundry). There is no `BOARD_MODEL_A`; this is the variable for Run A |
| `BOARD_MODEL_B` | `claude-sonnet-5` | Run B's model, used only when `BOARD_CONSISTENCY_RUNS=2`. Set it to the same model as `BOARD_MODEL` (e.g. `claude-opus-5`) so the two runs are equally strong and the reconciliation does not favour a weaker reading. A deployment of this name must exist on Foundry; the run checks it first and stops with a clear message if not |
| `BOARD_CONSISTENCY_RUNS` | `1` | `1` = a single run. `2` = Run A (`BOARD_MODEL`) and Run B (`BOARD_MODEL_B`) research independently and in parallel (about double the tokens, similar wall-clock time), both with the same document fact sheets; the model reconciles every indicator they scored differently, its recommendation is the final score, and the report shows how many of the 22 scores matched. Outside-in only: inside-out is always a single run. Restart the backend after changing it |
| `BOARD_MIN_FETCHES`, `BOARD_MIN_FETCHES_PEER` | `20`, `12` | page reads below which a company / peer is sent back to read more before its scores are accepted |
| `BOARD_REVIEW_ROUNDS` | `2` | maximum retrieval-review rounds per subject (`0` = off) |
| `BOARD_EFFORT` | `high` | reasoning effort (both runs) |
| `BOARD_WEB_TOOLS` | `latest` (`basic` on Foundry) | web tool version; `latest` overrides the Foundry default |
| `BOARD_SEARCH_USES` | `90` | max web searches per subject (`BOARD_PIPELINE=single` only) |
| `BOARD_PIPELINE` | `tasks` | `tasks`: retrieval as short independent tasks (one per retrieval item, the registers, each event-sweep query), the engine writes the Rule 16 log, one scoring conversation scores from the evidence ledger; `single`: one long conversation per subject (the v1.3 first port) |
| `BOARD_TASK_SEARCHES` / `BOARD_TASK_FETCHES` | `8` / `8` | ceilings for one retrieval task |
| `BOARD_SCORER_SEARCHES` / `BOARD_SCORER_FETCHES` | `12` / `8` | ceilings for the scoring conversation (it closes gaps only) |
| `BOARD_TASK_CALLS` | `12` | retrieval tasks running at once, across all subjects |
| `BOARD_TASK_MODEL` / `BOARD_TASK_EFFORT` | unset | model and effort for retrieval tasks; unset = the subject's own model and `BOARD_EFFORT` (no downgrade) |
| `BOARD_FACTSHEET_CATEGORIES` | `Proxy / circular,Annual / ESG report,Transcript` | document categories that get a fact sheet (`all` = every file; the rest are searched in full); `BOARD_FACTSHEET_PARALLEL` (16) sections at once |
| `BOARD_MIN_DOC_CITES` | `3` | supplied documents a subject's scores must cite (as `provided: <Cite as label>`); `0` turns the check off |
| `BOARD_DOC_ANALYSIS` | `all` | fact sheets (with fields and red flags, every section read, coverage recorded): `all` documents, `company` only, `off` |
| `BOARD_FACTSHEET_MAX_TOKENS` | `0` | cap on document text read for fact sheets per run; 0 = read all of it |
| `BOARD_ANCHOR_RECHECK` | `on` | after grading, every score in `BOARD_RECHECK_SCORES` is read again, strictly, against the anchors; where the second reading differs it replaces the first score and the change is listed in a table at the end of the report (an addition to the skill) |
| `BOARD_RECHECK_SCORES` | `2,4,5` | the scores the recheck reads again: not 1 (Rule 3 already guards it) and not 3 (the landing point for mixed facts) |
| `BOARD_RECHECK_MODEL` | unset | model for the recheck; unset = `BOARD_MODEL` |
| `BOARD_FETCH_USES` | `60` | max page fetches per subject |
| `BOARD_FETCH_TOKENS` | `30000` | token budget per fetched page |
| `BOARD_SKILL_DIR` | `<root>/skill` | location of the skill references |
| `BOARD_SECTOR` | inferred | sector pack for the retrieval registers (`energy` or `general`, see `skill/assets/retrieval_spec.json`); by default `energy` when a company or peer name looks like an oil, gas or energy company, otherwise `general` (each subject then names its own sector register) |

### Rules v1.3: retrieval log and fact sheet

The skill is on v1.3 (`skill/references/changelog.md`). Each subject's research prompt carries a checklist built from `skill/assets/retrieval_spec.json`: the eight retrieval items (R1 to R8), the sector registers, a filing sweep and fourteen event-sweep queries to the as-of date (today), and a fact sheet per indicator. The subject submits the filled log and fact sheet with its scores. `app/domain/retrieval.py` (a port of the skill's `retrieval_checks.py`) holds the grade until every entry is complete (Rule 16), checks each evidence item's source type, class, outlet and time window (Rule 17) and recomputes the RECENT flag. Runs made under v1.2 stay viewable but are not compared with v1.3 runs. Midpoints round down throughout. With `BOARD_CONSISTENCY_RUNS=2`, the model reconciles the two runs (Rules 18-19) and brings the fact-sheet entries behind each adopted cell across.

## Layout

`app/config.py log.py db.py models.py schemas.py main.py` core; `app/api/` routes (`assessments`, `survey`, `reference`,
`uploads`, `errors`); `app/services/repo.py` persistence (replaces `server/store.py`), `jobs.py`, `storage.py`,
`runs.py` (grade, history, build deliverables, job bodies; replaces `server/pipeline.py`).


## How uploaded documents are identified

No register is needed. Each file is identified from its cover page (`app/services/register.py`): category, what it really is, period, date, and the label it is cited by (for example `CBRE FY2025 10-K`). The file name is only a fallback, so a code name or a wrong name does not matter. A file the cover rules cannot place is compared with what the app has learned from earlier document registers (`app/services/doclearn.py`), and if nothing learned fits, a model is shown the cover page and the closest lessons and asked. Files filed under the wrong company and duplicate copies are set aside; gaps (no annual filing, fewer than three proxies, fewer than four call transcripts) are listed. If an A&M register (Excel) is among the uploaded files it overrides all of this and the app learns from it. Teach it ahead of time with `python scripts/learn_register.py <register.xlsx> <zips or folders>`; the store is `storage/learned/documents.json` (word lists from cover pages only).

Documents and research run side by side: the files are read, identified and summarised in a background thread while the web research runs, and the scoring step waits for them only if they are not ready. If preparing them fails, the run stops at scoring with the reason; the research is saved (see `BOARD_TASK_CACHE`), so a rerun does not pay for it again.

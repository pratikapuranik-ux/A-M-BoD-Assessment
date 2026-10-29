# Architecture

    frontend (React 18 + TS, Vite)                     backend (FastAPI)                         skill/
    ───────────────────────────────                    ─────────────────                         ──────
    pages/ ── TanStack Query (api/queries.ts) ──/api──> api/assessments.py ──> services/runs.py
      │        polls a run every 1 s                    api/reference.py         │ BackgroundTasks
      │                                                                          ▼
    store/ (Zustand: session, inside-out draft)          agents/graph.py  (LangGraph StateGraph)
    report/ (views, visx + Recharts charts)                read_material → load_history → score
                                                           → rule_check → deliver
                                                             │            │          │
                                                   services/documents   domain/engine.py ──> scripts/grade.py
                                                   (pdfplumber, pypdf,    (port of js/engine.js,  (compute_subject,
                                                    python-docx,           js/rules.js)            validate_subject)
                                                    openpyxl)                         │
                                                   services/sources        services/deliverables ──> scripts/build_docx.py,
                                                   (httpx + tenacity)      services/pdf_summary      build_dashboard.py, …
                                                                           (reportlab)              (subprocess)
                                                   SQLAlchemy 2.0 models ── SQLite nexus.db (Alembic migrations)

**One source of truth for the rules.** `skill/scripts/grade.py` computes and validates grades. The backend imports it
(`app/domain/skill.py`) rather than re-implementing it; `app/domain/engine.py` adds what the app needs around it:
inside-out re-scoring from the material actually supplied (Part D), trend history, prior-action status, the run object
and the language guardrails. The browser no longer grades anything. It renders the model returned by the API.

**Data.** `assessments` (company, period, mode, prior option, status), `stage_runs` (one per pipeline execution, with
step progress, the run in `run.json` shape and the graded model), `uploaded_files` (public reports, board documents,
other material, prior run files with their parsed history entry) and `deliverables` (files built per stage). Uploads
and outputs live under `NEXUS_STORAGE_DIR/<assessment id>/`.

**Inside-out preview.** `POST /api/assessments/{id}/inside-out/preview` re-scores without storing anything, so the
input page shows how many indicators the selected documents settle, and flags language issues as the director types.

**Scoring is live.** `app/agents/` (LangGraph) researches the company and every peer with Claude and web search, and the
model scores each of the 22 indicators against the anchors. Nothing is replayed from `app/data/example_view.json` or
`skill/example_runs` (tests only). Every research run is a fresh, standalone assessment (`NEXUS_REUSE_HISTORY=1` opts back
in to attaching earlier quarters). Only the Rule 6/7 arithmetic is code (`app/domain/engine.py`). See `backend/README.md`
for the research settings. For Postgres, set `NEXUS_DATABASE_URL` and add a driver; migrations are dialect-neutral.

**Legacy prototype.** `index.html`, `js/`, `css/` and `tests/engine.test.js` are the earlier static version. Its
`js/data/chevron.js` and `js/data/downloads.js` are not in this folder, so it no longer runs as-is. The example content
it used is preserved in `backend/app/data/example_view.json` (converted from `tests/fixtures/example_view.js`).

# A&M Board Assessment: Day 1 / Day 2

Grades a listed company's board A to F on six Day 1 / Day 2 dimensions and 22 indicators, in two stages
(outside-in, then optional inside-out), with a Word report, an HTML dashboard and a PDF summary per stage.
Worked example: **Chevron** against **ExxonMobil** and **BP**.

## Tech stack

**Backend** (`backend/`)

| Layer | Technology |
|---|---|
| Runtime | Python 3.12+ |
| API | FastAPI + Uvicorn |
| Agent orchestration | LangGraph |
| ORM / DB | SQLAlchemy 2.0 + Alembic |
| Database (MVP) | SQLite (`sqlite:///./nexus.db`) → Postgres planned |
| HTTP clients | httpx |
| Resilience | tenacity (retries) |
| Logging | structlog |
| PDF/Docs | pypdf, pdfplumber, python-docx, openpyxl, reportlab |

**Frontend** (`frontend/`)

| Layer | Technology |
|---|---|
| Framework | React 18 + TypeScript |
| Build | Vite |
| Routing | React Router v6 |
| Server state | TanStack Query |
| Client state | Zustand |
| Styling | Tailwind CSS + Radix UI + Preline |
| Charts | Recharts, @visx |
| Animation | Framer Motion |

## Run it

Needs Python 3.12+ and Node.js 18.18+.

```powershell
# 1. API on http://localhost:8000  (creates ./nexus.db and runs Alembic migrations on startup)
cd backend
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONUTF8 = "1"
uvicorn app.main:app --reload --port 8000

# 2. Web app on http://localhost:5173  (Vite proxies /api to :8000)
cd frontend
npm install
npm run dev
```

On macOS or Linux use `source .venv/bin/activate` and `export PYTHONUTF8=1`. In VS Code, **Terminal > Run Task** has
"API (uvicorn)" and "Web (vite)". Interactive API docs: http://localhost:8000/docs.

Tests: `cd backend; pytest` (grading engine against the 23 Oct 2026 report, rule checks, guardrails, API smoke
test) and `cd frontend; npm run typecheck`.

### Configuration (environment variables, all optional)

| Variable | Default | Purpose |
|---|---|---|
| `NEXUS_DATABASE_URL` | `sqlite:///./nexus.db` | SQLAlchemy URL. For Postgres, add a driver (e.g. `psycopg[binary]`) and use `postgresql+psycopg://…` |
| `NEXUS_SKILL_DIR` | `../skill` | The skill's scripts and example runs |
| `NEXUS_STORAGE_DIR` | `backend/storage` | Uploads and built deliverables, one folder per assessment |
| `NEXUS_CORS_ORIGINS` | `http://localhost:5173` | Comma-separated |
| `NEXUS_LOG_JSON` | `0` | `1` for JSON log lines (structlog) |
| `NEXUS_CHECK_SOURCE_URLS` | `0` | `1` to check cited source URLs during the outside-in run (httpx + tenacity) |
| `NEXUS_MIGRATE_ON_STARTUP` | `1` | Or run `alembic upgrade head` yourself |

## Try the flow
Sign in (demo, nothing is checked) > **New assessment** > tick the listed confirmation > Generate. Upload
`skill/example_runs/prior_2026-Q3_simulated_run.json` under *Earlier assessments* to see trend parsing. In inside-out,
use **Fill with simulated material**, or return the filled questionnaire from the simulated ZIP
(`15_Self_Assessment_Questionnaire_FILLED.docx`) to see it parsed. Grades re-score live as documents are ticked.

## Where things are
| Folder | What |
|---|---|
| `backend/app/domain/` | Grading engine (`engine.py`), bridge to the skill's `grade.py` (`skill.py`), example content |
| `backend/app/agents/graph.py` | LangGraph stage pipeline: read material → history → score → rule check → deliverables |
| `backend/app/services/` | Document text extraction, questionnaire parser, source checks, deliverable builders, PDF summary, run executor |
| `backend/app/api/` | FastAPI routers; `backend/alembic/` migrations |
| `frontend/src/` | React app: `pages/` (landing, home, Briefcase, journey), `report/` (report views and charts), `api/`, `store/` |
| `skill/` | The skill: scripts (source of truth for scoring rules), references, `framework.json`, example run files |
| `docs/` | `ARCHITECTURE.md`, `SPEC_COVERAGE.md`, `SHARING.md` |
| `index.html`, `js/`, `css/`, `tests/`, `tools/` | **Legacy** static prototype, kept for reference until the React app is signed off |

## Real vs simulated
Outside-in grades, rationale and 108 sources are from the 23 Oct 2026 Chevron report. Inside-out documents, self-assessment
answers, the prior quarter (2026-Q3) and prior-action status are **simulated** and labelled. Sign-in and notifications are
demo only. The run pipeline replays the 23 Oct run rather than retrieving sources, and the Word and HTML deliverables are
rendered by the skill's scripts from its example run files. On-screen grades and the PDF summary follow the material
actually supplied. Midpoints round down everywhere (2.5 is a D).

DRAFT ONLY. Requires review and approval by a qualified Alvarez and Marsal professional before use.

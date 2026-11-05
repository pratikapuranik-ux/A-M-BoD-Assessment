# A&M Board Assessment: Day 1 / Day 2

Grades a listed company's board A to F on six Day 1 / Day 2 dimensions and 22 indicators, in two stages
(outside-in, then optional inside-out), with a Word report, an HTML dashboard and a PDF summary per stage.

## Tech stack

**Backend** (`backend/`)

| Layer | Technology |
|---|---|
| Runtime | Python 3.12+ |
| API | FastAPI + Uvicorn |
| Agent orchestration | LangGraph |
| ORM / DB | SQLAlchemy 2.0 + Alembic |
| Database (MVP) | SQLite (`sqlite:///./bod_assessment.db`) → Postgres planned |
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
# 1. API on http://localhost:8000  (creates ./bod_assessment.db and runs Alembic migrations on startup)
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

Copy `.env.example` to `.env` in the project root to configure the backend locally. Live research requires valid Anthropic or Microsoft Foundry credentials; without them, the application runs but live research is disabled.

| Variable | Default | Purpose |
|---|---|---|
| `BOARD_DATABASE_URL` | `sqlite:///./bod_assessment.db` | SQLAlchemy URL. For Postgres, add a driver (e.g. `psycopg[binary]`) and use `postgresql+psycopg://…` |
| `BOARD_SKILL_DIR` | `../skill` | The skill's scripts and example runs |
| `BOARD_STORAGE_DIR` | `backend/storage` | Uploads and built deliverables, one folder per assessment |
| `BOARD_CORS_ORIGINS` | `http://localhost:5173` | Comma-separated |
| `BOARD_LOG_JSON` | `0` | `1` for JSON log lines (structlog) |
| `BOARD_CHECK_SOURCE_URLS` | `0` | `1` to check cited source URLs during the outside-in run (httpx + tenacity) |
| `BOARD_MIGRATE_ON_STARTUP` | `1` | Or run `alembic upgrade head` yourself |

## Try the flow
Sign in > **New assessment** > tick the listed confirmation > Generate. Every run is a fresh research run: nothing is
pre-loaded, simulated or replayed, and no earlier assessment is attached to it. In inside-out, add your own board
documents and invite directors to the anonymous self-assessment. Grades re-score live as documents are ticked.

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

## Data in this app
Nothing is simulated, replayed or pre-loaded. Every assessment is researched live by Claude from public sources (and from
any documents you supply); the app ships no example company, prior quarter or sample answers. Sign-in is a local
convenience and notifications are not sent. Midpoints round down everywhere (2.5 is a D).

DRAFT ONLY. Requires review and approval by a qualified Alvarez and Marsal professional before use.

"""Static settings and paths for the research agents (model, provider, budgets, retry waits).

Values come from the environment (BOARD_MODEL, ANTHROPIC_*, ANTHROPIC_FOUNDRY_*, BOARD_WEB_TOOLS). Modules read the
tunable ones as attributes (``settings.RETRY_WAITS``) at call time so tests can patch them.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

AGENTS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = AGENTS_DIR.parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
PROMPTS = AGENTS_DIR / "prompts"


def _skill_dir() -> Path:
    for cand in (os.environ.get("BOARD_SKILL_DIR"), PROJECT_ROOT / "skill", BACKEND_DIR / "skill"):
        if cand and (Path(cand) / "assets" / "framework.json").exists():
            return Path(cand)
    return PROJECT_ROOT / "skill"


SKILL = _skill_dir(); SCRIPTS = SKILL / "scripts"; REFS = SKILL / "references"
FW = json.loads((SKILL / "assets" / "framework.json").read_text(encoding="utf-8"))
IND_IDS = [i["id"] for i in FW["indicators"]]; DIMS = sorted(FW["dimensions"], key=int)
PEER_RELATIVE = FW["peer_relative"]
REF_FILES = ["guardrails.md", "framework.md", "outside_in_overrides.md", "scoring_rules.md", "sources.md", "inside_out_documents.md", "data_model.md"]

MODEL = os.environ.get("BOARD_MODEL") or "claude-opus-5"  # Run A, the reconciliation and the final write-up
MODEL_B = os.environ.get("BOARD_MODEL_B") or "claude-sonnet-5"  # Run B: the independent second run (a deployment of this name must exist on Foundry)
DOC_INLINE_TOKENS = 60_000  # supplied documents on one subject up to this size are sent whole; more are searched instead
DOC_SEARCHES = 80  # searches of the supplied documents one subject may make
OCR_MODEL = os.environ.get("BOARD_OCR_MODEL") or MODEL_B  # reads scanned pages and images into text (services/ocr.py)
# Microsoft Foundry (Azure) instead of the Claude API when its key and resource are set. Foundry has no server-side
# fallback, and Azure-hosted deployments take only the basic web tools (BOARD_WEB_TOOLS=latest overrides).
FOUNDRY = bool(os.environ.get("ANTHROPIC_FOUNDRY_API_KEY") and (os.environ.get("ANTHROPIC_FOUNDRY_RESOURCE") or os.environ.get("ANTHROPIC_FOUNDRY_BASE_URL")))
BETAS = [] if FOUNDRY else ["server-side-fallback-2026-07-01"]
LATEST_WEB = (os.environ.get("BOARD_WEB_TOOLS") or ("basic" if FOUNDRY else "latest")) == "latest"
PROVIDER = "Microsoft Foundry" if FOUNDRY else "Anthropic"
EFFORT = os.environ.get("BOARD_EFFORT") or "high"
MAX_TOKENS = 64000
HEARTBEAT = 30  # seconds between 'still working' progress lines
def _int_env(name, default, lo=1):
    try: return max(lo, int(os.environ.get(name) or default))
    except ValueError: return default


# Per-subject ceilings on web_search / web_fetch; the Rule 14 retrieval set cannot be covered with fewer (BOARD_* override)
SEARCH_USES, FETCH_USES, FETCH_TOKENS = _int_env("BOARD_SEARCH_USES", 90), _int_env("BOARD_FETCH_USES", 60), _int_env("BOARD_FETCH_TOKENS", 30000)
SEARCH_BUDGET, FETCH_BUDGET = SEARCH_USES, FETCH_USES
# Context ceiling (the model takes 1,000,000 tokens): once a conversation passes PRUNE_AT tokens, the text of fetched pages older than
# the newest KEEP_RECENT pages is replaced by a stub that keeps the URL and title
PRUNE_AT, KEEP_RECENT = _int_env("BOARD_CONTEXT_PRUNE_AT", 400000, lo=50000), _int_env("BOARD_CONTEXT_KEEP_RECENT", 8, lo=0)
DOC_TOOL_TOKENS = _int_env("BOARD_DOC_TOOL_TOKENS", 300000, lo=20000)  # text one subject may be given by the search and page tools in all
KEEP_RECENT_DOCS = _int_env("BOARD_CONTEXT_KEEP_RECENT_DOCS", 10, lo=0)  # newest search and page results kept in view; older ones are cut like fetched web pages
# Retrieval review: a subject that has read fewer pages than this floor (or still lists Rule 14 documents as unavailable) is sent
# back to read more before its scores are accepted. REVIEW_ROUNDS=0 switches the review off.
# Supplied documents a subject's scores must cite (as 'provided: <file>' evidence): the lower of this and the number of readable files supplied on it
MIN_DOC_CITES = _int_env("BOARD_MIN_DOC_CITES", 3)
MIN_FETCHES, MIN_FETCHES_PEER =_int_env("BOARD_MIN_FETCHES", 20), _int_env("BOARD_MIN_FETCHES_PEER", 12)
REVIEW_ROUNDS = _int_env("BOARD_REVIEW_ROUNDS", 1, lo=0)  # one retrieval review: a second round cost minutes and rarely changed a score
# Rule 18: every outside-in assessment is run this many times on the same rule version and the runs are compared (1 = no test)
CONSISTENCY_RUNS = 2 if (os.environ.get("BOARD_CONSISTENCY_RUNS") or "1").strip() == "2" else 1  # 2: Run A / Run B in parallel, then reconciled (graph._run_two)
# Research pipeline. "tasks" (default): the Rule 16 retrieval work is split into short independent tasks (one per retrieval item, one for the
# registers, one per event-sweep query), each in its own small conversation; the engine writes the retrieval log from them, and one scoring
# conversation scores from the evidence they found plus the supplied documents. "single": one long conversation per subject does it all.
# Anchor recheck: after the scores pass the engine's checks, every score in RECHECK_SCORES is read again, strictly, against the written
# anchors (services/audit.py). Where the second reading differs, its score replaces the first and the change is listed in the report. RECHECK_MODEL
# unset = BOARD_MODEL. An addition to the skill, disclosed in the report.
# A finished retrieval task is kept on disk (same subject, task, day, model, limits): a crash or a rerun pays only for what was not finished.
TASK_CACHE = (os.environ.get("BOARD_TASK_CACHE") or "on").strip().lower() not in ("off", "0", "false", "no")
RECHECK = (os.environ.get("BOARD_ANCHOR_RECHECK") or "on").strip().lower() not in ("off", "0", "false", "no")
# Scores read again: 4 and 5 (the generous end), and 2. Not 1 (Rule 3 already requires two documents or a strong item) and not 3 (the landing point for mixed facts).
RECHECK_SCORES = tuple(sorted({int(x) for x in (os.environ.get("BOARD_RECHECK_SCORES") or "2,4,5").replace(" ", "").split(",") if x.isdigit() and 1 <= int(x) <= 5}))
RECHECK_MODEL = os.environ.get("BOARD_RECHECK_MODEL") or None
PIPELINE = "single" if (os.environ.get("BOARD_PIPELINE") or "tasks").strip().lower() == "single" else "tasks"
TASK_SEARCHES, TASK_FETCHES = _int_env("BOARD_TASK_SEARCHES", 8), _int_env("BOARD_TASK_FETCHES", 8)  # ceilings for one retrieval task
SCORER_SEARCHES, SCORER_FETCHES = _int_env("BOARD_SCORER_SEARCHES", 12), _int_env("BOARD_SCORER_FETCHES", 8)  # to close gaps while scoring
TASK_MODEL, TASK_EFFORT = os.environ.get("BOARD_TASK_MODEL") or None, os.environ.get("BOARD_TASK_EFFORT") or None  # unset: the subject's own model and BOARD_EFFORT, as for scoring
TASK_CALLS = _int_env("BOARD_TASK_CALLS", 12)  # retrieval tasks running at once, across all subjects
MAX_CONTINUATIONS, MAX_JSON_RETRIES, MAX_FIX_ROUNDS, SUBJECT_WORKERS = 8, 2, 3, 6  # company and up to five peers at once
MODEL_CALL_SLOTS = _int_env("BOARD_MODEL_CALLS", 8)  # subjects researching at once across both consistency runs (2 runs x 4 subjects = 8)
CACHE = {"type": "ephemeral", "ttl": "1h"}
PEER_PREFIXES = "XBKLN"
BLOCKED = ["facebook.com", "glassdoor.com", "indeed.com", "instagram.com", "linkedin.com", "medium.com",
           "quora.com", "reddit.com", "tiktok.com", "twitter.com", "x.com"]
RETRY_WAITS = (15, 30, 60, 90)  # seconds before each app-level retry while the service is busy; tests set zeros
BUSY_STATUS = {429, 500, 502, 503, 529}

PERIOD_RE = re.compile(r"^\d{4}-Q[1-4]$"); DATE_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
CODE_RE = re.compile(r"^(?:[EXBKLN]\d{2,3}|IO\d{2}|SA\d{2})$")
BLOCK_RE = re.compile(r"^\s*BLOCK \[(.*?)\] (.*?): (.*)$", re.M)
AM_RE = re.compile(r"\bA&M\b|Alvarez", re.I)
# Backstop for the Writing rules in system.md (the prompt is the primary control): the mechanical tells of a figurative
# register. Deliberately narrow - every alternative is an idiom or a personification with no literal use in a board
# report, so a hit is a rewrite and not a judgement call. A new metaphor is the prompt's job, not this pattern's.
STYLE_RE = re.compile(
    r"\bteeth\b(?!\s*whitening)|\bpunch(?:es|ed|ing)?\s+above\b|\bmov(?:e|es|ed|ing)\s+the\s+needle\b"
    r"|\blow[- ]hanging\s+fruit\b|\bboil(?:ing)?\s+the\s+ocean\b|\bkick(?:s|ed|ing)?\s+the\s+can\b"
    r"|\bcanary\s+in\s+the\s+coal\b|\belephant\s+in\s+the\s+room\b|\bfiring\s+on\s+all\s+cylinders\b"
    r"|\bdouble[- ]edged\s+sword\b|\bsacred\s+cow|\bnorth\s+star\b|\blean(?:s|ed|ing)?\s+into?\b"
    r"|\btells?\s+a\s+story\b|\btip\s+of\s+the\s+iceberg\b|\bgreen\s+shoots\b|\bskin\s+in\s+the\s+game\b"
    r"|\bsea\s+change\b", re.I)
CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

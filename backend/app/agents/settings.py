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
    for cand in (os.environ.get("NEXUS_SKILL_DIR"), PROJECT_ROOT / "skill", BACKEND_DIR / "skill"):
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


# Per-subject ceilings on web_search / web_fetch; the Rule 15 retrieval set cannot be covered with fewer (BOARD_* override)
SEARCH_USES, FETCH_USES, FETCH_TOKENS = _int_env("BOARD_SEARCH_USES", 60), _int_env("BOARD_FETCH_USES", 60), _int_env("BOARD_FETCH_TOKENS", 30000)
SEARCH_BUDGET, FETCH_BUDGET = SEARCH_USES, FETCH_USES
# Context ceiling (the model takes 1,000,000 tokens): once a conversation passes PRUNE_AT tokens, the text of fetched pages older than
# the newest KEEP_RECENT pages is replaced by a stub that keeps the URL and title
PRUNE_AT, KEEP_RECENT = _int_env("BOARD_CONTEXT_PRUNE_AT", 400000, lo=50000), _int_env("BOARD_CONTEXT_KEEP_RECENT", 8, lo=0)
# Retrieval review: a subject that has read fewer pages than this floor (or still lists Rule 15 documents as unavailable) is sent
# back to read more before its scores are accepted. REVIEW_ROUNDS=0 switches the review off.
MIN_FETCHES, MIN_FETCHES_PEER = _int_env("BOARD_MIN_FETCHES", 20), _int_env("BOARD_MIN_FETCHES_PEER", 12)
REVIEW_ROUNDS = _int_env("BOARD_REVIEW_ROUNDS", 2, lo=0)
# Rule 12: every outside-in assessment is run this many times on the same rule version and the runs are compared (1 = no test)
CONSISTENCY_RUNS = _int_env("BOARD_CONSISTENCY_RUNS", 1)  # set 2 for Run A (BOARD_MODEL) plus Run B (BOARD_MODEL_B) and reconciliation
MAX_CONTINUATIONS, MAX_JSON_RETRIES, MAX_FIX_ROUNDS, SUBJECT_WORKERS = 8, 2, 3, 6  # company and up to five peers at once
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
CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

"""Grading bridge: runs the rule engine on a copy of a run and returns (blocking problems, graded run).

Problems are (subject name, where, message) tuples so fixes can be routed to the conversation that caused them.
app.domain.engine.grade is the single source of truth for the rules; if it fails the run fails with a clear error.
"""
from __future__ import annotations

import copy
import re

import structlog

from . import settings as cfg
from .client import ResearchError

log = structlog.get_logger("agents.grading")
_TUPLE_RE = re.compile(r"^\s*(?:BLOCK\s+)?\[(.*?)\]\s+(.*?):\s+(.*)$", re.S)


def _parse(p):
    if isinstance(p, (tuple, list)) and len(p) == 3: return tuple(p)
    if isinstance(p, str):
        m = _TUPLE_RE.match(p)
        if m: return m.groups()
    return None


def grade_run(run):
    """Grade a copy with the rule engine. An engine failure is an error: no silent fallback to another grader."""
    from app.domain import engine
    graded = copy.deepcopy(run)
    try:
        res = engine.grade(graded, check=False)  # writes "computed" into the copy's subjects
    except Exception as e:
        log.error("engine_grade_failed", error=str(e))
        raise ResearchError(f"The grading engine failed: {e}") from e
    if not isinstance(res, dict) or not all("computed" in s for s in graded.get("subjects", [])):
        raise ResearchError("The grading engine did not return computed grades for every subject.")
    problems = [_parse(p) for p in res.get("problems", [])]  # "[subject] where: message" -> (subject, where, message)
    if any(p is None for p in problems):
        raise ResearchError("The grading engine returned a problem it could not route: " + "; ".join(str(p) for p in res["problems"][:3]))
    return problems, graded

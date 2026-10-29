"""Tool schemas (strict client tools and the server-side web tools) and prompt loading."""
from __future__ import annotations

import functools
from string import Template

from . import settings as cfg
from .settings import FW, IND_IDS, DIMS

S = {"type": "string"}; BOOL = {"type": "boolean"}


def _arr(x): return {"type": "array", "items": x}
def _enum(*v): return {"type": "string", "enum": list(v)}
def _obj(**props): return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}
def _tool(name, desc, schema): return {"name": name, "description": desc, "strict": True, "input_schema": schema}


CELL = dict(id=_enum(*IND_IDS), score={"type": "integer", "enum": [0, 1, 2, 3, 4, 5]},
            confidence=_enum("High", "Medium", "Low", "None"), na_cause=_enum(*FW["na_causes"], "none"),
            evidence=_arr(S), rationale=S)
ACTION = _obj(heading=S, description=S, improves=S, measures=_arr(S), target_by=S)  # improves: which indicators it should raise and how
OI_CLASSES = [c for c in FW["evidence_classes"] if c not in ("inside_out", "self_assessment")]

SUBJECT_TOOL = _tool("submit_subject_assessment",
    "Submit the scored assessment of one subject's board. Call it once research is complete, with all 22 indicators. "
    "When asked to revise, call it again with only the indicators, evidence items, dimensions and comparables that change; "
    "empty lists keep what was submitted before.",
    _obj(indicators=_arr(_obj(**CELL, summary=S)),
         evidence=_arr(_obj(code=S, document=S, doc_type=S, date=S, url=S, excerpt=S, evidence_class=_enum(*OI_CLASSES), search_log=S)),
         dimensions=_arr(_obj(dimension=_enum(*DIMS), assessment_text=S, limitations=S)),
         comparables=_arr(_obj(metric=S, value=S, evidence=S)),
         documents_unavailable=_arr(S)))
SYNTH_TOOL = _tool("submit_synthesis",
    "Submit the narrative fields of the outside-in run. Call it once with every field; when asked to revise, resubmit "
    "with the fields that change (empty strings and lists keep what was submitted before).",
    _obj(headline=S, overall_summary=S, what_moved=S, headline_findings=_arr(S),
         key_metrics=_arr(_obj(metric=S, why=S, current=S)), peer_position=S, peer_summary_lines=_arr(S),
         scorecard_headline=_arr(_obj(key=_enum(*DIMS, "7"), text=S)),
         peer_row_summary=_arr(_obj(dimension=_enum(*DIMS), text=S)),
         peer_summaries=_arr(_obj(ticker=S, summary=S)), actions=_arr(ACTION), additional_information_needed=_arr(S)))
IO_TOOL = _tool("submit_inside_out",
    "Submit the post inside-out cells and narrative for the company. Call it once with all 22 cells; when asked to "
    "revise, resubmit with what changes (empty strings and lists keep what was submitted before).",
    _obj(cells=_arr(_obj(**CELL, carried_forward=BOOL)), documents=_arr(_obj(code=S, date=S, excerpt=S)),
         headline=S, overall_summary=S, what_moved=S, better=_arr(S), worse=_arr(S), headline_findings=_arr(S),
         io_change_notes=_arr(_obj(id=_enum(*IND_IDS), note=S)), actions=_arr(ACTION),
         prior_actions_status=_arr(_obj(id=S, status=_enum(*FW["action_statuses"]), evidence_note=S, metrics_note=S)),
         back_on_track=_arr(_obj(id=S, what_happened=S, impact=S, root_cause=S, prevention=S, measures=_arr(S))),
         additional_information_needed=_arr(S)))
RECON_TOOL = _tool("submit_reconciliation",
    "Submit your recommendation for every indicator on which the two runs gave different scores: which run's score and rationale stands, "
    "and why. Call it once with one item per disputed indicator.",
    _obj(items=_arr(_obj(indicator=_enum(*IND_IDS), choice=_enum("A", "B"), reason=S))))
WEB_TOOLS = [{"type": "web_search_20260209" if cfg.LATEST_WEB else "web_search_20250305", "name": "web_search",
              "max_uses": cfg.SEARCH_USES, "blocked_domains": cfg.BLOCKED},
             {"type": "web_fetch_20260209" if cfg.LATEST_WEB else "web_fetch_20250910", "name": "web_fetch", "max_uses": cfg.FETCH_USES,
              "max_content_tokens": cfg.FETCH_TOKENS, "blocked_domains": cfg.BLOCKED}]
SUBJECT_KEYS = {"indicators": "id", "evidence": "code", "dimensions": "dimension", "comparables": "metric"}
SYNTH_KEYS = {"scorecard_headline": "key", "peer_row_summary": "dimension", "peer_summaries": "ticker"}
IO_KEYS = {"cells": "id", "documents": "code", "io_change_notes": "id", "prior_actions_status": "id", "back_on_track": "id"}


@functools.lru_cache(maxsize=1)
def system_blocks():
    """The cached system prompt: the house prompt plus the methodology reference files."""
    parts = [(cfg.PROMPTS / "system.md").read_text(encoding="utf-8").strip()]
    for f in cfg.REF_FILES:
        text = (cfg.REFS / f).read_text(encoding="utf-8")
        if f == "sources.md":  # the file repeats its last four sections verbatim
            h = "## Approved news list"; second = text.find(h, text.find(h) + 1)
            text = text[:second] if second > 0 else text
        parts.append(f'<reference file="{f}">\n{text.strip()}\n</reference>')
    # the skill itself, read from skill/ at import time so it stays the single source of truth
    skill = (cfg.SKILL / "SKILL.md").read_text(encoding="utf-8").strip()
    parts.append('<reference file="SKILL.md">\nScripts are run by the harness, so ignore the bash steps and follow the scoring, evidence, '
                 f'synthesis, Stage 2 and delivery guidance.\n\n{skill}\n</reference>')
    return [{"type": "text", "text": "\n\n".join(parts), "cache_control": cfg.CACHE}]


def render_prompt(file, **kw):
    return Template((cfg.PROMPTS / file).read_text(encoding="utf-8")).substitute(**kw)

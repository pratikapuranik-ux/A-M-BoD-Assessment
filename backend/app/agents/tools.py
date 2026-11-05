"""Tool schemas (strict client tools and the server-side web tools) and prompt loading."""
from __future__ import annotations

import functools
import os
import re
from string import Template

from . import settings as cfg
from .settings import FW, IND_IDS, DIMS
from app.domain.retrieval import SPEC as RSPEC

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

INT = {"type": "integer"}
SOURCE_TYPES = RSPEC["sources"]["source_types"]
# Rule 16: the retrieval log and the fact sheet. Lists of entries (the strict schema has no free-form keys); the run file keeps them as dicts.
LOG_ITEM = _obj(id=_enum(*[i["id"] for i in RSPEC["retrieval_items"]]), status=_enum("found", "searched_none", "unavailable", "not_applicable"),
                documents=_arr(S), queries=_arr(S), years=_arr(INT), **{"from": S, "to": S}, filings_reviewed=INT, feed=S, reason=S)
LOG_REGISTER = _obj(id=S, status=_enum("searched", "not_applicable"), query=S, date=S, hits=_arr(S), reason=S)
LOG_SWEEP = _obj(id=_enum(*[q["id"] for q in RSPEC["event_sweep"]]), query=S, **{"from": S, "to": S}, results_reviewed=INT, hits=_arr(S))
LOG_FACT = _obj(indicator=_enum(*IND_IDS), field=S, status=_enum("found", "not_disclosed"), value=S, evidence=_arr(S), where_searched=S)
EXTRA_REGISTER = _obj(id=S, name=S, query=S)

SUBJECT_TOOL = _tool("submit_subject_assessment",
    "Submit the scored assessment of one subject's board. Call it once research is complete, with all 22 indicators, the retrieval log "
    "(retrieval_items, registers, event_sweep) and the fact sheet (facts). "
    "When asked to revise, call it again with only the indicators, evidence items, dimensions, comparables and log entries that change; "
    "empty lists keep what was submitted before.",
    _obj(indicators=_arr(_obj(**CELL, summary=S)),
         evidence=_arr(_obj(code=S, document=S, doc_type=S, date=S, event_date=S, url=S, excerpt=S, evidence_class=_enum(*OI_CLASSES), search_log=S,
                            source_type=_enum(*SOURCE_TYPES), outlet=S, underlying_source_type=S)),
         dimensions=_arr(_obj(dimension=_enum(*DIMS), assessment_text=S, limitations=S)),
         comparables=_arr(_obj(metric=S, value=S, evidence=S)),
         retrieval_items=_arr(LOG_ITEM), registers=_arr(LOG_REGISTER), event_sweep=_arr(LOG_SWEEP), facts=_arr(LOG_FACT),
         extra_registers=_arr(EXTRA_REGISTER), extra_trade_press=_arr(S),
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
         # the only self-assessment material that reaches the appendix: themes across respondents, never a quoted answer
         self_assessment_themes=_arr(_obj(dimension=_enum(*DIMS), theme=S, summary=S)),
         headline=S, overall_summary=S, what_moved=S, better=_arr(S), worse=_arr(S), headline_findings=_arr(S),
         io_change_notes=_arr(_obj(id=_enum(*IND_IDS), note=S)), actions=_arr(ACTION),
         prior_actions_status=_arr(_obj(id=S, status=_enum(*FW["action_statuses"]), evidence_note=S, metrics_note=S)),
         back_on_track=_arr(_obj(id=S, what_happened=S, impact=S, root_cause=S, prevention=S, measures=_arr(S))),
         additional_information_needed=_arr(S)))
SEARCH_TOOL = _tool("search_provided_documents",
    "Search the documents the A&M team supplied on this subject. Returns the best matching passages, each with its file name and page. "
    "Use it for each indicator's topic, with more than one wording; pass a file name (or part of one) to search only that file, or an empty string for all.",
    _obj(query=S, file=S))
READ_PAGE_TOOL = _tool("read_provided_page",
    "Read one page of a supplied document exactly as it was extracted, to check a figure or a statement against the source. "
    "Give the file name (or part of it) and the page number.",
    _obj(file=S, page={"type": "integer"}))
RECON_TOOL = _tool("submit_reconciliation",
    "Submit your recommendation for every indicator on which the two runs gave different scores: which run's score and rationale stands, "
    "and why. Call it once with one item per disputed indicator.",
    _obj(items=_arr(_obj(indicator=_enum(*IND_IDS), choice=_enum("A", "B"), reason=S))))
WEB_TOOLS = [{"type": "web_search_20260209" if cfg.LATEST_WEB else "web_search_20250305", "name": "web_search",
              "max_uses": cfg.SEARCH_USES, "blocked_domains": cfg.BLOCKED},
             {"type": "web_fetch_20260209" if cfg.LATEST_WEB else "web_fetch_20250910", "name": "web_fetch", "max_uses": cfg.FETCH_USES,
              "max_content_tokens": cfg.FETCH_TOKENS, "blocked_domains": cfg.BLOCKED}]
SUBJECT_KEYS = {"indicators": "id", "evidence": "code", "dimensions": "dimension", "comparables": "metric", "retrieval_items": "id", "registers": "id",
                "event_sweep": "id", "facts": "_k", "extra_registers": "id"}  # facts carry a composite key, added when they are received
SYNTH_KEYS = {"scorecard_headline": "key", "peer_row_summary": "dimension", "peer_summaries": "ticker"}
IO_KEYS = {"cells": "id", "documents": "code", "io_change_notes": "id", "prior_actions_status": "id", "back_on_track": "id"}


RULING_14 = re.compile(r"\n?<!-- ruling-1\.4:start -->.*?<!-- ruling-1\.4:end -->\n?", re.S)


def ruling_1_4_on() -> bool:
    """The methodology owner's ruling on 1.4 (quality means product and service quality) is applied unless BOARD_RULING_1_4 is off."""
    return (os.environ.get("BOARD_RULING_1_4") or "on").strip().lower() not in ("off", "0", "false", "no")


@functools.lru_cache(maxsize=1)
def system_blocks():
    """The cached system prompt: the house prompt plus the methodology reference files."""
    parts = [(cfg.PROMPTS / "system.md").read_text(encoding="utf-8").strip()]
    for f in cfg.REF_FILES:
        text = (cfg.REFS / f).read_text(encoding="utf-8")
        if f == "framework.md": text = RULING_14.sub("\n", text) if not ruling_1_4_on() else text.replace("<!-- ruling-1.4:start -->\n", "").replace("<!-- ruling-1.4:end -->\n", "")
        if f == "sources.md":  # the file repeats its last four sections verbatim
            h = "## Approved news list"; second = text.find(h, text.find(h) + 1)
            text = text[:second] if second > 0 else text
        parts.append(f'<reference file="{f}">\n{text.strip()}\n</reference>')
    # the skill itself, read from skill/ at import time so it stays the single source of truth
    skill = (cfg.SKILL / "SKILL.md").read_text(encoding="utf-8").strip()
    parts.append('<reference file="SKILL.md">\nScripts are run by the harness, so ignore the bash steps and follow the scoring, evidence, '
                 'synthesis, Stage 2 and delivery guidance. The retrieval log and fact sheet (Rule 16) are submitted with each subject\'s scores, '
                 'and the harness runs the Rule 16-17 checks when it grades. Two runs are reconciled by the harness (step 1.4b), not by the user.'
                 f'\n\n{skill}\n</reference>')
    return [{"type": "text", "text": "\n\n".join(parts), "cache_control": cfg.CACHE}]


def render_prompt(file, **kw):
    return Template((cfg.PROMPTS / file).read_text(encoding="utf-8")).substitute(**kw)

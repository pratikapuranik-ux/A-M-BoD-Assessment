"""Anchor audit: a strict second reading of an assessment's scores against the written anchors.

The research agent scores and explains each indicator in one pass, and its judgement drifts upwards at the boundaries: it names a
Mixed anchor in the rationale and still scores above it, or lets a peer comparison lift a score out of the band of an anchor whose own
test is met. The audit reads only each rationale and the anchors and says which score a strict reader of the anchors would give.
It changes nothing by itself: it returns its findings with the anchor words it relied on.
"""
from __future__ import annotations

import json
import re

from app.log import get_logger
from app.services.usage import record

log = get_logger(__name__)

PROMPT = """You are a strict auditor of a board assessment. Below, for each indicator, are the anchors (scores 1, 3 and 5; 2 and 4 sit between them) and a first-pass score with its rationale. Judge only from the facts stated in each rationale.

Rules for the audit:
- Find the anchor whose own wording, including any measurable test it names, the stated facts match. A score of 5 or 1 needs the facts to match that anchor as written. Use 2 or 4 only when the facts clearly sit between two anchors.
- If the rationale itself says the 3 anchor (or a Mixed anchor) describes the facts, the score is 3, not 4.
- If an anchor names a measurable test and the stated figures meet it (for example, capex below depreciation), that anchor applies even if peers look similar: a peer comparison does not lift a score out of the band of an anchor whose test is met.
- A claim in the rationale that the cited facts do not directly support does not count.
Return only JSON: a list with one object per indicator, {"id", "strict_score", "reason"}; reason is one sentence naming the anchor words relied on.

"""


class AuditError(RuntimeError):
    """The audit could not be made; the message is fit to show the user."""


def _anchors(indicator: dict) -> dict:
    from app.agents import settings as cfg
    return ((cfg.FW.get("outside_in_overrides") or {}).get(indicator["id"]) or {}).get("anchors") or indicator["anchors"]


def build_prompt(items: list[dict]) -> str:
    """items: [{id, name, score, rationale}]; indicators without a score are left out."""
    from app.agents import settings as cfg
    by = {i["id"]: i for i in cfg.FW["indicators"]}
    blocks = []
    for it in items:
        if it.get("score") in (None, 0) or it["id"] not in by: continue
        a = _anchors(by[it["id"]])
        blocks.append(f'<indicator id="{it["id"]}" name="{by[it["id"]]["name"]}">\n<anchor_1>{a["1"]}</anchor_1>\n<anchor_3>{a["3"]}</anchor_3>\n'
                      f'<anchor_5>{a["5"]}</anchor_5>\n<first_pass_score>{it["score"]}</first_pass_score>\n'
                      f'<first_pass_rationale>{it.get("rationale") or ""}</first_pass_rationale>\n</indicator>')
    return PROMPT + "\n".join(blocks)


def _ask(prompt: str, label: str, model: str | None = None) -> str:
    from app.agents import client as C, settings as cfg
    model = model or cfg.MODEL
    try:
        resp = C.call_with_retry(lambda: C.get_client().messages.create(model=model, max_tokens=12000, messages=[{"role": "user", "content": prompt}]), label)
    except Exception as e:  # noqa: BLE001
        sdk = getattr(C, "anthropic", None)
        if sdk is not None and isinstance(e, sdk.AnthropicError): raise AuditError(str(C.api_error(e, label))) from e
        raise AuditError(f"{type(e).__name__}: {e}") from e
    record(label, model, getattr(resp, "usage", None))
    return "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text")


RECHECK_PROMPT = """You are a strict second reader of a board assessment. Below, for each indicator, are the anchors (scores 1, 3 and 5; 2 and 4 sit between them) and a first-pass score with its rationale. Judge only from the facts stated in each rationale.

Rules:
- Find the anchor whose own wording, including any measurable test it names, the stated facts match. A score of 5 or 1 needs the facts to match that anchor as written. Use 2 or 4 only when the facts clearly sit between two anchors.
- If the rationale itself says the 3 anchor (or a Mixed anchor) describes the facts, the score is 3, not 4.
- If an anchor names a measurable test and the stated figures meet it (for example, capex below depreciation), that anchor applies even if peers look similar: a peer comparison does not lift a score out of the band of an anchor whose test is met.
- A claim in the rationale that the cited facts do not directly support does not count.
- Move a score only when the anchors require it; where the first-pass score is the one the anchors give, keep it. A score may move up as well as down.
Return only JSON: a list with one object per indicator, {"key", "strict_score", "reason", "rationale", "summary"}. reason is one sentence naming the anchor words relied on. When your score differs from the first-pass score, also write rationale: the rationale rewritten for your score, two or three sentences (about 50 words), naming the anchor parts met, using only the facts and evidence codes already in the first-pass rationale, declarative and literal, with no metaphor, idiom or personification, and without mentioning the first-pass score, a recheck or a change; and, only where a first-pass summary is given, summary: one line of at most 20 words with the codes. When your score equals the first-pass score, rationale and summary are empty strings.

"""


def build_recheck_prompt(items: list[dict]) -> str:
    """items: [{key, id, score, rationale, summary}] of one subject."""
    from app.agents import settings as cfg
    by = {i["id"]: i for i in cfg.FW["indicators"]}; blocks = []
    for it in items:
        a = _anchors(by[it["id"]])
        blocks.append(f'<indicator key="{it["key"]}" id="{it["id"]}" name="{by[it["id"]]["name"]}">\n<anchor_1>{a["1"]}</anchor_1>\n<anchor_3>{a["3"]}</anchor_3>\n'
                      f'<anchor_5>{a["5"]}</anchor_5>\n<first_pass_score>{it["score"]}</first_pass_score>\n'
                      f'<first_pass_rationale>{it.get("rationale") or ""}</first_pass_rationale>\n'
                      + (f'<first_pass_summary>{it["summary"]}</first_pass_summary>\n' if it.get("summary") else "") + "</indicator>")
    return RECHECK_PROMPT + "\n".join(blocks)


def recheck(items: list[dict], label: str = "anchor recheck", model: str | None = None) -> dict[str, dict]:
    """The recheck of one subject's scores: {key: {strict_score, reason, rationale, summary}}. Raises AuditError."""
    if not items: return {}
    text = _ask(build_recheck_prompt(items), label, model)
    m = re.search(r"\[.*\]", text, re.S)
    try: rows = json.loads(m.group(0)) if m else None
    except ValueError: rows = None
    if not isinstance(rows, list): raise AuditError("the recheck did not return a list of scores")
    out = {}
    for r in rows:
        if not isinstance(r, dict) or not r.get("key"): continue
        try: strict = int(r["strict_score"])
        except (KeyError, TypeError, ValueError): continue
        if 1 <= strict <= 5: out[str(r["key"])] = {"strict_score": strict, "reason": str(r.get("reason") or "").strip(),
                                                    "rationale": str(r.get("rationale") or "").strip(), "summary": str(r.get("summary") or "").strip()}
    return out


def audit(items: list[dict], label: str = "anchor audit") -> list[dict]:
    """The audit of the scored indicators: [{id, name, score, strict_score, reason}], in the order given."""
    scored = [it for it in items if it.get("score") not in (None, 0)]
    if not scored: return []
    text = _ask(build_prompt(scored), label)
    m = re.search(r"\[.*\]", text, re.S)
    try: rows = json.loads(m.group(0)) if m else None
    except ValueError: rows = None
    if not isinstance(rows, list): raise AuditError("the audit did not return a list of scores")
    got = {str(r.get("id")): r for r in rows if isinstance(r, dict)}
    out = []
    for it in scored:
        r = got.get(it["id"])
        try: strict = int(r["strict_score"]) if r else None
        except (KeyError, TypeError, ValueError): strict = None
        if strict is not None and not 1 <= strict <= 5: strict = None
        out.append({"id": it["id"], "name": it.get("name"), "score": it["score"], "strict_score": strict, "reason": (r or {}).get("reason", "")})
    return out

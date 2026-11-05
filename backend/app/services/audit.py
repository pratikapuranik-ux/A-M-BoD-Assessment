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


def _ask(prompt: str, label: str) -> str:
    from app.agents import client as C, settings as cfg
    try:
        resp = C.call_with_retry(lambda: C.get_client().messages.create(model=cfg.MODEL, max_tokens=12000, messages=[{"role": "user", "content": prompt}]), label)
    except Exception as e:  # noqa: BLE001
        sdk = getattr(C, "anthropic", None)
        if sdk is not None and isinstance(e, sdk.AnthropicError): raise AuditError(str(C.api_error(e, label))) from e
        raise AuditError(f"{type(e).__name__}: {e}") from e
    return "".join(getattr(b, "text", "") for b in resp.content if getattr(b, "type", "") == "text")


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

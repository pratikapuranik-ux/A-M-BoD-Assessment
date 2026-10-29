"""Reconciliation of Run A and Run B (Rule 12).

Two independent runs score the same subjects. Where they gave an indicator different scores, the model (Run A's, Opus) is shown
both rationales with their evidence and recommends which run's score and rationale stands. Run A's subjects are changed in place:
a cell where Run B stands takes Run B's score, confidence, rationale and summary, and the evidence it cites is copied into Run A's
evidence list under fresh codes (an item Run A already holds is reused). The returned block is stored as run["reconciliation"].
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor

import structlog

from . import settings as cfg
from .checks import _check_text
from .conversation import Conv
from .settings import FW, IND_IDS
from .tools import RECON_TOOL, render_prompt

log = structlog.get_logger("agents.reconcile")
CITE = re.compile(r"\[([A-Z]{1,2}\d{2,3})\]")
IND = {i["id"]: i for i in FW["indicators"]}


def _cell(subject, ind):
    return next(c for c in subject.data["indicators"] if c["id"] == ind)


def _score(cell):
    return cell.get("score") or 0  # 0 = not assessable


def _shown(score):
    return score or None


def disputes(a, b) -> list[str]:
    """The indicators on which the two runs scored this subject differently."""
    return [i for i in IND_IDS if _score(_cell(a, i)) != _score(_cell(b, i))]


def _key(e):
    return ((e.get("url") or "").strip().lower(), re.sub(r"\W+", " ", (e.get("excerpt") or "").lower()).strip())


class Merger:
    """Maps Run B's evidence codes for one subject onto Run A's list: an item A already holds keeps A's code, any other gets the next free code."""

    def __init__(self, a, b):
        self.a, self.b = a, b
        self.by_key = {_key(e): e["code"] for e in a.data["evidence"]}
        self.b_items = {e["code"]: e for e in b.data["evidence"]}
        self.map: dict[str, str] = {}
        self.added: list[dict] = []

    def code_for(self, bcode):
        if bcode in self.map: return self.map[bcode]
        item = self.b_items.get(bcode)
        if item is None: return None
        k = _key(item)
        if k != ("", "") and k in self.by_key:
            final = self.by_key[k]
        else:
            nums = [int(e["code"][len(self.a.prefix):]) for e in self.a.data["evidence"] + self.added
                    if e["code"].startswith(self.a.prefix) and e["code"][len(self.a.prefix):].isdigit()]
            final = f"{self.a.prefix}{max(nums + [0]) + 1:02d}"
            self.added.append(dict(item, code=final)); self.by_key[k] = final
        self.map[bcode] = final
        return final

    def text(self, s):
        return CITE.sub(lambda m: f"[{self.code_for(m.group(1)) or m.group(1)}]", s or "")

    def adopt(self, cell_b):
        """Run B's cell with its evidence codes rewritten onto Run A's list."""
        c = dict(cell_b)
        seen, ev = set(), []
        for x in cell_b.get("evidence") or []:
            y = self.code_for(x) or x
            if y not in seen: seen.add(y); ev.append(y)
        c["evidence"] = ev; c["rationale"] = self.text(cell_b.get("rationale")); c["summary"] = self.text(cell_b.get("summary"))
        return c


def _items(codes, evidence, mapper=None):
    out = []
    by = {e["code"]: e for e in evidence}
    for x in codes or []:
        e = by.get(x)
        if e: out.append(f'  [{mapper(x) if mapper else x}] {e.get("document", "")} ({e.get("date", "")}), {e.get("evidence_class", "")}: "{e.get("excerpt", "")}"')
    return "\n".join(out) or "  (none listed)"


def _case(a, b, ind, merger):
    d, ca, cb = IND[ind], _cell(a, ind), _cell(b, ind)
    anchors = "; ".join(f"{k} = {v}" for k, v in d["anchors"].items())
    for x in cb.get("evidence") or []: merger.code_for(x)  # assign the final codes up front, so the reasons can cite them
    return (f"### {ind} {d['name']}\nDefinition: {d['definition']}\nAnchors: {anchors}\n"
            f"Run A: score {_shown(_score(ca)) or 'not assessable'}, confidence {ca.get('confidence')}. {ca.get('rationale', '')}\n"
            f"Run A evidence:\n{_items(ca.get('evidence'), a.data['evidence'])}\n"
            f"Run B: score {_shown(_score(cb)) or 'not assessable'}, confidence {cb.get('confidence')}. {merger.text(cb.get('rationale'))}\n"
            f"Run B evidence:\n{_items(cb.get('evidence'), b.data['evidence'], merger.code_for)}")


def _adjudicate(a, b, ids, ctx):
    from . import nodes  # shares the model-call slots with the research
    merger = Merger(a, b)
    cases = "\n\n".join(_case(a, b, i, merger) for i in ids)
    known = {e["code"] for e in a.data["evidence"]} | {e["code"] for e in merger.added}
    chosen: dict[str, dict] = {}

    def accept(inp):
        items = inp.get("items") or []
        got = [x.get("indicator") for x in items]
        p = []
        if missing := [i for i in ids if i not in got]: p.append(f"missing indicators: {missing}")
        if extra := sorted({i for i in got if i not in ids}): p.append(f"not disputed, remove: {extra}")
        if dup := sorted({i for i in got if got.count(i) > 1}): p.append(f"submitted more than once: {dup}")
        for x in items:
            if not (x.get("reason") or "").strip(): p.append(f"{x.get('indicator')}: the reason is empty")
        p += _check_text([x.get("reason") or "" for x in items], known)
        if not p: chosen.update({x["indicator"]: x for x in items})
        return p

    prompt = render_prompt("reconcile.md", today=ctx["today"], period=ctx["period"], name=a.name,
                           role="the company being assessed" if a.role == "company" else "a peer", peerset=ctx["peerset"], cases=cases)
    conv = Conv(f"reconciliation of {a.short}", [RECON_TOOL], prompt, model=cfg.MODEL)
    conv.stop = ctx.get("stop")
    with nodes._SLOTS:
        conv.submit(RECON_TOOL["name"], accept)

    rows, keep, changed = [], set(), []
    for ind in ids:
        x = chosen[ind]; ca, cb = _cell(a, ind), _cell(b, ind)
        pick = x["choice"]
        final = _score(cb) if pick == "B" else _score(ca)
        if pick == "B":
            new = merger.adopt(cb)
            a.data["indicators"] = [new if c["id"] == ind else c for c in a.data["indicators"]]
            keep |= set(new["evidence"]) | set(CITE.findall(new["rationale"])) | set(CITE.findall(new.get("summary") or ""))
            changed.append(f"{ind} {_shown(_score(ca)) or 'n/a'} -> {_shown(final) or 'n/a'}")
        keep |= set(CITE.findall(x["reason"]))
        rows.append({"subject": a.short, "role": a.role, "indicator": ind, "name": IND[ind]["name"], "a": _shown(_score(ca)),
                     "b": _shown(_score(cb)), "final": _shown(final), "chosen": pick, "reason": x["reason"].strip()})
    a.data["evidence"] = a.data["evidence"] + [e for e in merger.added if e["code"] in keep]
    a.draft = a.data  # later revisions merge into the reconciled data
    if changed and a.role == "company":
        dims = sorted({IND[i.split()[0]]["dimension"] for i in changed})
        a.recon_note = ("Reconciliation with an independent second run changed these indicator scores: " + "; ".join(changed) +
                        f". Resubmit the assessment_text and limitations of dimension(s) {', '.join(dims)} so the narrative matches the final scores.")
    return rows


def reconcile(subjects_a, subjects_b, ctx) -> dict:
    """Reconciles every subject (company and peers) and returns the block stored as run['reconciliation']. Run A's subjects are updated in place."""
    total = len(IND_IDS) * len(subjects_a)
    jobs = [(a, b, ids) for a, b in zip(subjects_a, subjects_b) if (ids := disputes(a, b))]
    rows: list[dict] = []
    if jobs:
        with ThreadPoolExecutor(max_workers=len(jobs)) as pool:
            for r in pool.map(lambda j: _adjudicate(j[0], j[1], j[2], ctx), jobs): rows += r
    order = {s.short: n for n, s in enumerate(subjects_a)}
    rows.sort(key=lambda r: (order.get(r["subject"], 99), IND_IDS.index(r["indicator"])))
    log.info("reconciled", disputed=len(rows), total=total)
    return {"models": {"A": {"model": cfg.MODEL, "effort": cfg.EFFORT}, "B": {"model": cfg.MODEL_B, "effort": cfg.EFFORT}},
            "agreed": total - len(rows), "total": total, "rows": rows}

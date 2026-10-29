"""Graded run files -> the view object `D` the front end reads; base_view() is the same shape with no company (js/data/base.js).

Faithful port of server/convert.py: same signatures and output keys."""
from __future__ import annotations

import hashlib
import re
from typing import Any

from .skill import (DIM_OF, DIMS, FW, FW_KEYS, IND, IND_IDS, LV, METHOD, READ, company_of, defs as _defs, framework, peers_of)

__all__ = ["FW", "DIMS", "IND_IDS", "framework", "short_name", "slug", "company_id", "company_of", "peers_of", "subj_short", "first_sentence",
           "prefixes", "base_view", "to_view", "READ", "METHOD"]

_SUFFIX = re.compile(r"[\s,]+(corporation|corp\.?|incorporated|inc\.?|holdings?|company|co\.?|group|limited|ltd\.?|p\.?l\.?c\.?|s\.?a\.?|n\.?v\.?|ag|se|llc|lp)$", re.I)


def short_name(name: str) -> str:
    """'Exxon Mobil (ExxonMobil Holdings Corporation)' -> 'ExxonMobil'; 'BP p.l.c.' -> 'BP'; 'Chevron Corporation' -> 'Chevron'."""
    m = re.search(r"\(([^)]+)\)", name or "")
    s = (m.group(1) if m else name or "").strip()
    while True:
        t = _SUFFIX.sub("", s).strip()
        if t == s or not t: break
        s = t
    return s


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def slug(name: str, ticker: str = "") -> str:
    """Company id: the name in a-z0-9 and dashes, else the ticker, else co-<hash of the name>. At most 56 characters,
    so store.unique_id's '-n' suffix stays within valid_id's 64."""
    s = _slug(name) or _slug(ticker) or "co-" + hashlib.sha256((name or "").encode("utf-8")).hexdigest()[:10]
    return s[:56].strip("-")


def company_id(comp: dict) -> str:
    return slug(subj_short(comp), comp.get("ticker", ""))


def subj_short(s: dict) -> str:
    return s.get("short") or short_name(s.get("name", ""))


def first_sentence(t: str | None) -> str:
    t = (t or "").strip()
    return t.split(". ")[0].rstrip(".") + "." if t else ""


def _cell(s: dict, iid: str, lens: str = "board") -> dict:
    return ((s.get("indicators") or {}).get(iid) or {}).get(lens) or {}


def _dim(s: dict, d: str, lens: str = "board") -> dict:
    return ((s.get("computed") or {}).get("dimensions") or {}).get(d, {}).get(lens) or {}


def _overall(s: dict, lens: str = "board") -> dict:
    return ((s.get("computed") or {}).get("overall") or {}).get(lens) or {}


def _action(k: int, a: dict) -> dict:
    out = {"n": f"{k:02d}", "heading": a.get("heading", ""), "description": a.get("description", ""), "measures": a.get("measures", []) or [], "target": a.get("target_by", "")}
    if a.get("improves"): out["improves"] = a["improves"]  # which indicators the action should raise (new runs only)
    return out


def prefixes(run: dict) -> dict:
    """Evidence-code letter prefix -> subject short name, by which subject's board cells cite the codes."""
    votes: dict[str, dict[str, int]] = {}
    for s in run["subjects"]:
        for iid in IND_IDS:
            for e in _cell(s, iid).get("evidence") or []:
                p = re.match(r"[A-Za-z]+", e)
                if p: votes.setdefault(p.group(0), {}).setdefault(subj_short(s), 0); votes[p.group(0)][subj_short(s)] += 1
    return {p: max(v, key=v.get) for p, v in votes.items() if p not in ("IO", "SA")}


def _used(run: dict) -> dict[str, list[str]]:
    used: dict[str, set] = {}
    for s in run["subjects"]:
        for iid, ind in (s.get("indicators") or {}).items():
            for l in ("board", "board_io"):
                for e in ((ind.get(l) or {}).get("evidence") or []):
                    used.setdefault(e, set()).add(iid + ("" if s.get("role") == "company" else f" ({s['name']})"))
    return {k: sorted(v) for k, v in used.items()}


def _ev(e: dict, used: list[str] | None = None) -> dict:
    out = {"doc": e.get("document", ""), "date": e.get("date", ""), "cls": e.get("evidence_class", "direct"), "origin": e.get("source_origin", "public"),
           "recent": bool(e.get("recent")), "excerpt": e.get("excerpt", ""), "url": e.get("url", "")}
    if e.get("search_log"): out["search"] = e["search_log"]
    if e.get("question"): out["question"] = e["question"]
    if used is not None: out["used"] = ", ".join(used) or "context"
    return out


def _io_ev(code: str, e: dict) -> dict:
    out = {"doc": e.get("document", ""), "date": e.get("date", ""), "cls": e.get("evidence_class"), "origin": e.get("source_origin", e.get("evidence_class"))}
    q = e.get("question")
    m = re.fullmatch(r"SA(\d+)", code)
    if not q and m and 0 < int(m.group(1)) <= len(FW["questionnaire"]): q = FW["questionnaire"][int(m.group(1)) - 1][2]
    if q: out["question"] = q
    out["excerpt"] = e.get("excerpt", "")
    return out


def _sa_answers(io_run: dict) -> list[str]:
    n = len(FW["questionnaire"])
    ans = io_run.get("self_assessment_answers")
    if isinstance(ans, dict): return [str(ans.get(str(k), "") or "") for k in range(1, n + 1)]
    if isinstance(ans, list): return [str(a or "") for a in ans][:n] + [""] * max(0, n - len(ans))
    ev =io_run.get("evidence", {})
    return [(ev.get(f"SA{k:02d}") or {}).get("excerpt", "") for k in range(1, n + 1)]


def _io(io_run: dict) -> dict:
    comp = company_of(io_run)
    cells = {}
    for iid in IND_IDS:
        c = _cell(comp, iid, "board_io")
        if not c or c.get("carried_forward") or c.get("score") is None: continue
        cells[iid] = {"score": c["score"], "conf": c.get("confidence"), "rationale": c.get("rationale", ""), "ev": c.get("evidence", []) or []}
    ev = {k: _io_ev(k, v) for k, v in sorted(io_run.get("evidence", {}).items()) if v.get("evidence_class") in ("inside_out", "self_assessment")}
    ivo = io_run.get("inside_vs_outside") or {}
    return {
        "cells": cells, "ev": ev, "headline": io_run.get("headline", ""), "drives": io_run.get("what_moved", ""),
        "better": ivo.get("better", []), "worse": ivo.get("worse", []),
        "actions": [_action(k, a) for k, a in enumerate(io_run.get("actions", [])[:5], 1)],
        "prior_actions": [{"id": p.get("id"), "heading": p.get("heading", ""), "status": p.get("status"), "note": p.get("evidence_note", ""), "metrics": p.get("metrics_note", "")}
                          for p in io_run.get("prior_actions_status", [])],
        "back": [{"id": b.get("id"), "heading": b.get("heading", ""), "what": b.get("what_happened", ""), "impact": b.get("impact", ""), "cause": b.get("root_cause", ""),
                  "prevent": b.get("prevention", ""), "measures": b.get("measures", [])} for b in io_run.get("back_on_track", [])],
        "sa": _sa_answers(io_run), "ratings": {str(k): v for k, v in (io_run.get("self_ratings") or {}).items()},
        "overall": _overall(comp, "board_io"),
    }


def _prior(oi_run: dict, prior_run: dict | None) -> dict | None:
    if prior_run:
        stage = prior_run.get("run", {}).get("stage", "outside_in")
        comp = company_of(prior_run); lens = "board_io" if stage == "inside_out" else "board"
        return {"period": prior_run["run"]["period"], "stage": stage, "scores": {i: (_cell(comp, i, lens) or _cell(comp, i)).get("score") for i in IND_IDS},
                "actions": prior_run.get("actions", [])}
    hist = oi_run.get("history") or []
    if not hist: return None
    return _hist(hist[-1])


def _hist(h: dict) -> dict:
    io = "board_io" in h.get("lenses", []); lens = "board_io" if io else "board"
    return {"period": h["period"], "stage": "inside_out" if io else "outside_in", "scores": {i: (h.get("indicators", {}).get(i) or {}).get(lens) for i in IND_IDS},
            "actions": h.get("actions", [])}


def _priors(oi_run: dict, prior_runs: list[dict]) -> list[dict]:
    """Every earlier assessment on file, oldest first: prior run files, else the run's own history."""
    out = [_prior(oi_run, p) for p in prior_runs] if prior_runs else [_hist(h) for h in oi_run.get("history") or []]
    cur = oi_run.get("run", {}).get("period")
    return sorted((p for p in out if p and p["period"] != cur), key=lambda p: p["period"])


def base_view() -> dict:
    """The framework with no company loaded: what the app shows before any company is added."""
    return {
        "meta": {"id": "", "company": "", "short": "", "ticker": "", "period": "", "date": "", "peers": [], "peer_short": [], "mode": "director_request", "prefixes": {}, "source": ""},
        "headline": "", "overall_line": "", "drives": "", "actions": [], "metrics": [], "position": "", "position_lines": [], "scorecard": [], "coverage_note": "",
        "ind_summary": [], "peer_table": [], "addl": [], "dimtext": {},
        "ind": {i["id"]: {"name": i["name"], "score": None, "rationale": "", "conf": None, "ev": []} for i in IND},
        "peers": [], "read": READ, "method": METHOD, "ev": {}, "defs": _defs(), "io": None, "prior": None, "priors": [],
        "docs": [list(x) for x in FW["inside_out_priority_docs"]], "q": [list(x) for x in FW["questionnaire"]],
        "modes": FW["run_modes"], "scale": FW["grade_scale"], "findings_oi": [], "findings_io": [], "overall": {}, "files": {},
    }


def to_view(oi_run: dict, io_run: dict | None = None, prior_run: dict | None = None, meta: dict | None = None, prior_runs: list[dict] | None = None) -> dict:
    meta = meta or {}
    comp = company_of(oi_run); peers = peers_of(oi_run); r = oi_run.get("run", {})
    used = _used(oi_run)
    cov = (comp.get("computed") or {}).get("coverage", {}).get("board", {})
    na = [f"{i} ({_cell(comp, i).get('na_cause', '')})" for i in IND_IDS if _cell(comp, i).get("score") is None]
    sch = oi_run.get("scorecard_headline") or {}; summ = oi_run.get("indicator_summary") or {}; rs = oi_run.get("peer_row_summary") or {}
    prov = _overall(comp).get("provisional")

    D: dict[str, Any] = {
        "meta": {"id": meta.get("id") or company_id(comp), "company": comp["name"], "short": subj_short(comp), "ticker": comp.get("ticker", ""),
                 "period": r.get("period", ""), "date": r.get("run_date", ""), "peers": [p["name"] for p in peers], "peer_short": [subj_short(p) for p in peers],
                 "mode": meta.get("mode") or r.get("mode", ""), "prefixes": prefixes(oi_run), "source": meta.get("source", "imported")},
        "headline": oi_run.get("headline", ""),
        "overall_line": (oi_run.get("overall_summary") or {}).get("board", ""),
        "drives": oi_run.get("what_moved") or " ".join(oi_run.get("headline_findings", [])),
        "actions": [_action(k, a) for k, a in enumerate(oi_run.get("actions", [])[:5], 1)],
        "metrics": [[m.get("metric", ""), m.get("why", ""), m.get("current", "") or ""] for m in oi_run.get("key_metrics", [])[:6]],
        "position": oi_run.get("peer_position", ""),
        "position_lines": ["• " + x for x in oi_run.get("peer_summary_lines", [])[:5]],
        "scorecard": [{"dim": f"{d}. {FW['dimensions'][d]}", "grade": _dim(comp, d).get("grade"), "line": sch.get(d, "")} for d in DIMS]
                     + [{"dim": "Overall", "grade": _overall(comp).get("grade"), "line": "Rounded average of dimension letters (midpoints round down)." + (" * provisional" if prov else "")}],
        "coverage_note": "Grades rest on outside-in information; where an indicator is not assessable or scored on thin public evidence, board documents can arrive at a more accurate grade.",
        "ind_summary": [{"name": f"{i['id']} {i['name']}", "score": _cell(comp, i["id"]).get("score"),
                         "line": summ.get(i["id"]) or first_sentence(_cell(comp, i["id"]).get("rationale")) or "Not assessable."} for i in IND],
        "peer_table": [["Dimension", comp["name"]] + [p["name"] for p in peers] + ["How the company compares"]]
                      + [[f"{d}. {FW['dimensions'][d]}", _dim(comp, d).get("grade")] + [_dim(p, d).get("grade") for p in peers] + [rs.get(d, "")] for d in DIMS]
                      + [["Overall", _overall(comp).get("grade")] + [_overall(p).get("grade") for p in peers] + [oi_run.get("peer_position", "")]],
        "addl": ["• " + x for x in oi_run.get("additional_information_needed", [])],
        "dimtext": {d: {"title": f"{d}. {FW['dimensions'][d]}  ·  Outside-in {_dim(comp, d).get('grade') or 'n/a'}", "text": (comp.get("assessment_text") or {}).get(d, ""),
                        "limit": ("Where this grade is limited: " + comp["limitations"][d]) if (comp.get("limitations") or {}).get(d) else ""} for d in DIMS},
        "ind": {},
        "peers": [],
        "read": READ, "method": METHOD,
        "ev": {k: _ev(v, used.get(k, [])) for k, v in sorted(oi_run.get("evidence", {}).items())},
        "defs": _defs(),
        "io": None, "prior": None,
        "docs": [list(x) for x in FW["inside_out_priority_docs"]],
        "q": [list(x) for x in FW["questionnaire"]],
        "modes": FW["run_modes"], "scale": FW["grade_scale"],
        "findings_oi": oi_run.get("headline_findings", []),
        "findings_io": (io_run or {}).get("headline_findings", []),
        "overall": {"oi": _overall(comp)},
        "files": meta.get("files", {}),
    }
    for i in IND:
        c = _cell(comp, i["id"])
        D["ind"][i["id"]] = {"name": i["name"], "score": c.get("score"), "rationale": c.get("rationale", ""), "conf": c.get("confidence"), "ev": c.get("evidence", []) or []}
        if c.get("score") is None: D["ind"][i["id"]]["na"] = c.get("na_cause")
    for p in peers:
        ind = {}
        for iid in IND_IDS:
            c = _cell(p, iid); ind[iid] = {"score": c.get("score"), "rationale": c.get("rationale", ""), "ev": c.get("evidence", []) or []}
            if c.get("score") is None: ind[iid]["na"] = c.get("na_cause")
        D["peers"].append({"grades": [_dim(p, d).get("grade") for d in DIMS] + [_overall(p).get("grade")], "ind": ind, "summary": p.get("summary", "")})
    if io_run:
        D["io"] = _io(io_run)
        D["overall"]["io"] = D["io"].pop("overall")
    D["prior"] = _prior(oi_run, prior_run)
    D["priors"] = _priors(oi_run, prior_runs if prior_runs is not None else ([prior_run] if prior_run else []))
    if oi_run.get("reconciliation"): D["reconciliation"] = oi_run["reconciliation"]  # Run A / Run B reconciliation, shown in the reports
    return D

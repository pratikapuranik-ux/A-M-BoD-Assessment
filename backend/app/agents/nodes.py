"""Graph nodes for the outside-in and inside-out research graphs, plus the per-subject / per-session objects they drive."""
from __future__ import annotations

import copy
import datetime as dt
import json
import re
import threading

import structlog

from . import settings as cfg
from .checks import (_assemble_io, _assemble_oi, _calibration, _cell, _check_cells, _check_evidence, _check_text, _digest,
                     _drop, _evidence_item, _io_check, _io_inputs, _merge, _problem_text, _provided, _route, _synth_check)
from .client import ResearchError, ResearchInvalid
from .conversation import Conv
from .grading import grade_run
from .progress import Band, MonotonicProgress, narrate, phases, short_name
from .settings import DIMS, FW, IND_IDS, PEER_PREFIXES, PERIOD_RE
from .state import InsideOutState, OutsideInState, SubjectTask
from .tools import (IO_KEYS, IO_TOOL, SUBJECT_KEYS, SUBJECT_TOOL, SYNTH_KEYS, SYNTH_TOOL, WEB_TOOLS, render_prompt)

log = structlog.get_logger("agents.nodes")


def today() -> dt.date:
    return dt.date.today()


# ---------------------------------------------------------------- outside-in: one subject

class Subject:
    def __init__(self, name, ticker, role, prefix, model=None):
        self.name, self.ticker, self.role, self.prefix, self.short = name, ticker or "", role, prefix, short_name(name)
        self.data, self.draft, self.conv = None, None, None
        self.model = model        # None = BOARD_MODEL (Run A); Run B passes its own
        self.recon_note = ""      # set by the reconciliation: asks the next revision to bring the narrative in line with the final scores
        self.counts = {"web_search": 0, "web_fetch": 0}

    def accept(self, inp):
        # merge into the latest submission even if it was rejected: Claude is told empty fields keep what it sent before,
        # so a correction that resends only the fixed indicators must still see the evidence list from the first try
        merged = self.draft = _merge(self.draft, inp, SUBJECT_KEYS)
        known = {e.get("code") for e in merged.get("evidence", [])}
        p = _check_evidence(merged.get("evidence", []), self.prefix) + _check_cells(merged.get("indicators", []), known, items={e.get("code"): e for e in merged.get("evidence", [])})
        dims = [d.get("dimension") for d in merged.get("dimensions", [])]
        if missing := [d for d in DIMS if d not in dims]: p.append(f"dimensions missing assessment_text and limitations: {missing}")
        for d in merged.get("dimensions", []):
            if not (d.get("assessment_text") or "").strip(): p.append(f"dimension {d.get('dimension')}: assessment_text is empty")
        p += _check_text([(d.get("assessment_text") or "") + (d.get("limitations") or "") for d in merged.get("dimensions", [])]
                         + [c.get("summary") or "" for c in merged.get("indicators", [])], known)
        if not p: self.data = merged
        else: _drop(self.draft, "evidence", "code", {e.get("code") for e in merged.get("evidence", []) if not re.fullmatch(self.prefix + r"\d{2,3}", e.get("code") or "")})
        return p

    def research(self, ctx, band, i):
        def on_block(b):
            if getattr(b, "type", "") == "server_tool_use":
                if b.name in self.counts: self.counts[b.name] += 1
                band.tick(i, narrate(self.short, b.name, getattr(b, "input", None)))
        on_phase = phases(lambda m: band.tick(i, m), {"thinking": f"Weighing the evidence on {self.short}",
                                                      SUBJECT_TOOL["name"]: f"Writing up {self.short}'s scores on the 22 indicators"})
        content = render_prompt("subject.md", today=ctx["today"], period=ctx["period"], name=self.name, ticker=self.ticker or "n/a",
                                role="the company being assessed" if self.role == "company" else "peer", peerset=ctx["peerset"],
                                prefix=self.prefix, behaviour_from=ctx["meta"]["document_window"]["behaviour_from"],
                                trend_from=ctx["meta"]["document_window"]["trend_from"], search_budget=cfg.SEARCH_BUDGET, fetch_budget=cfg.FETCH_BUDGET)
        if self.role == "company" and ctx.get("provided"): content = [{"type": "text", "text": content}] + ctx["provided"]
        self.conv = Conv(f"research on {self.short}", WEB_TOOLS + [SUBJECT_TOOL], content, on_block, on_phase, model=self.model)
        self.conv.stop = ctx.get("stop")
        band.tick(i, f"Starting research on {self.short}")
        self.conv.submit(SUBJECT_TOOL["name"], self.accept)
        self.review(band, i)
        band.tick(i, f"Scored {self.short}'s board on all 22 indicators", done=True)

    def review(self, band, i):
        """Retrieval review. While this subject has read fewer pages than the floor (or still lists Rule 15 documents as
        unavailable in the first round), it is sent back to read more before its scores are accepted."""
        floor = min(cfg.MIN_FETCHES if self.role == "company" else cfg.MIN_FETCHES_PEER, max(1, cfg.FETCH_USES - 2))
        for rnd in range(cfg.REVIEW_ROUNDS):
            reads, searches = self.counts["web_fetch"], self.counts["web_search"]
            missing = list((self.data or {}).get("documents_unavailable") or [])
            if reads >= floor and not (rnd == 0 and missing): return
            band.tick(i, f"Reviewing {self.short}'s retrieval: reading more primary documents")
            lines = "\n".join(f"- {d}" for d in missing[:12]) or "- (none listed)"
            self.revise(
                f"Retrieval review for {self.name}: so far {searches} searches and {reads} page reads (the expected minimum is about {floor} reads "
                f"of primary documents). Before these scores are accepted:\n"
                f"1. Retry each document you listed as unavailable by another route: the investor-relations HTML page, the SEC EDGAR filing index, "
                f"the regulator or exchange page, or a reputable mirror of the same filing:\n{lines}\n"
                f"2. Read in full the latest proxy statement (pay discussion, governance guidelines, director and committee sections, board evaluation) "
                f"and the annual report cash-flow statements, if you have not.\n"
                f"3. Search for adverse and Day 2 evidence you may have missed: waivers of age or term limits, director or executive departures and "
                f"their stated reasons, litigation and regulator actions, impairments, reversed decisions, protective governance provisions.\n"
                f"Then call submit_subject_assessment again with only the indicators, evidence items, dimensions and comparables that the new reading "
                f"changes. Keep a document in documents_unavailable only if every route failed. If nothing changes, call it with all lists empty.")

    def revise(self, text):
        self.conv.say(text)
        self.conv.submit(SUBJECT_TOOL["name"], self.accept)

    def to_run(self, today):
        inds = {c["id"]: {"board": _cell(c)} for c in self.data["indicators"]}
        out = {"name": self.name, "ticker": self.ticker, "role": self.role, "indicators": {i: inds[i] for i in IND_IDS}}
        if self.role == "company":
            dims = {d["dimension"]: d for d in self.data["dimensions"]}
            out["assessment_text"] = {d: dims[d]["assessment_text"] for d in DIMS}
            out["limitations"] = {d: dims[d]["limitations"] for d in DIMS}
        return out

    def evidence(self, today):
        return {e["code"]: _evidence_item(e, today) for e in sorted(self.data["evidence"], key=lambda e: e["code"])}


def fix_jobs(subjects, by, extra=None):
    """The revision message for each subject that has blocking problems (or shared calibration text) to deal with."""
    jobs = []
    for s in subjects:
        text = ""
        if by.get(s.name): text += f"grade.py reported these blocking problems for {s.name}:\n{_problem_text(by[s.name])}\n"
        if extra: text += extra + "\n"
        if getattr(s, "recon_note", ""): text += s.recon_note + "\n"; s.recon_note = ""
        if text:
            jobs.append((s, text + "Call submit_subject_assessment again with only the indicators, evidence items, dimensions "
                                   "and comparables that change (empty lists keep what you submitted). If nothing needs to change, "
                                   "call it with all lists empty."))
    return jobs


class SynthSession:
    """The synthesis conversation and its merged draft."""

    def __init__(self, subjects, period, mode, prog, ctx, graded):
        self.subjects, self.period, self.known, self.syn, self.draft = subjects, period, set(graded["evidence"]), {}, None
        prior = "There is no prior quarter for this company; what_moved explains what drove the grade across dimensions."
        self.conv = Conv("the synthesis", [SYNTH_TOOL], render_prompt("synthesis.md", today=ctx["today"], period=period, mode=mode,
                         company=subjects[0].name, prior_note=prior, digest=_digest(graded, subjects)),
                         lambda b: prog(prog.pct + 1 if prog.pct < 93 else prog.pct, "Writing the headline, findings and actions"),
                         phases(lambda m: prog(prog.pct, m), {"thinking": "Weighing the findings across the peer set",
                                                              SYNTH_TOOL["name"]: "Writing the headline, findings and actions"}))

    def accept(self, inp):
        merged = self.draft = _merge(self.draft, inp, SYNTH_KEYS)
        p = _synth_check(merged, self.subjects[1:], self.known, self.period)
        if not p: self.syn = merged
        return p

    def submit(self): self.conv.submit(SYNTH_TOOL["name"], self.accept)


# ---------------------------------------------------------------- outside-in: nodes

def plan(state: OutsideInState):
    company, ticker, peers, period, mode = state["company"], state.get("ticker", ""), state["peers"], state["period"], state["mode"]
    if not (company or "").strip(): raise ValueError("company is required")
    if not 2 <= len(peers) <= FW["max_peers"]: raise ValueError(f"choose two to {FW['max_peers']} peers")
    if not PERIOD_RE.match(period or ""): raise ValueError("period must be YYYY-Qn")
    if mode not in FW["run_modes"]: raise ValueError(f"mode must be one of {list(FW['run_modes'])}")
    prog = MonotonicProgress(state.get("progress"))
    t = today()
    meta = {"run_date": t.isoformat(), "period": period, "stage": "outside_in", "mode": mode, "rule_version": FW["rule_version"],
            "document_window": {"behaviour_from": f"{t.year - 2}-{t.month:02d}", "trend_from": f"FY{t.year - 5}"},
            "consistency_run": 1, "simulated": False}
    model = state.get("model")
    subjects = [Subject(company.strip(), ticker, "company", "E", model)] + [
        Subject(p["name"].strip(), p.get("ticker", ""), "peer", PEER_PREFIXES[n], model) for n, p in enumerate(peers)]
    documents = state.get("documents")
    ctx = state.get("shared") if state.get("shared") is not None else {}
    ctx.update(today=t.isoformat(), today_date=t, period=period, meta=meta, prog=prog,
               peerset="; ".join(f"{s.name} ({s.ticker or 'n/a'})" for s in subjects),
               provided=_provided(subjects[0].name, documents) if documents else None)
    ctx.setdefault("stop", threading.Event())
    prog(2, f"Planning research on {subjects[0].short} and {len(peers)} peers")
    # the company and every peer are researched at the same time: no subject's research depends on another's
    ctx["band"] = Band(prog, 3, 72, len(subjects))
    return {"ctx": ctx, "subjects": subjects, "rnd": 0, "jobs": [], "rest": [], "calibrated": False, "done": False}


def _guarded(ctx, fn):
    """Runs one parallel branch; the first failure stops the other branches and is the one reported."""
    try:
        fn()
    except BaseException as e:
        if not ctx["stop"].is_set(): ctx["stop"].set(); ctx["failed"] = e
        raise


_SLOTS = threading.BoundedSemaphore(cfg.SUBJECT_WORKERS)  # all subjects of all consistency runs share these model-call slots


def research_subject(task: SubjectTask):
    with _SLOTS:
        _guarded(task["ctx"], lambda: task["subject"].research(task["ctx"], task["ctx"]["band"], task["idx"]))
    return {}


def fix_subject(task: SubjectTask):
    with _SLOTS:
        _guarded(task["ctx"], lambda: task["subject"].revise(task["text"]))
    return {}


def calibrate_and_grade(state: OutsideInState):
    """Grades the subjects' scores, then sends calibration (round 0) or blocking problems back to the subjects that caused them."""
    ctx, subjects, rnd, prog = state["ctx"], state["subjects"], state["rnd"], state["ctx"]["prog"]
    if ctx.get("failed"): raise ctx["failed"]
    if rnd == 0: prog(73, "Comparing the company with its peers on the peer-relative indicators")
    problems, graded = grade_run(_assemble_oi(ctx, subjects, {}))
    if rnd > 0 and not problems: return {"graded": graded, "jobs": [], "calibrated": True}
    if rnd == cfg.MAX_FIX_ROUNDS:
        raise ResearchInvalid(f"The scores still break {len(problems)} rule(s) after {cfg.MAX_FIX_ROUNDS} fix rounds: "
                              + "; ".join(f"{n} {w}: {m}" for n, w, m in problems[:5]), problems)
    if problems: prog(74 + 3 * rnd, f"Fixing {len(problems)} rule issue(s) flagged by the grade check")
    by, _ = _route(problems, subjects)
    return {"graded": graded, "jobs": fix_jobs(subjects, by, _calibration(subjects) if rnd == 0 else None), "rnd": rnd + 1}


def synthesis(state: OutsideInState):
    ctx, prog = state["ctx"], state["ctx"]["prog"]
    prog(85, "Writing the headline, findings and actions")
    sess = SynthSession(state["subjects"], ctx["period"], ctx["meta"]["mode"], prog, ctx, state["graded"])
    sess.submit()
    prog(95, "Checking the finished assessment against the scoring rules")
    return {"synth": sess, "rnd": 0, "jobs": [], "rest": [], "done": False}


def final_check(state: OutsideInState):
    ctx, subjects, sess, rnd = state["ctx"], state["subjects"], state["synth"], state["rnd"]
    problems, graded = grade_run(_assemble_oi(ctx, subjects, sess.syn))
    sess.known = set(graded["evidence"])
    if not problems: return {"graded": graded, "done": True, "jobs": [], "rest": []}
    if rnd == cfg.MAX_FIX_ROUNDS:
        raise ResearchInvalid(f"The assessment still breaks {len(problems)} rule(s) after {cfg.MAX_FIX_ROUNDS} fix rounds.", problems)
    by, rest = _route(problems, subjects)
    return {"graded": graded, "jobs": fix_jobs(subjects, by), "rest": rest, "rnd": rnd + 1}


def revise_synthesis(state: OutsideInState):
    sess, rest = state["synth"], state.get("rest") or []
    if rest:
        sess.conv.say(f"grade.py reported these blocking problems:\n{_problem_text(rest)}\nCall submit_synthesis again with the fields that change.")
        sess.submit()
    return {"rest": []}


def finalize(state: OutsideInState):
    ctx = state["ctx"]
    ctx["prog"](100, f"Outside-in assessment of {state['subjects'][0].short} complete")
    return {"result": state["graded"]}


# ---------------------------------------------------------------- inside-out

class InsideOutSession:
    def __init__(self, **kw): self.__dict__.update(kw)

    def accept(self, inp):
        merged = self.draft = _merge(self.draft, inp, IO_KEYS)
        p = _io_check(merged, self.oi_cells, self.known, self.io_items, self.sa, self.prior, self.period)
        if not p: self.io = merged
        else:
            pids = {a.get("id") for a in self.prior}
            _drop(self.draft, "documents", "code", {d.get("code") for d in self.draft.get("documents", []) if d.get("code") not in self.io_items})
            for f in ("prior_actions_status", "back_on_track"): _drop(self.draft, f, "id", {x.get("id") for x in self.draft.get(f, []) if x.get("id") not in pids})
        return p

    def submit(self): self.conv.submit(IO_TOOL["name"], self.accept)


def io_prepare(state: InsideOutState):
    oi_run, documents, answers, ratings = state["oi_run"], state["documents"], state["answers"], state["ratings"]
    prog = MonotonicProgress(state.get("progress"))
    if (oi_run.get("run") or {}).get("stage") != "outside_in": raise ValueError("run_inside_out needs an outside-in run")
    t = today(); period = oi_run["run"]["period"]
    base = copy.deepcopy(oi_run)
    for s in base["subjects"]:
        s.pop("computed", None)
        for ind in s["indicators"].values(): ind.pop("board_io", None)
    base["run"].update(stage="inside_out", run_date=t.isoformat(), simulated=False)
    io_items, blocks, sa = _io_inputs(base, documents, answers, t)
    if not io_items and not sa: raise ValueError("upload at least one board document or answer at least one question")
    ratings = {str(k): int(v) for k, v in (ratings or {}).items() if str(k) in DIMS and int(v) in (1, 3, 5)}
    comp = next(s for s in base["subjects"] if s["role"] == "company"); short = short_name(comp["name"])
    hist = sorted(base.get("history", []), key=lambda h: h.get("period", ""))
    prior = hist[-1].get("actions", []) if hist else []
    prog(3, f"Reading {len(io_items)} board document(s) and {len(sa)} questionnaire answer(s)")

    _, oi_graded = grade_run(oi_run)
    oc = next(s for s in oi_graded["subjects"] if s["role"] == "company")["computed"]
    oi_cells = {i: comp["indicators"][i]["board"] for i in IND_IDS}
    known = {k for k in base["evidence"] if k.startswith("E")} | set(io_items) | set(sa)
    digest = json.dumps({
        "outside_in": {"overall": oc["overall"]["board"], "dimensions": {d: oc["dimensions"][d]["board"] for d in DIMS},
                       "headline": oi_run.get("headline"), "what_moved": oi_run.get("what_moved"),
                       "headline_findings": oi_run.get("headline_findings"), "cells": oi_cells},
        "outside_in_evidence": {k: f"{v['document']} ({v.get('date', '')}): {v.get('excerpt', '')}" for k, v in base["evidence"].items() if k.startswith("E")},
        "board_documents": {k: v["document"] + f" [file {v['file_name']}]" for k, v in io_items.items()},
        "self_assessment": {k: {"question": v["question"], "answer": v["excerpt"]} for k, v in sa.items()},
        "self_ratings": ratings, "current_actions": oi_run.get("actions", []), "prior_actions": prior,
    }, indent=1, ensure_ascii=False)
    text = render_prompt("inside_out.md", today=t.isoformat(), period=period, company=comp["name"], digest=digest)
    steps = iter(["Reading the board documents", "Comparing the board documents with the public record",
                  "Re-scoring the board on the inside view", "Reviewing prior actions"])
    msg = ["Reading the board documents"]

    def on_block(b):
        if getattr(b, "type", "") in ("text", "tool_use", "thinking"): msg[0] = next(steps, msg[0])
        prog(min(prog.pct + 4, 70), msg[0])

    conv = Conv(f"inside-out review of {short}", [IO_TOOL], blocks + [{"type": "text", "text": text}], on_block,
                phases(lambda m: prog(prog.pct, m), {"thinking": "Weighing the board documents against the public record",
                                                     IO_TOOL["name"]: "Writing up the inside-out scores"}))
    sess = InsideOutSession(base=base, io_items=io_items, sa=sa, prior=prior, ratings=ratings, period=period, short=short,
                            oi_cells=oi_cells, known=known, conv=conv, io={}, draft=None, prog=prog)
    return {"session": sess, "rnd": 0, "done": False}


def io_score(state: InsideOutState):
    sess = state["session"]
    sess.prog(8, "Reading the board documents")
    sess.submit()
    sess.prog(75, "Checking the inside-out scores against the scoring rules")
    return {}


def io_check(state: InsideOutState):
    sess, rnd = state["session"], state["rnd"]
    problems, graded = grade_run(_assemble_io(sess.base, sess.io, sess.io_items, sess.sa, sess.prior, sess.ratings, sess.period))
    if not problems: return {"graded": graded, "problems": [], "done": True}
    if rnd == cfg.MAX_FIX_ROUNDS:
        raise ResearchInvalid(f"The inside-out scores still break {len(problems)} rule(s) after {cfg.MAX_FIX_ROUNDS} fix rounds: "
                              + "; ".join(f"{w}: {m}" for _, w, m in problems[:5]), problems)
    sess.prog(78 + 5 * rnd, f"Fixing {len(problems)} rule issue(s) flagged by the grade check")
    return {"graded": graded, "problems": problems, "rnd": rnd + 1}


def io_revise(state: InsideOutState):
    sess = state["session"]
    sess.conv.say(f"grade.py reported these blocking problems:\n{_problem_text(state['problems'])}\n"
                  "Call submit_inside_out again with the cells and fields that change.")
    sess.submit()
    return {}


def io_finalize(state: InsideOutState):
    sess = state["session"]
    sess.prog(100, f"Inside-out update for {sess.short} complete")
    return {"result": state["graded"]}

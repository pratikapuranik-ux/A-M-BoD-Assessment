"""LangGraph definitions and the public research API.

Outside-in:   plan -> [research_subject x (company + peers), bounded by SUBJECT_WORKERS] -> calibrate_and_grade
              -(blocking problems / calibration)-> [fix_subject x n] -> calibrate_and_grade ... (bounded by MAX_FIX_ROUNDS)
              -> synthesis -> final_check -(problems)-> [refix_subject x n] -> revise_synthesis -> final_check ... -> finalize
Inside-out:   io_prepare -> io_score -> io_check -(problems)-> io_revise -> io_check ... -> io_finalize
"""
from __future__ import annotations

import threading

import structlog
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from . import nodes, settings as cfg
from .client import PROVIDER, ResearchError, ResearchInvalid, ResearchRefused, research_enabled  # noqa: F401  (public API)
from .progress import Progress
from .state import InsideOutState, OutsideInState

log = structlog.get_logger("agents.graph")


def _fan_out_research(state: OutsideInState):
    ctx = state["ctx"]
    return [Send("research_subject", {"ctx": ctx, "idx": i, "subject": s, "text": ""}) for i, s in enumerate(state["subjects"])]


def _fan_out(node):
    def route(state: OutsideInState):
        return [Send(node, {"ctx": state["ctx"], "idx": i, "subject": s, "text": text})
                for i, (s, text) in enumerate(state["jobs"])]
    return route


def _after_calibrate(state: OutsideInState):
    if state.get("calibrated"): return "synthesis"
    return _fan_out("fix_subject")(state) if state.get("jobs") else "calibrate_and_grade"


def _after_final_check(state: OutsideInState):
    if state.get("done"): return "finalize"
    return _fan_out("refix_subject")(state) if state.get("jobs") else "revise_synthesis"


def build_outside_in():
    g = StateGraph(OutsideInState)
    g.add_node("plan", nodes.plan)
    g.add_node("research_subject", nodes.research_subject)
    g.add_node("calibrate_and_grade", nodes.calibrate_and_grade)
    g.add_node("fix_subject", nodes.fix_subject)
    g.add_node("synthesis", nodes.synthesis)
    g.add_node("final_check", nodes.final_check)
    g.add_node("refix_subject", nodes.fix_subject)
    g.add_node("revise_synthesis", nodes.revise_synthesis)
    g.add_node("finalize", nodes.finalize)
    g.add_edge(START, "plan")
    g.add_conditional_edges("plan", _fan_out_research, ["research_subject"])
    g.add_edge("research_subject", "calibrate_and_grade")
    g.add_conditional_edges("calibrate_and_grade", _after_calibrate, ["fix_subject", "calibrate_and_grade", "synthesis"])
    g.add_edge("fix_subject", "calibrate_and_grade")
    g.add_edge("synthesis", "final_check")
    g.add_conditional_edges("final_check", _after_final_check, ["refix_subject", "revise_synthesis", "finalize"])
    g.add_edge("refix_subject", "revise_synthesis")
    g.add_edge("revise_synthesis", "final_check")
    g.add_edge("finalize", END)
    return g.compile()


def _after_io_check(state: InsideOutState):
    return "io_finalize" if state.get("done") else "io_revise"


def build_inside_out():
    g = StateGraph(InsideOutState)
    for name, fn in (("io_prepare", nodes.io_prepare), ("io_score", nodes.io_score), ("io_check", nodes.io_check),
                     ("io_revise", nodes.io_revise), ("io_finalize", nodes.io_finalize)):
        g.add_node(name, fn)
    g.add_edge(START, "io_prepare")
    g.add_edge("io_prepare", "io_score")
    g.add_edge("io_score", "io_check")
    g.add_conditional_edges("io_check", _after_io_check, ["io_finalize", "io_revise"])
    g.add_edge("io_revise", "io_check")
    g.add_edge("io_finalize", END)
    return g.compile()


_GRAPHS: dict = {}
_GRAPH_LOCK = threading.Lock()


def _graph(name, build):
    with _GRAPH_LOCK:
        if name not in _GRAPHS: _GRAPHS[name] = build()
    return _GRAPHS[name]


def _config():
    # supersteps: each fix round adds a few; the default limit of 25 is too tight for 2 x 3 rounds
    return {"recursion_limit": 200, "max_concurrency": cfg.SUBJECT_WORKERS}


def _run_once(company, ticker, peers, period, mode, progress, documents) -> dict:
    shared: dict = {"stop": threading.Event()}
    state = {"company": company, "ticker": ticker, "peers": peers, "period": period, "mode": mode, "documents": documents,
             "progress": progress, "shared": shared}
    try:
        out = _graph("outside_in", build_outside_in).invoke(state, _config())
    except BaseException:
        if shared.get("failed") is not None: raise shared["failed"]  # the first failure is the one reported
        raise
    return out["result"]


def build_research():
    """Research phase only: plan, then every subject researched (and its retrieval reviewed) in parallel."""
    g = StateGraph(OutsideInState)
    g.add_node("plan", nodes.plan)
    g.add_node("research_subject", nodes.research_subject)
    g.add_edge(START, "plan")
    g.add_conditional_edges("plan", _fan_out_research, ["research_subject"])
    g.add_edge("research_subject", END)
    return g.compile()


def build_finish():
    """Everything after the research: calibrate and grade, fix rounds, synthesis, final check. Starts from finished subjects."""
    g = StateGraph(OutsideInState)
    g.add_node("calibrate_and_grade", nodes.calibrate_and_grade)
    g.add_node("fix_subject", nodes.fix_subject)
    g.add_node("synthesis", nodes.synthesis)
    g.add_node("final_check", nodes.final_check)
    g.add_node("refix_subject", nodes.fix_subject)
    g.add_node("revise_synthesis", nodes.revise_synthesis)
    g.add_node("finalize", nodes.finalize)
    g.add_edge(START, "calibrate_and_grade")
    g.add_conditional_edges("calibrate_and_grade", _after_calibrate, ["fix_subject", "calibrate_and_grade", "synthesis"])
    g.add_edge("fix_subject", "calibrate_and_grade")
    g.add_edge("synthesis", "final_check")
    g.add_conditional_edges("final_check", _after_final_check, ["refix_subject", "revise_synthesis", "finalize"])
    g.add_edge("refix_subject", "revise_synthesis")
    g.add_edge("revise_synthesis", "final_check")
    g.add_edge("finalize", END)
    return g.compile()


def _research_once(company, ticker, peers, period, mode, progress, documents, model) -> dict:
    shared: dict = {"stop": threading.Event()}
    state = {"company": company, "ticker": ticker, "peers": peers, "period": period, "mode": mode, "documents": documents,
             "progress": progress, "shared": shared, "model": model}
    try:
        return _graph("research", build_research).invoke(state, _config())
    except BaseException:
        if shared.get("failed") is not None: raise shared["failed"]
        raise


def _preflight(model: str) -> None:
    """One tiny request through the same call path, so an unavailable model (e.g. no Foundry deployment of that name) fails the run at the start."""
    from . import client as cl
    from .conversation import Conv
    c = Conv(f"check of model {model}", [], "Reply with the single word: ready", model=model)
    c.strict = False
    try:
        c.turn()
    except ResearchError:
        raise
    except Exception as e:
        raise ResearchError(f"The model {model} (Run B) could not be used: {cl._err(e) if hasattr(cl, '_err') else e}. "
                            "Check that a deployment of that name exists, or set BOARD_MODEL_B.") from e


def _finish_progress(progress):
    """The finishing phase reports 73-100 on its own scale; it fills the last third (66-100) of the combined run."""
    def cb(pct, msg=""):
        if progress: progress(int(66 + (max(72, min(pct, 100)) - 72) / 28 * 34), msg)
    return cb


def _run_two(company, ticker, peers, period, mode, progress, documents) -> dict:
    """Run A (BOARD_MODEL) and Run B (BOARD_MODEL_B) research the whole peer set independently and in parallel; the model then
    reconciles every indicator they scored differently, and the reconciled subjects go through grading, synthesis and checks once."""
    from .reconcile import reconcile
    from .progress import MonotonicProgress
    _preflight(cfg.MODEL_B)
    lock, pcts, last = threading.Lock(), [0, 0], [""]

    def reporter(k, label):
        def cb(pct, msg=""):
            with lock:
                pcts[k] = pct
                if msg: last[0] = f"{label}: {msg}"
                if progress: progress(int(2 + (sum(pcts) / 2) / 72 * 58), last[0])
        return cb

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(_research_once, company, ticker, peers, period, mode, reporter(0, "Run A"), documents, cfg.MODEL)
        fb = pool.submit(_research_once, company, ticker, peers, period, mode, reporter(1, "Run B"), documents, cfg.MODEL_B)
        errors = []
        outs = []
        for f in (fa, fb):
            try: outs.append(f.result())
            except BaseException as e: errors.append(e)
    if errors: raise errors[0]
    a, b = outs
    ctx, subjects_a, subjects_b = a["ctx"], a["subjects"], b["subjects"]
    if progress: progress(62, "Reconciling the two runs where they scored an indicator differently")
    block = reconcile(subjects_a, subjects_b, ctx)
    ctx["reconciliation"] = block
    gap = max([abs((r["a"] or 0) - (r["b"] or 0)) for r in block["rows"]] + [0])
    ctx["consistency_result"] = (f"Outside-in run A ({cfg.MODEL}) and run B ({cfg.MODEL_B}): {block['agreed']} of {block['total']} indicator scores identical; "
                                 f"{len(block['rows'])} reconciled by the model's recommendation (largest gap {gap} point{'s' if gap != 1 else ''}; "
                                 f"{'within' if gap <= 1 else 'NOT within'} the one-point tolerance of Rule 12).")
    ctx["notes"] = (f"Run A ({cfg.MODEL}): {_notes(subjects_a)} | Run B ({cfg.MODEL_B}): {_notes(subjects_b)}")
    ctx["prog"] = MonotonicProgress(_finish_progress(progress))
    state = {"ctx": ctx, "subjects": subjects_a, "rnd": 0, "jobs": [], "rest": [], "calibrated": False, "done": False}
    try:
        out = _graph("finish", build_finish).invoke(state, _config())
    except BaseException:
        if ctx.get("failed") is not None: raise ctx["failed"]
        raise
    return out["result"]


def _notes(subjects):
    from .checks import _retrieval_notes
    return _retrieval_notes(subjects)


def run_outside_in(company: str, ticker: str, peers: list[dict], period: str, mode: str, progress: Progress | None,
                   documents: list[dict] | None = None) -> dict:
    """One run: cfg.CONSISTENCY_RUNS is fixed at 1. _run_two (Run A and Run B with reconciliation, Rule 12) is kept but not used."""
    if cfg.CONSISTENCY_RUNS <= 1: return _run_once(company, ticker, peers, period, mode, progress, documents)
    return _run_two(company, ticker, peers, period, mode, progress, documents)


def run_inside_out(oi_run: dict, documents: list[dict], answers: dict[str, str], ratings: dict[str, int], progress: Progress | None) -> dict:
    out = _graph("inside_out", build_inside_out).invoke(
        {"oi_run": oi_run, "documents": documents, "answers": answers, "ratings": ratings, "progress": progress}, _config())
    return out["result"]

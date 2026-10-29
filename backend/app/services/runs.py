"""The assessment pipeline around the stored runs (replaces server/pipeline.py and the job bodies in server/app.py).

SKILL.md order: grade priors -> load_history into oi/io -> grade oi/io -> build deliverables. The skill subprocess calls are
direct calls to domain.engine (grade, load_history) and services.deliverables (build_*).
"""
from __future__ import annotations

import importlib
import os
from typing import Callable

from app.domain import view as convert
from app.log import get_logger
from app.services import jobs, repo, storage

log = get_logger(__name__)
Progress = Callable[[int, str], None]


# ---------------- grading and rendering ----------------

def grade(run: dict, check: bool = False) -> dict:
    """engine.grade -> {ok, problems:[str], warnings:[str]}; writes `computed` into run unless check."""
    from app.domain import engine
    return engine.grade(run, check=check)


def prepare(cid: str, progress: Progress | None = None) -> dict:
    """Grade priors, load them as history into the outside-in / inside-out runs, grade those. Returns grade results by stage."""
    from app.domain import engine
    p = progress or (lambda *_: None)
    res: dict = {}
    with repo.lock(cid):
        ps = repo.priors(cid)
        for k, pr in enumerate(ps):
            key = f"prior_{pr.get('run', {}).get('period') or k}"
            p(5 + k, f"Grading {key}")
            res[key] = engine.grade(pr)
            repo.write_prior(cid, pr)
        for stage in repo.STAGES:
            run = repo.read_run(cid, stage)
            if run is None: continue
            if ps:
                p(15, f"Loading {len(ps)} prior quarter(s) into {stage}")
                engine.load_history(run, ps)
            p(20, f"Grading {stage}")
            res[stage] = engine.grade(run)
            repo.write_run(cid, stage, run)
    return res


def build_all(cid: str, parts: set[str] | None = None, progress: Progress | None = None) -> dict:
    """Render deliverables into NEXUS_STORAGE_DIR/<id>/out and record them. parts: subset of oi, io, prior, quest."""
    from app.services import deliverables as D
    p = progress or (lambda *_: None)
    with repo.lock(cid):
        meta = repo.load_meta(cid); oi = repo.read_run(cid, "outside_in"); io = repo.read_run(cid, "inside_out"); prior = repo.latest_prior(cid)
        names = D.file_names(meta.get("short") or meta.get("name", cid), oi, io, prior)
        out = storage.ensure_out(cid)
        files = dict(meta.get("files") or {})
        want = parts or {"oi", "io", "prior", "quest"}
        steps: list[tuple[str, Callable, object]] = []
        if "oi" in want: steps += [("oi_docx", D.build_docx, oi), ("oi_html", D.build_dashboard, oi)]
        if "io" in want and io: steps += [("io_docx", D.build_docx, io), ("io_html", D.build_dashboard, io)]
        if "prior" in want and prior: steps.append(("prior_docx", D.build_docx, prior))
        if "quest" in want: steps.append(("quest", D.build_questionnaire, convert.company_of(oi)["name"]))
        if not io:
            for k in ("io_docx", "io_html"):
                if files.pop(k, None): repo.drop_file_record(cid, k)
        for n, (key, fn, src) in enumerate(steps):
            p(40 + int(55 * n / max(1, len(steps))), f"Building {names[key]}")
            old = files.get(key)
            target = out / names[key]
            tmp = storage.tmp_path(out, target.suffix)
            try:
                fn(src, str(tmp))
                storage.replace(tmp, target)
            finally:
                storage.remove(tmp)
            repo.record_file(cid, key, names[key]); files[key] = names[key]
            if old and old != names[key] and old not in (names[k] for k in files if k != key and k in names):
                try: os.remove(out / old)
                except OSError: pass
        repo.save_meta(cid, repo.load_meta(cid))  # bump 'updated'
    p(98, "Deliverables built")
    return files


# ---------------- research module (app.agents.graph, written separately) ----------------

def research_module():
    """Lazy import of the LangGraph research module; ImportError -> None. Tests monkeypatch this."""
    try: return importlib.import_module("app.agents.graph")
    except ImportError: return None


def research_status() -> dict:
    mod = research_module()
    if mod is None: return {"enabled": False, "reason": "the research module (app.agents.graph) is not available"}
    try:
        ok, reason = mod.research_enabled()
        return {"enabled": bool(ok), "reason": str(reason or "")}
    except Exception as e:  # noqa: BLE001
        return {"enabled": False, "reason": f"research_enabled() failed: {type(e).__name__}: {e}"}


def research_errors(mod) -> tuple:
    return tuple(x for x in (getattr(mod, "ResearchError", None), ValueError) if x)


def job_error(e: Exception) -> jobs.JobError:
    """ResearchError (or a ValueError from research) -> a clean job error with its problem list."""
    return jobs.JobError(str(e), [p if isinstance(p, str) else (f"[{p[0]}] {p[1]}: {p[2]}" if len(p) == 3 else " ".join(map(str, p)))
                                  for p in getattr(e, "problems", None) or []])


# ---------------- job bodies ----------------

def build_work(cid: str, parts: set[str] | None = None):
    def work(job: jobs.Job):
        res = prepare(cid, job.update)
        bad = {k: v["problems"] for k, v in res.items() if v["problems"]}
        if bad: raise jobs.JobError("Rule check failed after loading history", [f"{k}: {p}" for k, ps in bad.items() for p in ps], {"company_id": cid})
        build_all(cid, parts, job.update)
        return {"company_id": cid}
    return work


def research_work(company: str, ticker: str, peers: list[dict], period: str, mode: str, provided: list[dict]):
    def work(job: jobs.Job):
        mod = research_module()
        if mod is None: raise jobs.JobError("the research module (app.agents.graph) is not available")
        job.update(2, f"Researching {company} and {len(peers)} peers" + (f", with {len(provided)} document(s) you supplied" if provided else ""))
        kw = {"documents": provided} if provided else {}
        try: run = mod.run_outside_in(company, ticker, peers, period, mode, lambda pct, msg="": job.update(2 + int(pct * 0.8), msg), **kw)
        except research_errors(mod) as e: raise job_error(e) from e
        if not isinstance(run, dict) or not isinstance(run.get("subjects"), list): raise jobs.JobError("research returned no run file")
        run.setdefault("run", {}).setdefault("mode", mode); run["run"].setdefault("period", period); run["run"].setdefault("stage", "outside_in")
        comp = convert.company_of(run); backup = None
        try:
            # Every research run is a fresh, standalone assessment: nothing saved for the same company (earlier quarters, inside-out
            # runs, survey answers) is attached to it. NEXUS_REUSE_HISTORY=1 restores the legacy "new period of a company on file".
            reuse = (os.environ.get("NEXUS_REUSE_HISTORY") or "").lower() in ("1", "true", "yes")
            cid = repo.match_id(convert.company_id(comp), comp["name"], comp.get("ticker", "")) if reuse else None
            if cid: jobs.hold(cid, job); backup = repo.new_period(cid, run)
            else: cid = repo.create(run, source="research"); jobs.hold(cid, job)
        except (ValueError, repo.StoreError, jobs.Busy) as e:
            raise jobs.JobError("a job is already running for this company" if isinstance(e, jobs.Busy) else str(e)) from e
        job.update(84, f"Stored as '{cid}'; grading")
        try: g = prepare(cid, lambda p, m: job.update(84, m))["outside_in"]
        except BaseException:
            if backup: repo.restore(cid, backup)
            raise
        if g["problems"]:
            if backup:  # a same-period refresh that fails keeps the assessment it would have replaced
                repo.restore(cid, backup)
                raise jobs.JobError(f"the research run failed {len(g['problems'])} rule check(s); the previous {period} assessment was kept", g["problems"], {"company_id": cid})
            repo.set_problems(cid, g["problems"])
            raise jobs.JobError(f"the research run failed {len(g['problems'])} rule check(s); stored as '{cid}' for review", g["problems"], {"company_id": cid})
        build_all(cid, None, lambda p, m: job.update(86 + int((p - 40) * 0.2), m))
        cons = ((run.get("coverage") or {}).get("consistency_result") or "")
        warnings = list(g["warnings"]) + ([f"Consistency test (Rule 12): {cons}"] if ("FAIL" in cons or "NOT within" in cons) else [])
        return {"company_id": cid, "warnings": warnings}
    return work


def inside_out_work(cid: str, mode: str, extracted: list[dict], answers: dict, ratings: dict, n: int):
    def work(job: jobs.Job):
        mod = research_module()
        if mod is None: raise jobs.JobError("the research module (app.agents.graph) is not available")
        oi = repo.read_run(cid, "outside_in")
        job.update(2, f"Reading {len(extracted)} document(s) and {sum(1 for a in answers.values() if a)} answer(s)")
        try: io = mod.run_inside_out(oi, extracted, answers, ratings, lambda pct, msg="": job.update(2 + int(pct * 0.8), msg))
        except research_errors(mod) as e: raise job_error(e) from e
        if not isinstance(io, dict) or not isinstance(io.get("subjects"), list): raise jobs.JobError("research returned no inside-out run")
        r = io.setdefault("run", {}); r["stage"] = "inside_out"; r["mode"] = mode; r.setdefault("period", oi["run"].get("period"))
        io.setdefault("self_assessment_answers", answers); io.setdefault("self_ratings", {str(k): v for k, v in ratings.items()})
        with repo.lock(cid):
            repo.write_run(cid, "inside_out", io, keep_prev=True); repo.set_used(cid, n)
            repo.set_problems(cid, None)
        job.update(84, "Grading")
        g = prepare(cid, lambda p, msg: job.update(84, msg)).get("inside_out", {"problems": [], "warnings": []})
        if g["problems"]:
            repo.set_problems(cid, g["problems"])
            raise jobs.JobError(f"the inside-out run failed {len(g['problems'])} rule check(s); stored for review", g["problems"], {"company_id": cid})
        build_all(cid, {"io"}, lambda p, m: job.update(86 + int((p - 40) * 0.2), m))
        return {"company_id": cid, "warnings": g["warnings"]}
    return work

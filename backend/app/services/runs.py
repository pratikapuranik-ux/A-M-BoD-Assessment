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
    """Render deliverables into BOARD_STORAGE_DIR/<id>/out and record them. parts: subset of oi, io, prior, quest."""
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

def read_documents(job, docs: list[dict], *, max_slot: int | None = None, search: dict | None = None) -> list[dict]:
    """Read the uploaded documents (slow for long PDFs, so it happens here, with progress, not while the request waits).
    search={'company': {...}, 'peers': [...]}: outside-in. Every PDF becomes text, each file is assigned to the company or a peer
    (by its folder, unless the page said which) and kept for reuse by this assessment; the agents then search the text instead of
    receiving it. Without it (inside-out) the documents go to the model whole, condensed when they are over one request."""
    if not docs: return []
    from app.api.errors import ApiError
    from app.api.uploads import extract_documents
    from app.services import library, subjects
    job.update(2, f"Reading {len(docs)} uploaded file(s)")
    kw = {}
    if search:
        kw = dict(as_text=True, scope=library.scope(search["company"].get("ticker", ""), search.get("period", "")),
                  who=lambda name: subjects.assign(name, search["company"], search["peers"]))
    try: out, probs = extract_documents(docs, max_slot=max_slot, progress=lambda m: job.update(2, m), **kw)
    except ApiError as e: raise jobs.JobError(e.error) from e
    if probs: raise jobs.JobError("some documents could not be read", probs)
    for note in out.notes: job.update(2, note)  # skipped files inside zips go to the job's log
    if search: return out  # searched, so the size of the upload does not matter (see analyse_documents)
    from app.services import digest
    try: notes = digest.fit(out, lambda m: job.update(3, m))  # one request holds about a million tokens: condense what does not fit
    except digest.DigestError as e: raise jobs.JobError(f"the documents are too large to research: {e}") from e
    for note in notes: job.update(3, note)
    return out


def analyse_documents(job, docs: list[dict], names: list[str], period: str, ticker: str) -> dict[int, str]:
    """Fact sheets for the long documents (kept with each file for reuse) and a cross-document review per subject. A failure here
    never stops the run: the documents can still be searched."""
    import os
    from app.services import factsheet, library
    mode = (os.environ.get("BOARD_DOC_ANALYSIS") or "company").strip().lower()  # company: only the company's own documents; all: peers too; off: search only
    if not docs or mode == "off": return {}
    if mode != "all":  # peers' documents are searched, not summarised: the company is the subject of the assessment
        docs = [d for d in docs if int(d.get("subject") or 0) == 0]; names = names[:1]
        if not docs: return {}
    scope = library.scope(ticker, period)
    def keep(d):  # stored the moment it is complete: a stall or restart does not lose it
        if d.get("sha"): library.update(scope, d["sha"], facts=d["facts"])
    try: findings, notes = factsheet.prepare(docs, names, lambda m: job.update(4, m), on_sheet=keep)
    except Exception as e:  # noqa: BLE001
        job.update(4, f"Key facts could not be extracted ({type(e).__name__}: {str(e)[:200]}); the documents will be searched instead"); return {}
    for n in notes: job.update(4, n)
    return findings


def build_work(cid: str, parts: set[str] | None = None):
    def work(job: jobs.Job):
        res = prepare(cid, job.update)
        bad = {k: v["problems"] for k, v in res.items() if v["problems"]}
        if bad: raise jobs.JobError("Rule check failed after loading history", [f"{k}: {p}" for k, ps in bad.items() for p in ps], {"company_id": cid})
        build_all(cid, parts, job.update)
        return {"company_id": cid}
    return work


def research_work(company: str, ticker: str, peers: list[dict], period: str, mode: str, docs: list[dict]):
    def work(job: jobs.Job):
        mod = research_module()
        if mod is None: raise jobs.JobError("the research module (app.agents.graph) is not available")
        from app.agents import tools as agent_tools
        job.update(2, "Scoring ruling for 1.4 (quality means product and service quality): " + ("on" if agent_tools.ruling_1_4_on() else "off, so 1.4 is read as before"))
        provided = read_documents(job, docs, search={"company": {"name": company, "ticker": ticker}, "peers": peers, "period": period})
        findings = analyse_documents(job, provided, [company] + [p["name"] for p in peers], period, ticker)
        job.update(6, f"Researching {company} and {len(peers)} peers" + (f", with {len(provided)} document(s) you supplied" if provided else ""))
        kw = {"documents": provided, "findings": findings} if provided else {}
        try: run = mod.run_outside_in(company, ticker, peers, period, mode, lambda pct, msg="": job.update(2 + int(pct * 0.8), msg), **kw)
        except research_errors(mod) as e: raise job_error(e) from e
        if not isinstance(run, dict) or not isinstance(run.get("subjects"), list): raise jobs.JobError("research returned no run file")
        run.setdefault("run", {}).setdefault("mode", mode); run["run"].setdefault("period", period); run["run"].setdefault("stage", "outside_in")
        run["run"]["documents_provided"] = [{"name": d.get("name", ""), "slot": 0, "subject": d.get("subject", 0)} for d in provided]  # names only, so the inputs can be shown again later
        comp = convert.company_of(run); backup = None
        try:
            # Every research run is a fresh, standalone assessment: nothing saved for the same company (earlier quarters, inside-out
            # runs, survey answers) is attached to it. BOARD_REUSE_HISTORY=1 restores the legacy "new period of a company on file".
            reuse = (os.environ.get("BOARD_REUSE_HISTORY") or "").lower() in ("1", "true", "yes")
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
        warnings = list(g["warnings"]) + list(getattr(provided, "notes", [])) + ([f"Consistency test (Rule 18): {cons}"] if ("FAIL" in cons or "NOT within" in cons) else [])
        return {"company_id": cid, "warnings": warnings}
    return work


def inside_out_work(cid: str, mode: str, docs: list[dict], answers: dict, ratings: dict, n: int, max_slot: int):
    def work(job: jobs.Job):
        mod = research_module()
        if mod is None: raise jobs.JobError("the research module (app.agents.graph) is not available")
        oi = repo.read_run(cid, "outside_in")
        extracted = read_documents(job, docs, max_slot=max_slot)
        if n == 0 and not extracted: raise jobs.JobError("none of the documents could be used, and there are no self-assessment responses")
        job.update(2, f"Reading {len(extracted)} document(s) and {sum(1 for a in answers.values() if a)} answer(s)")
        try: io = mod.run_inside_out(oi, extracted, answers, ratings, lambda pct, msg="": job.update(2 + int(pct * 0.8), msg))
        except research_errors(mod) as e: raise job_error(e) from e
        if not isinstance(io, dict) or not isinstance(io.get("subjects"), list): raise jobs.JobError("research returned no inside-out run")
        r = io.setdefault("run", {}); r["stage"] = "inside_out"; r["mode"] = mode; r.setdefault("period", oi["run"].get("period"))
        # Anonymity: the answers themselves are never written to the run file, only how many responses informed it
        io.pop("self_assessment_answers", None); io["self_assessment_responses"] = int(n or 0)
        r["documents_provided"] = [{"name": d.get("name", ""), "slot": int(d.get("slot") or 0)} for d in extracted]
        io.setdefault("self_ratings", {str(k): v for k, v in ratings.items()})
        with repo.lock(cid):
            repo.write_run(cid, "inside_out", io, keep_prev=True); repo.set_used(cid, n)
            repo.set_problems(cid, None)
        job.update(84, "Grading")
        g = prepare(cid, lambda p, msg: job.update(84, msg)).get("inside_out", {"problems": [], "warnings": []})
        if g["problems"]:
            repo.set_problems(cid, g["problems"])
            raise jobs.JobError(f"the inside-out run failed {len(g['problems'])} rule check(s); stored for review", g["problems"], {"company_id": cid})
        build_all(cid, {"io"}, lambda p, m: job.update(86 + int((p - 40) * 0.2), m))
        return {"company_id": cid, "warnings": list(g["warnings"]) + list(getattr(extracted, "notes", []))}
    return work

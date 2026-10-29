"""Local prototype server: static front end at / and the JSON API under /api.

    python server/app.py            # http://127.0.0.1:5173  (PORT / HOST env vars override)

Data lives in BOARD_DATA_DIR (default ./data). The app starts with no companies; each one is researched or imported.
"""
from __future__ import annotations

import importlib
import json
import logging
import os
import random
import re
import shutil
import sys
import tempfile
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path: sys.path.insert(0, HERE)


def _load_env(path: str) -> None:
    """Read KEY=value lines from the project's .env into the environment; values already set in the shell win."""
    if not os.path.isfile(path): return
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line: continue
            k, v = line.split("=", 1); k = k.strip().removeprefix("export ").strip(); v = v.strip().strip('"').strip("'")
            if k and v and k not in os.environ: os.environ[k] = v


_load_env(os.environ.get("BOARD_ENV_FILE") or os.path.join(os.path.dirname(HERE), ".env"))

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from starlette.exceptions import HTTPException as StarletteHTTPException  # noqa: E402

import convert  # noqa: E402
import extract  # noqa: E402
import jobs  # noqa: E402
import pipeline  # noqa: E402
import store  # noqa: E402

ROOT = convert.ROOT
FILE_KEYS = ("oi_docx", "oi_html", "io_docx", "io_html", "prior_docx", "quest")
PERIOD = re.compile(r"^\d{4}-Q[1-4]$")
EMAIL = re.compile(r"^[^@\s<>\"']+@[^@\s<>\"']+\.[^@\s<>\"']*[^@\s<>\"'.]$")
NAMED_EMAIL = re.compile(r"^[^<>]*<([^<>]*)>$")  # "Name <addr>"
MAX_EMAILS = 50  # per request; store.MAX_INVITES per survey
MAX_OI_DOCS = 10  # documents supplied with an outside-in research request
CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
# Anonymity guardrail: the inside-out view is prepared only once this many people have responded, and refreshed only
# with the same responses or at least this many more. Default 3; BOARD_MIN_RESPONSES in .env lowers it for a demo.
MIN_RESPONSES = max(1, int(os.environ.get("BOARD_MIN_RESPONSES") or 3))


class ApiError(Exception):
    def __init__(self, status: int, error: str, problems: list | None = None, job_id: str | None = None):
        super().__init__(error); self.status = status; self.error = error; self.problems = problems or []; self.job_id = job_id


def _submit(kind: str, work, *keys: str) -> jobs.Job:
    try: return jobs.submit(kind, work, keys)
    except jobs.Busy as e: raise ApiError(409, "a job is already running for this company; wait for it to finish", job_id=e.job.id)


def _job_error(e: Exception) -> jobs.JobError:
    """research.ResearchError (or a ValueError from research) -> a clean job error with its problem list."""
    return jobs.JobError(str(e), [p if isinstance(p, str) else (f"[{p[0]}] {p[1]}: {p[2]}" if len(p) == 3 else " ".join(map(str, p)))
                                  for p in getattr(e, "problems", None) or []])


def _research_errors(mod) -> tuple:
    return tuple(x for x in (getattr(mod, "ResearchError", None), ValueError) if x)


def _research():
    """Lazy import of server/research.py (written separately); ImportError -> None."""
    try: return importlib.import_module("research")
    except ImportError: return None


def research_status() -> dict:
    mod = _research()
    if mod is None: return {"enabled": False, "reason": "server/research.py is not available"}
    try:
        ok, reason = mod.research_enabled(); return {"enabled": bool(ok), "reason": str(reason or "")}
    except Exception as e:  # noqa: BLE001
        return {"enabled": False, "reason": f"research_enabled() failed: {type(e).__name__}: {e}"}


def _build_job(cid: str, parts: set[str] | None = None, kind: str = "build") -> jobs.Job:
    def work(job: jobs.Job):
        res = pipeline.prepare(cid, job.update)
        bad = {k: v["problems"] for k, v in res.items() if v["problems"]}
        if bad: raise jobs.JobError("Rule check failed after loading history", [f"{k}: {p}" for k, ps in bad.items() for p in ps], {"company_id": cid})
        pipeline.build_all(cid, parts, job.update)
        return {"company_id": cid}
    return _submit(kind, work, cid)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    os.makedirs(store.companies_dir(), exist_ok=True)
    yield


app = FastAPI(title="A&M Board Assessment (local prototype)", lifespan=lifespan)


@app.exception_handler(ApiError)
async def _api_error(_r: Request, e: ApiError):
    return JSONResponse({"error": e.error, "problems": e.problems, **({"job_id": e.job_id} if e.job_id else {})}, status_code=e.status)


@app.exception_handler(PermissionError)
async def _locked(_r: Request, e: PermissionError):
    return JSONResponse({"error": "a file is in use by OneDrive or another program; try again in a moment", "problems": []}, status_code=503)


@app.exception_handler(StarletteHTTPException)
async def _http_error(_r: Request, e: StarletteHTTPException):
    return JSONResponse({"error": str(e.detail), "problems": []}, status_code=e.status_code)


@app.exception_handler(RequestValidationError)
async def _validation_error(_r: Request, e: RequestValidationError):
    return JSONResponse({"error": "invalid request", "problems": [f"{'.'.join(map(str, x.get('loc', [])))}: {x.get('msg')}" for x in e.errors()]}, status_code=422)


MAX_BODY = 140 * 1024 * 1024  # 100 MB of documents once base64-encoded, plus the rest of the request


async def _body(request: Request) -> dict:
    if int(request.headers.get("content-length") or 0) > MAX_BODY: raise ApiError(413, f"the upload is too large; at most {extract.MAX_FILE // 2**20} MB per file and {extract.MAX_UPLOAD // 2**20} MB in total")
    try: b = await request.json()
    except Exception: raise ApiError(400, "request body must be JSON")
    if not isinstance(b, dict): raise ApiError(400, "request body must be a JSON object")
    return b


def _company(cid: str) -> str:
    if not store.exists(cid): raise ApiError(404, f"company '{cid}' not found")
    return cid


# ---------------- API ----------------

@app.get("/api/health")
def health():
    return {"ok": True, "research": research_status()}


@app.get("/api/framework")
def framework():
    return convert.framework()


@app.get("/api/companies")
def companies():
    out = []
    for c in store.list_ids():
        try: out.append(store.summary(c))
        except Exception as e:  # noqa: BLE001 - one unreadable company (deleted mid-list, held by OneDrive) must not hide the rest
            logging.getLogger(__name__).warning("company %s skipped from the list: %s: %s", c, type(e).__name__, e)
    return out


@app.get("/api/companies/{cid}/view")
def view(cid: str, mode: str | None = None):
    _company(cid)
    if mode and mode not in convert.FW["run_modes"]: raise ApiError(400, f"mode must be one of {list(convert.FW['run_modes'])}")
    return store.view(cid, mode)


@app.get("/api/companies/{cid}/files/{key}")
def file(cid: str, key: str):
    _company(cid)
    if key not in FILE_KEYS: raise ApiError(404, f"unknown file key '{key}' (one of {list(FILE_KEYS)})")
    p = store.file_path(cid, key)
    if not p: raise ApiError(404, f"{key} has not been built for '{cid}'")
    return FileResponse(p, filename=os.path.basename(p))


def _check_runs(oi, io, priors) -> list[str]:
    """Shape checks, then grade.py --check on each file in a temp dir. Returns blocking problems."""
    probs: list[str] = []
    def shape(r, label, stage):
        if not isinstance(r, dict) or not isinstance(r.get("run"), dict) or not isinstance(r.get("subjects"), list):
            probs.append(f"{label}: not a run file (needs 'run' and 'subjects')"); return False
        if stage and r["run"].get("stage", "outside_in") != stage: probs.append(f"{label}: run.stage must be '{stage}'")
        if r["run"].get("simulated"): probs.append(f"{label}: simulated assessments cannot be added; use a real outside-in or inside-out run")
        if sum(1 for s in r["subjects"] if isinstance(s, dict) and s.get("role") == "company") != 1: probs.append(f"{label}: exactly one subject must have role 'company'"); return False
        return True
    ok_oi = shape(oi, "outside_in", "outside_in")
    if io is not None and shape(io, "inside_out", "inside_out") and ok_oi:
        if convert.company_of(io)["name"] != convert.company_of(oi)["name"]: probs.append("inside_out: company differs from the outside-in run")
        if io["run"].get("period") != oi["run"].get("period"): probs.append("inside_out: period differs from the outside-in run")
    seen: set[str] = set()
    for k, p in enumerate(priors):
        if not shape(p, f"prior[{k}]", None): continue
        pp = str(p["run"].get("period") or "")
        if pp in seen: probs.append(f"prior[{k}]: period {pp} is given more than once")
        seen.add(pp)
        if ok_oi and pp >= str(oi["run"].get("period") or ""): probs.append(f"prior[{k}]: period {pp} is not earlier than the current run ({oi['run'].get('period')})")
    if probs: return probs
    tmp = tempfile.mkdtemp(prefix="import_")
    try:
        for label, r in [("outside_in", oi)] + ([("inside_out", io)] if io is not None else []) + [(f"prior {p['run'].get('period')}", p) for p in priors]:
            path = os.path.join(tmp, "run.json")
            with open(path, "w", encoding="utf-8") as f: json.dump(r, f)
            g = pipeline.grade(path, check=True); probs += [f"{label}: {x}" for x in g["problems"]]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return probs


@app.post("/api/companies/import")
async def import_company(request: Request):
    b = await _body(request)
    oi, io, priors = b.get("outside_in"), b.get("inside_out"), b.get("priors") or []
    if oi is None: raise ApiError(400, "outside_in run is required")
    if not isinstance(priors, list): raise ApiError(400, "priors must be a list of run files")
    probs = _check_runs(oi, io, priors)
    if probs: raise ApiError(422, "the run files failed the rule check", probs)
    cid = convert.company_id(convert.company_of(oi))
    if store.exists(cid):
        if not b.get("replace"): raise ApiError(409, f"company '{cid}' already exists; send replace: true to overwrite")
        _delete(cid)
    try: cid = store.create(oi, io, priors, source="imported", cid=cid)
    except store.StoreError as e: raise ApiError(409, str(e))
    return {"id": cid, "job_id": _build_job(cid, kind="import").id}


@app.post("/api/research")
async def research(request: Request):
    b = await _body(request)
    company, ticker, peers, period, mode = (b.get("company") or "").strip(), (b.get("ticker") or "").strip(), b.get("peers"), (b.get("period") or "").strip(), b.get("mode") or "director_request"
    probs = []
    if not company: probs.append("company is required")
    if not isinstance(peers, list) or not 2 <= len(peers) <= convert.FW["max_peers"]: probs.append(f"peers: give 2-{convert.FW['max_peers']} peers")
    elif any(not isinstance(p, dict) or not (p.get("name") or "").strip() for p in peers): probs.append("peers: each peer needs a name (and ideally a ticker)")
    if not PERIOD.match(period): probs.append("period must be YYYY-Qn")
    if mode not in convert.FW["run_modes"]: probs.append(f"mode must be one of {list(convert.FW['run_modes'])}")
    docs = b.get("documents") or []
    if not isinstance(docs, list) or len(docs) > MAX_OI_DOCS: probs.append(f"documents: give a list of at most {MAX_OI_DOCS} files")
    if probs: raise ApiError(400, "invalid research request", probs)
    provided, total = [], 0
    for d in docs:
        if not isinstance(d, dict): probs.append("each document must be an object"); continue
        total += len(str(d.get("data_b64") or "")) * 3 // 4
        if total > extract.MAX_UPLOAD: raise ApiError(400, f"{d.get('name') or 'document'}: the documents together exceed {extract.MAX_UPLOAD // 2**20} MB; send fewer or smaller files")
        try: provided.append(extract.extract_b64(dict(d, slot=0)))
        except extract.ExtractError as e: probs.append(str(e))
    if not probs:
        try: extract.fit_pdfs(provided)
        except extract.ExtractError as e: probs.append(str(e))
    if probs: raise ApiError(400, "some documents could not be read", probs)
    st = research_status()
    if not st["enabled"]: raise ApiError(503, "research is not available: " + st["reason"])
    peers = [{"name": p["name"].strip(), "ticker": (p.get("ticker") or "").strip()} for p in peers]

    pending = convert.slug(convert.short_name(company), ticker)
    mid = store.match_id(pending, company, ticker)
    try:
        if mid: store.check_period(mid, period)
    except ValueError as e: raise ApiError(409, str(e))

    def work(job: jobs.Job):
        mod = _research()
        if mod is None: raise jobs.JobError("server/research.py is not available")
        job.update(2, f"Researching {company} and {len(peers)} peers" + (f", with {len(provided)} document(s) you supplied" if provided else ""))
        kw = {"documents": provided} if provided else {}
        try: run = mod.run_outside_in(company, ticker, peers, period, mode, lambda pct, msg="": job.update(2 + int(pct * 0.8), msg), **kw)
        except _research_errors(mod) as e: raise _job_error(e) from e
        if not isinstance(run, dict) or not isinstance(run.get("subjects"), list): raise jobs.JobError("research returned no run file")
        run.setdefault("run", {}).setdefault("mode", mode); run["run"].setdefault("period", period); run["run"].setdefault("stage", "outside_in")
        comp = convert.company_of(run); backup = None
        try:
            cid = store.match_id(convert.company_id(comp), comp["name"], comp.get("ticker", ""))  # same name and ticker: a new period
            if cid: jobs.hold(cid, job); backup = store.new_period(cid, run)
            else: cid = store.create(run, source="research"); jobs.hold(cid, job)
        except (ValueError, store.StoreError, jobs.Busy) as e:
            raise jobs.JobError("a job is already running for this company" if isinstance(e, jobs.Busy) else str(e)) from e
        job.update(84, f"Stored as '{cid}'; grading")
        try: g = pipeline.prepare(cid, lambda p, m: job.update(84, m))["outside_in"]
        except BaseException:
            if backup: store.restore(cid, backup)
            raise
        if g["problems"]:
            if backup:  # a same-period refresh that fails keeps the assessment it would have replaced
                store.restore(cid, backup)
                raise jobs.JobError(f"the research run failed {len(g['problems'])} rule check(s); the previous {period} assessment was kept", g["problems"], {"company_id": cid})
            meta = store.load_meta(cid); meta["problems"] = g["problems"]; store.save_meta(cid, meta)
            raise jobs.JobError(f"the research run failed {len(g['problems'])} rule check(s); stored as '{cid}' for review", g["problems"], {"company_id": cid})
        pipeline.build_all(cid, None, lambda p, m: job.update(86 + int((p - 40) * 0.2), m))
        return {"company_id": cid, "warnings": g["warnings"]}
    return {"job_id": _submit("research", work, mid or pending).id}


def _idle(cid: str) -> None:
    if j := jobs.active(cid): raise ApiError(409, "a job is running for this company", job_id=j.id)


@app.post("/api/companies/{cid}/inside-out")
async def inside_out(cid: str, request: Request):
    _company(cid); _idle(cid)
    b = await _body(request)
    meta = store.load_meta(cid)
    mode = b.get("mode") or meta.get("mode") or "director_request"
    docs = b.get("documents") or []
    probs = []
    if mode not in convert.FW["run_modes"]: probs.append(f"mode must be one of {list(convert.FW['run_modes'])}")
    if not isinstance(docs, list): probs.append("documents must be a list")
    if probs: raise ApiError(400, "invalid inside-out request", probs)
    nd = len(convert.FW["inside_out_priority_docs"])
    s = store.load_survey(cid); n = len(s["responses"]); answers, ratings = _combined(s["responses"])
    extracted, total = [], 0
    for d in docs:
        if not isinstance(d, dict): probs.append("each document must be an object"); continue
        total += len(str(d.get("data_b64") or "")) * 3 // 4
        if total > extract.MAX_UPLOAD: raise ApiError(400, f"{d.get('name') or 'document'}: the documents together exceed {extract.MAX_UPLOAD // 2**20} MB; send fewer or smaller files")
        try:
            slot = int(d.get("slot") or 0)
            if not 0 <= slot <= nd: raise extract.ExtractError(f"{d.get('name')}: slot must be 0-{nd}")
            x = extract.extract_b64(dict(d, slot=slot)); extracted.append(x)
        except (extract.ExtractError, ValueError) as e: probs.append(str(e))
    if not probs:
        try: extract.fit_pdfs(extracted)
        except extract.ExtractError as e: probs.append(str(e))
    if probs: raise ApiError(400, "some documents could not be read", probs)
    ok, why = _can_generate(n, s.get("used"))
    if not ok: raise ApiError(409, why)
    st = research_status()
    if not st["enabled"]: raise ApiError(503, "research is not available: " + st["reason"])

    def work(job: jobs.Job):
        mod = _research()
        if mod is None: raise jobs.JobError("server/research.py is not available")
        oi = store.read_run(cid, "outside_in")
        job.update(2, f"Reading {len(extracted)} document(s) and {sum(1 for a in answers.values() if a)} answer(s)")
        try: io = mod.run_inside_out(oi, extracted, answers, ratings, lambda pct, msg="": job.update(2 + int(pct * 0.8), msg))
        except _research_errors(mod) as e: raise _job_error(e) from e
        if not isinstance(io, dict) or not isinstance(io.get("subjects"), list): raise jobs.JobError("research returned no inside-out run")
        r = io.setdefault("run", {}); r["stage"] = "inside_out"; r["mode"] = mode; r.setdefault("period", oi["run"].get("period"))
        io.setdefault("self_assessment_answers", answers); io.setdefault("self_ratings", {str(k): v for k, v in ratings.items()})
        with store.lock(cid):
            old = store.run_path(cid, "inside_out")
            if os.path.exists(old): shutil.copy(old, old.replace(".json", ".prev.json"))
            store.write_run(cid, "inside_out", io); store.set_used(cid, n)
            m = store.load_meta(cid); m.pop("problems", None); store.save_meta(cid, m)
        job.update(84, "Grading")
        g = pipeline.prepare(cid, lambda p, msg: job.update(84, msg)).get("inside_out", {"problems": [], "warnings": []})
        if g["problems"]:
            m = store.load_meta(cid); m["problems"] = g["problems"]; store.save_meta(cid, m)
            raise jobs.JobError(f"the inside-out run failed {len(g['problems'])} rule check(s); stored for review", g["problems"], {"company_id": cid})
        pipeline.build_all(cid, {"io"}, lambda p, m: job.update(86 + int((p - 40) * 0.2), m))
        return {"company_id": cid, "warnings": g["warnings"]}
    return {"job_id": _submit("inside_out", work, cid).id}


# ---------------- board self-assessment (anonymous) ----------------

def _combined(rs: list[dict]) -> tuple[dict, dict]:
    """All responses as one set of answers and ratings averaged to 1, 3 or 5. Each question's answers are shuffled on their
    own and numbered after blanks are dropped, so "Response 2" is not the same person from one question to the next."""
    answers = {}
    for k in range(1, len(convert.FW["questionnaire"]) + 1):
        ts = [t for r in rs if (t := str(r["answers"].get(str(k)) or "").strip())]
        answers[str(k)] = "\n\n".join(f"Response {n}: {t}" for n, t in enumerate(random.sample(ts, len(ts)), 1))
    ratings = {}
    for d in convert.DIMS:
        v = [r["ratings"][d] for r in rs if type(r.get("ratings", {}).get(d)) is int]
        if v: a = sum(v) / len(v); ratings[d] = 1 if a < 2 else 3 if a < 4 else 5
    return answers, ratings


def _can_generate(n: int, used: int | None) -> tuple[bool, str | None]:
    """Anonymity: at least MIN_RESPONSES, and a refresh only on the same responses or MIN_RESPONSES more (differencing)."""
    if n < MIN_RESPONSES:
        return False, f"{n} of {MIN_RESPONSES} self-assessment responses received. To keep responses anonymous, the inside-out view is prepared only once at least {MIN_RESPONSES} people have responded."
    if used is None or n == used or n - used >= MIN_RESPONSES: return True, None
    k = MIN_RESPONSES - (n - used)
    return False, f"Wait for {k} more response{'s' if k != 1 else ''} before refreshing the inside-out view, so a single new response cannot be singled out"


def _base_url(request: Request) -> str:
    pub = (os.environ.get("BOARD_PUBLIC_URL") or "").strip().rstrip("/")
    return pub + "/" if pub else str(request.base_url)


def _survey_status(cid: str, request: Request) -> dict:
    s = store.load_survey(cid); base = _base_url(request); n = len(s["responses"]); ok, why = _can_generate(n, s.get("used"))
    return {"invites": [{"token": i["token"], "email": i["email"], "created": i["created"], "responded": i["responded"], "link": f"{base}?take={i['token']}"} for i in s["invites"]],
            "responses": n, "count": n, "min": MIN_RESPONSES, "can_generate": ok, "reason": why, "local": urlsplit(base).hostname in LOCAL_HOSTS}


def _clean_response(b: dict, paper: bool = False) -> tuple[dict, dict]:
    nq = len(convert.FW["questionnaire"]); a, r = b.get("answers") or {}, b.get("ratings") or {}
    if not isinstance(a, dict) or not isinstance(r, dict): raise ApiError(400, "answers and ratings must be objects")
    answers = {str(k): CTRL.sub("", str(a.get(str(k)) or "")).strip()[:4000] for k in range(1, nq + 1)}
    ratings = {str(d): v for d, v in r.items() if str(d) in convert.DIMS and type(v) is int and v in (1, 3, 5)}
    if paper and not any(answers.values()) and not ratings: raise ApiError(400, "the questionnaire has no answers or ratings")
    if not paper and not any(answers.values()): raise ApiError(400, "answer at least one question")
    return answers, ratings


def _emails(raw) -> list[str]:
    if not isinstance(raw, list) or not all(isinstance(e, str) for e in raw): raise ApiError(400, "emails must be a list of strings")
    out = [(m.group(1) if (m := NAMED_EMAIL.match(e.strip())) else e).strip() for e in raw if e.strip()]
    if not out: raise ApiError(400, "give at least one email address")
    if len(out) > MAX_EMAILS: raise ApiError(400, f"at most {MAX_EMAILS} email addresses at a time")
    if bad := [e for e in out if len(e) > 254 or not EMAIL.match(e)]: raise ApiError(400, "not an email address", [e[:80] for e in bad[:20]])
    return out


@app.get("/api/companies/{cid}/survey")
def survey_status(cid: str, request: Request):
    return _survey_status(_company(cid), request)


@app.post("/api/companies/{cid}/survey/invite")
async def survey_invite(cid: str, request: Request):
    _company(cid); emails = _emails((await _body(request)).get("emails"))
    try: store.add_invites(cid, emails)
    except ValueError as e: raise ApiError(400, str(e))
    return _survey_status(cid, request)


@app.delete("/api/companies/{cid}/survey/invite/{token}")
def survey_uninvite(cid: str, token: str, request: Request):
    _company(cid)
    if not store.remove_invite(cid, token): raise ApiError(404, "no open invitation with that link (answered invitations are kept)")
    return _survey_status(cid, request)


@app.post("/api/companies/{cid}/survey/responses")
async def survey_paper_response(cid: str, request: Request):
    """A returned Word questionnaire, added as one more anonymous response."""
    _company(cid); answers, ratings = _clean_response(await _body(request), paper=True)
    try: store.add_response(cid, answers, ratings)
    except store.DuplicateResponse: raise ApiError(409, "this questionnaire has already been added")
    return _survey_status(cid, request)


@app.get("/api/survey/{token}")
def survey_form(token: str):
    """What a respondent sees: the questions and the company's name, nothing from the assessment itself."""
    f = store.find_invite(token)
    if not f: raise ApiError(404, "this assessment link is not valid or has been withdrawn")
    cid, inv = f; m = store.load_meta(cid)
    return {"company": m.get("name", ""), "period": m.get("period", ""), "responded": inv["responded"], "min": MIN_RESPONSES,
            "questions": [{"n": k, "dimension": d, "dimension_name": convert.FW["dimensions"][d], "text": q} for k, (d, _, q) in enumerate(convert.FW["questionnaire"], 1)]}


@app.post("/api/survey/{token}")
async def survey_submit(token: str, request: Request):
    f = store.find_invite(token)
    if not f: raise ApiError(404, "this assessment link is not valid or has been withdrawn")
    answers, ratings = _clean_response(await _body(request))
    try: store.add_response(f[0], answers, ratings, token)
    except store.DuplicateResponse: raise ApiError(409, "an identical response has already been received; change at least one answer")
    except KeyError: raise ApiError(404, "this assessment link is not valid or has been withdrawn")
    except ValueError: raise ApiError(409, "a response has already been received from this link")
    return {"ok": True}


@app.get("/api/jobs/{job_id}")
def job(job_id: str):
    j = jobs.get(job_id)
    if not j: raise ApiError(404, f"job '{job_id}' not found")
    return j.to_dict()


def _delete(cid: str) -> None:
    _idle(cid)
    try: store.delete(cid)
    except OSError as e: raise ApiError(409, f"the company's files are in use (OneDrive or another program); try again in a moment ({type(e).__name__})")


@app.delete("/api/companies/{cid}")
def delete(cid: str):
    _company(cid); _delete(cid)
    return {"ok": True, "id": cid}


@app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def api_404(rest: str):
    raise ApiError(404, f"no API route /api/{rest}")


# ---------------- static front end ----------------

@app.get("/")
def index():
    return FileResponse(os.path.join(ROOT, "index.html"), headers={"Cache-Control": "no-cache"})


for _d in ("css", "js", "assets", "dist"):
    if os.path.isdir(os.path.join(ROOT, _d)): app.mount(f"/{_d}", StaticFiles(directory=os.path.join(ROOT, _d)), name=_d)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "5173")))

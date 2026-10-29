"""Company / assessment routes: list, view, files, import, outside-in research, inside-out, jobs, delete."""
from __future__ import annotations

import copy
import re

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from app.api import survey as survey_api
from app.api.errors import ApiError, read_body, submit
from app.api.uploads import MAX_OI_DOCS, extract_documents
from app.domain import view as convert
from app.log import get_logger
from app.schemas import DeleteOut, ImportOut, JobOut, JobRef
from app.services import jobs, repo, runs

log = get_logger(__name__)
router = APIRouter()
FILE_KEYS = ("oi_docx", "oi_html", "io_docx", "io_html", "prior_docx", "quest")
PERIOD = re.compile(r"^\d{4}-Q[1-4]$")


def _company(cid: str) -> str:
    if not repo.exists(cid): raise ApiError(404, f"company '{cid}' not found")
    return cid


def _idle(cid: str) -> None:
    if j := jobs.active(cid): raise ApiError(409, "a job is running for this company", job_id=j.id)


@router.get("/api/companies")
def companies():
    out = []
    for c in repo.list_ids():
        try: out.append(repo.summary(c))
        except Exception as e:  # noqa: BLE001 - one unreadable company must not hide the rest
            log.warning("company_skipped_from_list", company=c, error=f"{type(e).__name__}: {e}")
    return out


@router.get("/api/companies/{cid}/view")
def view(cid: str, mode: str | None = None):
    _company(cid)
    if mode and mode not in convert.FW["run_modes"]: raise ApiError(400, f"mode must be one of {list(convert.FW['run_modes'])}")
    return repo.view(cid, mode)


@router.get("/api/companies/{cid}/files/{key}")
def file(cid: str, key: str):
    _company(cid)
    if key not in FILE_KEYS: raise ApiError(404, f"unknown file key '{key}' (one of {list(FILE_KEYS)})")
    p = repo.file_path(cid, key)
    if not p: raise ApiError(404, f"{key} has not been built for '{cid}'")
    # the dashboards are shown in an iframe, so they are served inline; attachment would make the browser download them instead.
    # no-cache so a browser that cached an earlier attachment response revalidates instead of downloading the file again.
    if p.suffix == ".html":
        return FileResponse(str(p), headers={"Content-Disposition": f'inline; filename="{p.name}"', "Cache-Control": "no-cache"})
    return FileResponse(str(p), filename=p.name)


# ---------------- import ----------------

def check_runs(oi, io, priors) -> list[str]:
    """Shape checks, then the rule check (engine.grade check=True) on each file. Returns blocking problems."""
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
    for label, r in [("outside_in", oi)] + ([("inside_out", io)] if io is not None else []) + [(f"prior {p['run'].get('period')}", p) for p in priors]:
        g = runs.grade(copy.deepcopy(r), check=True); probs += [f"{label}: {x}" for x in g["problems"]]
    return probs


def _delete(cid: str) -> None:
    _idle(cid)
    try: repo.delete_company(cid)
    except OSError as e: raise ApiError(409, f"the company's files are in use (OneDrive or another program); try again in a moment ({type(e).__name__})")


@router.post("/api/companies/import", response_model=ImportOut)
async def import_company(request: Request):
    b = await read_body(request)
    oi, io, priors = b.get("outside_in"), b.get("inside_out"), b.get("priors") or []
    if oi is None: raise ApiError(400, "outside_in run is required")
    if not isinstance(priors, list): raise ApiError(400, "priors must be a list of run files")
    probs = check_runs(oi, io, priors)
    if probs: raise ApiError(422, "the run files failed the rule check", probs)
    cid = convert.company_id(convert.company_of(oi))
    if repo.exists(cid):
        if not b.get("replace"): raise ApiError(409, f"company '{cid}' already exists; send replace: true to overwrite")
        _delete(cid)
    try: cid = repo.create(oi, io, priors, source="imported", cid=cid)
    except repo.StoreError as e: raise ApiError(409, str(e))
    return {"id": cid, "job_id": submit("import", runs.build_work(cid), cid).id}


# ---------------- outside-in research ----------------

@router.post("/api/research", response_model=JobRef)
async def research(request: Request):
    b = await read_body(request)
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
    provided, probs = extract_documents(docs)
    if probs: raise ApiError(400, "some documents could not be read", probs)
    st = runs.research_status()
    if not st["enabled"]: raise ApiError(503, "research is not available: " + st["reason"])
    peers = [{"name": p["name"].strip(), "ticker": (p.get("ticker") or "").strip()} for p in peers]

    pending = convert.slug(convert.short_name(company), ticker)
    mid = repo.match_id(pending, company, ticker)
    try:
        if mid: repo.check_period(mid, period)
    except ValueError as e: raise ApiError(409, str(e))
    return {"job_id": submit("research", runs.research_work(company, ticker, peers, period, mode, provided), mid or pending).id}


# ---------------- inside-out ----------------

@router.post("/api/companies/{cid}/inside-out", response_model=JobRef)
async def inside_out(cid: str, request: Request):
    _company(cid); _idle(cid)
    b = await read_body(request)
    meta = repo.load_meta(cid)
    mode = b.get("mode") or meta.get("mode") or "director_request"
    docs = b.get("documents") or []
    probs = []
    if mode not in convert.FW["run_modes"]: probs.append(f"mode must be one of {list(convert.FW['run_modes'])}")
    if not isinstance(docs, list): probs.append("documents must be a list")
    if probs: raise ApiError(400, "invalid inside-out request", probs)
    nd = len(convert.FW["inside_out_priority_docs"])
    s = repo.load_survey(cid); n = len(s["responses"]); answers, ratings = survey_api.combine(s["responses"])
    extracted, probs = extract_documents(docs, max_slot=nd)
    if probs: raise ApiError(400, "some documents could not be read", probs)
    ok, why = survey_api.can_generate(n, s.get("used"))
    if not ok: raise ApiError(409, why)
    if n == 0 and not extracted: raise ApiError(409, "add board documents or collect self-assessment responses")
    st = runs.research_status()
    if not st["enabled"]: raise ApiError(503, "research is not available: " + st["reason"])
    return {"job_id": submit("inside_out", runs.inside_out_work(cid, mode, extracted, answers, ratings, n), cid).id}


# ---------------- jobs and delete ----------------

@router.get("/api/jobs/{job_id}", response_model=JobOut)
def job(job_id: str):
    j = jobs.get(job_id)
    if not j: raise ApiError(404, f"job '{job_id}' not found")
    return j.to_dict()


@router.delete("/api/companies/{cid}", response_model=DeleteOut)
def delete(cid: str):
    _company(cid); _delete(cid)
    return {"ok": True, "id": cid}

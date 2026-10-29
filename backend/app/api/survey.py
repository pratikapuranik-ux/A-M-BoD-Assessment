"""Board self-assessment (anonymous survey) routes and the anonymity guardrail."""
from __future__ import annotations

import os
import random
import re
from urllib.parse import urlsplit

from fastapi import APIRouter, Request

from app.api.errors import ApiError, read_body
from app.config import get_settings
from app.domain import view as convert
from app.schemas import OkOut, SurveyStatusOut
from app.services import repo

router = APIRouter()
EMAIL = re.compile(r"^[^@\s<>\"']+@[^@\s<>\"']+\.[^@\s<>\"']*[^@\s<>\"'.]$")
NAMED_EMAIL = re.compile(r"^[^<>]*<([^<>]*)>$")  # "Name <addr>"
MAX_EMAILS = 50  # per request; repo.MAX_INVITES per survey
CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def min_responses() -> int:
    """Anonymity guardrail: the inside-out view is prepared only once this many people have responded (default 3)."""
    return get_settings().min_responses


def combine(rs: list[dict]) -> tuple[dict, dict]:
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


def can_generate(n: int, used: int | None) -> tuple[bool, str | None]:
    """Anonymity: at least MIN_RESPONSES, and a refresh only on the same responses or MIN_RESPONSES more (differencing)."""
    m = min_responses()
    if n < m:
        return False, f"{n} of {m} self-assessment responses received. To keep responses anonymous, the inside-out view is prepared only once at least {m} people have responded."
    if used is None or n == used or n - used >= m: return True, None
    k = m - (n - used)
    return False, f"Wait for {k} more response{'s' if k != 1 else ''} before refreshing the inside-out view, so a single new response cannot be singled out"


def _base_url(request: Request) -> str:
    pub = (os.environ.get("BOARD_PUBLIC_URL") or os.environ.get("NEXUS_PUBLIC_URL") or "").strip().rstrip("/")
    return pub + "/" if pub else str(request.base_url)


def status(cid: str, request: Request) -> dict:
    s = repo.load_survey(cid); base = _base_url(request); n = len(s["responses"]); ok, why = can_generate(n, s.get("used"))
    return {"invites": [{"token": i["token"], "email": i["email"], "created": i["created"], "responded": i["responded"], "link": f"{base}?take={i['token']}"} for i in s["invites"]],
            "responses": n, "count": n, "min": min_responses(), "can_generate": ok, "reason": why, "local": urlsplit(base).hostname in LOCAL_HOSTS}


def clean_response(b: dict, paper: bool = False) -> tuple[dict, dict]:
    nq = len(convert.FW["questionnaire"]); a, r = b.get("answers") or {}, b.get("ratings") or {}
    if not isinstance(a, dict) or not isinstance(r, dict): raise ApiError(400, "answers and ratings must be objects")
    answers = {str(k): CTRL.sub("", str(a.get(str(k)) or "")).strip()[:4000] for k in range(1, nq + 1)}
    ratings = {str(d): v for d, v in r.items() if str(d) in convert.DIMS and type(v) is int and v in (1, 2, 3, 4, 5)}
    if paper and not any(answers.values()) and not ratings: raise ApiError(400, "the questionnaire has no answers or ratings")
    if not paper and not any(answers.values()): raise ApiError(400, "answer at least one question")
    return answers, ratings


def clean_emails(raw) -> list[str]:
    if not isinstance(raw, list) or not all(isinstance(e, str) for e in raw): raise ApiError(400, "emails must be a list of strings")
    out = [(m.group(1) if (m := NAMED_EMAIL.match(e.strip())) else e).strip() for e in raw if e.strip()]
    if not out: raise ApiError(400, "give at least one email address")
    if len(out) > MAX_EMAILS: raise ApiError(400, f"at most {MAX_EMAILS} email addresses at a time")
    if bad := [e for e in out if len(e) > 254 or not EMAIL.match(e)]: raise ApiError(400, "not an email address", [e[:80] for e in bad[:20]])
    return out


def _company(cid: str) -> str:
    if not repo.exists(cid): raise ApiError(404, f"company '{cid}' not found")
    return cid


@router.get("/api/companies/{cid}/survey", response_model=SurveyStatusOut)
def survey_status(cid: str, request: Request):
    return status(_company(cid), request)


@router.post("/api/companies/{cid}/survey/invite", response_model=SurveyStatusOut)
async def survey_invite(cid: str, request: Request):
    _company(cid); emails = clean_emails((await read_body(request)).get("emails"))
    try: repo.add_invites(cid, emails)
    except ValueError as e: raise ApiError(400, str(e))
    return status(cid, request)


@router.delete("/api/companies/{cid}/survey/invite/{token}", response_model=SurveyStatusOut)
def survey_uninvite(cid: str, token: str, request: Request):
    _company(cid)
    if not repo.remove_invite(cid, token): raise ApiError(404, "no open invitation with that link (answered invitations are kept)")
    return status(cid, request)


@router.post("/api/companies/{cid}/survey/responses", response_model=SurveyStatusOut)
async def survey_paper_response(cid: str, request: Request):
    """A returned Word questionnaire, added as one more anonymous response."""
    _company(cid); answers, ratings = clean_response(await read_body(request), paper=True)
    try: repo.add_response(cid, answers, ratings)
    except repo.DuplicateResponse: raise ApiError(409, "this questionnaire has already been added")
    return status(cid, request)


@router.get("/api/survey/{token}")
def survey_form(token: str):
    """What a respondent sees: the questions and the company's name, nothing from the assessment itself."""
    f = repo.find_invite(token)
    if not f: raise ApiError(404, "this assessment link is not valid or has been withdrawn")
    cid, inv = f; m = repo.load_meta(cid)
    return {"company": m.get("name", ""), "period": m.get("period", ""), "responded": inv["responded"], "min": min_responses(),
            "questions": [{"n": k, "dimension": d, "dimension_name": convert.FW["dimensions"][d], "text": q} for k, (d, _, q) in enumerate(convert.FW["questionnaire"], 1)]}


@router.post("/api/survey/{token}", response_model=OkOut)
async def survey_submit(token: str, request: Request):
    f = repo.find_invite(token)
    if not f: raise ApiError(404, "this assessment link is not valid or has been withdrawn")
    answers, ratings = clean_response(await read_body(request))
    try: repo.add_response(f[0], answers, ratings, token)
    except repo.DuplicateResponse: raise ApiError(409, "an identical response has already been received; change at least one answer")
    except KeyError: raise ApiError(404, "this assessment link is not valid or has been withdrawn")
    except ValueError: raise ApiError(409, "a response has already been received from this link")
    return {"ok": True}

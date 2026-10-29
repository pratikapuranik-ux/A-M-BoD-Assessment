"""Persistence (replaces server/store.py): companies, stage runs, prior runs, survey, deliverable records.

Same semantics as the JSON file store: per-company locking, unique ids, period checks, backup/restore of a same-period
refresh, anonymous survey with duplicate hashes and a usage counter. Binary files live under services.storage.
"""
from __future__ import annotations

import copy
import hashlib
import json
import random
import re
import secrets
import threading
import time
from typing import Any

from sqlalchemy import delete, func, select, update

from app.db import session_scope
from app.domain import view as convert
from app.log import get_logger
from app.models import Company, Deliverable, PriorRun, StageRun, SurveyHash, SurveyInvite, SurveyResponse
from app.services import storage
from app.services.storage import StoreError, valid_id  # noqa: F401 - re-exported

log = get_logger(__name__)
STAGES = ("outside_in", "inside_out")
MAX_INVITES = 200
_locks: dict[str, threading.RLock] = {}
_glock = threading.Lock()
_idlock = threading.Lock()


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def lock(cid: str) -> threading.RLock:
    with _glock:
        return _locks.setdefault(cid, threading.RLock())


def subj_short(s: dict) -> str:
    return s.get("short") or convert.short_name(s.get("name", ""))


def _overall(s: dict, lens: str = "board") -> dict:
    return ((s.get("computed") or {}).get("overall") or {}).get(lens) or {}


def _period(run: dict | None) -> str:
    return str(((run or {}).get("run") or {}).get("period") or "")


def _prior_key(run: dict) -> str:
    return re.sub(r"[^A-Za-z0-9-]+", "_", str(run.get("run", {}).get("period") or "unknown"))


# ---------------- companies ----------------

def exists(cid: str) -> bool:
    if not valid_id(cid):
        return False
    with session_scope() as s:
        return s.get(Company, cid) is not None


def list_ids() -> list[str]:
    with session_scope() as s:
        return sorted(s.scalars(select(Company.id)))


def _meta(c: Company, files: dict[str, str]) -> dict:
    m = {"id": c.id, "name": c.name, "short": c.short, "ticker": c.ticker, "period": c.period, "mode": c.mode, "source": c.source,
         "created": c.created, "files": files}
    if c.updated: m["updated"] = c.updated
    if c.problems is not None: m["problems"] = list(c.problems)
    return m


def _files(s, cid: str) -> dict[str, str]:
    return {d.key: d.filename for d in s.scalars(select(Deliverable).where(Deliverable.company_id == cid).order_by(Deliverable.id))}


def load_meta(cid: str) -> dict:
    if not valid_id(cid):
        raise KeyError(cid)
    with session_scope() as s:
        c = s.get(Company, cid)
        if c is None:
            raise KeyError(cid)
        return _meta(c, _files(s, cid))


def save_meta(cid: str, meta: dict) -> None:
    """Replace the editable fields; 'problems' absent means cleared. Files are managed by record_file()."""
    with session_scope() as s:
        c = s.get(Company, cid)
        if c is None:
            raise KeyError(cid)
        for k in ("name", "short", "ticker", "period", "mode", "source", "created"):
            if k in meta: setattr(c, k, meta[k] or "")
        c.problems = meta.get("problems")
        c.updated = now()


def set_problems(cid: str, problems: list | None) -> None:
    with lock(cid):
        m = load_meta(cid)
        m.pop("problems", None)
        if problems: m["problems"] = list(problems)
        save_meta(cid, m)


def _stage_row(s, cid: str, stage: str) -> StageRun | None:
    return s.scalar(select(StageRun).where(StageRun.company_id == cid, StageRun.stage == stage))


def read_run(cid: str, stage: str) -> dict | None:
    with session_scope() as s:
        r = _stage_row(s, cid, stage)
        return copy.deepcopy(r.run) if r else None


def write_run(cid: str, stage: str, run: dict, keep_prev: bool = False) -> None:
    with session_scope() as s:
        r = _stage_row(s, cid, stage)
        if r is None:
            s.add(StageRun(company_id=cid, stage=stage, period=_period(run), run=run))
        else:
            if keep_prev: r.prev_run = r.run
            r.run = run; r.period = _period(run)


def delete_run(cid: str, stage: str) -> None:
    with session_scope() as s:
        s.execute(delete(StageRun).where(StageRun.company_id == cid, StageRun.stage == stage))


def priors(cid: str) -> list[dict]:
    """Prior run files, oldest period first."""
    with session_scope() as s:
        return [copy.deepcopy(p.run) for p in s.scalars(select(PriorRun).where(PriorRun.company_id == cid).order_by(PriorRun.period))]


def write_prior(cid: str, run: dict) -> str:
    key = _prior_key(run)
    with session_scope() as s:
        p = s.scalar(select(PriorRun).where(PriorRun.company_id == cid, PriorRun.period == key))
        if p is None: s.add(PriorRun(company_id=cid, period=key, run=run))
        else: p.run = run
    return key


def latest_prior(cid: str) -> dict | None:
    ps = priors(cid)
    return ps[-1] if ps else None


# ---------------- deliverable files ----------------

def file_path(cid: str, key: str):
    with session_scope() as s:
        d = s.scalar(select(Deliverable).where(Deliverable.company_id == cid, Deliverable.key == key))
        name = d.filename if d else None
    return storage.deliverable_path(cid, name) if name else None


def file_urls(cid: str, meta: dict | None = None) -> dict:
    files = (meta or load_meta(cid)).get("files") or {}
    return {k: f"/api/companies/{cid}/files/{k}" for k, n in files.items() if storage.deliverable_path(cid, n)}


def record_file(cid: str, key: str, filename: str) -> None:
    p = storage.deliverable_path(cid, filename)
    with session_scope() as s:
        d = s.scalar(select(Deliverable).where(Deliverable.company_id == cid, Deliverable.key == key))
        if d is None: s.add(Deliverable(company_id=cid, key=key, filename=filename, size=p.stat().st_size if p else 0, created=now()))
        else: d.filename = filename; d.size = p.stat().st_size if p else 0; d.created = now()


def drop_file_record(cid: str, key: str) -> None:
    with session_scope() as s:
        s.execute(delete(Deliverable).where(Deliverable.company_id == cid, Deliverable.key == key))


# ---------------- ids ----------------

def unique_id(base: str) -> str:
    base = convert.slug(base); cid, n = base, 2
    while exists(cid):
        cid = f"{base}-{n}"; n += 1
    return cid


def _same(meta: dict, name: str, ticker: str) -> bool:
    return (meta.get("name") or "").casefold() == (name or "").casefold() and (meta.get("ticker") or "").casefold() == (ticker or "").casefold()


def match_id(base: str, name: str, ticker: str) -> str | None:
    """The id of the company on file under base (base, base-2, ...) with this name and ticker, else None."""
    cid, n = convert.slug(base), 2
    while exists(cid):
        if _same(load_meta(cid), name, ticker): return cid
        cid = f"{convert.slug(base)}-{n}"; n += 1
    return None


# ---------------- create / delete / view ----------------

def _purge_rows(s, cid: str) -> None:
    for t in (StageRun, PriorRun, SurveyInvite, SurveyResponse, SurveyHash, Deliverable):
        s.execute(delete(t).where(t.company_id == cid))
    s.execute(delete(Company).where(Company.id == cid))


def create(oi: dict, io: dict | None = None, priors_: list[dict] | None = None, source: str = "imported", cid: str | None = None) -> str:
    comp = convert.company_of(oi)
    with _idlock:
        cid = cid or unique_id(convert.company_id(comp))
        with lock(cid):
            if not valid_id(cid): raise KeyError(cid)
            if not exists(cid): storage.clear_leftovers(cid)
            storage.ensure_out(cid)
            with session_scope() as s:
                _purge_rows(s, cid)
                s.flush()
                r = oi.get("run", {})
                s.add(Company(id=cid, name=comp["name"], short=subj_short(comp), ticker=comp.get("ticker", ""), period=r.get("period", ""),
                              mode=r.get("mode", ""), source=source, created=now(), updated=now()))
                s.flush()
                s.add(StageRun(company_id=cid, stage="outside_in", period=_period(oi), run=oi))
                if io: s.add(StageRun(company_id=cid, stage="inside_out", period=_period(io), run=io))
                for p in priors_ or []:
                    s.add(PriorRun(company_id=cid, period=_prior_key(p), run=p))
    return cid


def delete_company(cid: str) -> None:
    """Rows first (the company leaves the list, answers go), then the files, even if OneDrive holds them briefly."""
    with lock(cid):
        with session_scope() as s:
            _purge_rows(s, cid)
        storage.remove_company(cid)


def view(cid: str, mode: str | None = None) -> dict:
    with lock(cid):
        meta = load_meta(cid); oi = read_run(cid, "outside_in"); io = read_run(cid, "inside_out"); ps = priors(cid)
    m = dict(meta, files=file_urls(cid, meta))
    if mode: m["mode"] = mode
    v = convert.to_view(oi, io, ps[-1] if ps else None, m, ps)
    # grades are computed here, never in the browser: the report reads `model` (current and peer grades) and `history` (trend)
    from app.domain import engine
    v["model"] = engine.model(v)
    v["history"] = engine.build_history(v.get("priors") or [], [p["period"] for p in v.get("priors") or []], v["meta"].get("period"), keep=4)
    return v


def check_period(cid: str, period: str) -> None:
    """ValueError unless `period` is the current one or later than every assessment on file."""
    with lock(cid):
        have = [_period(read_run(cid, "outside_in"))] + [_period(p) for p in priors(cid)]
    if late := sorted(p for p in have if p and period < p):
        raise ValueError(f"{period} is earlier than the {late[-1]} assessment on file; choose {late[-1]} to refresh it, or a later period")


def _clear_survey(s, cid: str) -> None:
    for t in (SurveyInvite, SurveyResponse, SurveyHash):
        s.execute(delete(t).where(t.company_id == cid))
    s.execute(update(Company).where(Company.id == cid).values(survey_used=None))


def new_period(cid: str, oi: dict, source: str = "research") -> dict | None:
    """A fresh outside-in run for a company already on file. For a later period the current assessment (inside-out where
    one was run, else outside-in) is kept as an earlier quarter, the old inside-out is set aside and the survey is deleted.
    For the same period only the outside-in run is replaced; the returned backup lets restore() put it back.
    Raises ValueError for a period earlier than the current one or than any prior on file."""
    with lock(cid):
        check_period(cid, _period(oi))
        cur_oi, cur_io = read_run(cid, "outside_in"), read_run(cid, "inside_out")
        new, cur = _period(oi), _period(cur_oi)
        meta = load_meta(cid); backup = None
        if cur_oi and new == cur:
            backup = {"outside_in": cur_oi, "meta": dict(meta)}
        else:
            if cur_oi: write_prior(cid, cur_io or cur_oi)
            with session_scope() as s:
                if cur_io: s.execute(delete(StageRun).where(StageRun.company_id == cid, StageRun.stage == "inside_out"))
                _clear_survey(s, cid)  # a new quarter, a new survey
        write_run(cid, "outside_in", oi)
        meta.pop("problems", None)
        meta.update(period=new, mode=oi.get("run", {}).get("mode", ""), source=source); save_meta(cid, meta)
    return backup


def restore(cid: str, backup: dict) -> None:
    """Undo a same-period new_period()."""
    with lock(cid):
        write_run(cid, "outside_in", backup["outside_in"]); save_meta(cid, backup["meta"])


def summary(cid: str) -> dict:
    with lock(cid):
        meta = load_meta(cid); oi = read_run(cid, "outside_in") or {}; io = read_run(cid, "inside_out"); prior = latest_prior(cid)
    comp = convert.company_of(oi); ov = _overall(comp)
    iov = _overall(convert.company_of(io), "board_io") if io else {}
    hist = oi.get("history") or []
    prior_period = (prior or {}).get("run", {}).get("period") or (hist[-1]["period"] if hist else None)
    return {"id": cid, "name": comp["name"], "short": subj_short(comp), "ticker": comp.get("ticker", ""), "period": oi.get("run", {}).get("period", ""),
            "peers": [subj_short(p) for p in convert.peers_of(oi)], "stages": {"outside_in": True, "inside_out": bool(io)},
            "grades": {"oi": ov.get("grade"), "io": iov.get("grade")}, "labels": {"oi": ov.get("label"), "io": iov.get("label")},
            "avg": {"oi": ov.get("numeric_average"), "io": iov.get("numeric_average")},
            "has_prior": bool(prior_period), "prior_period": prior_period,
            "source": meta.get("source", "imported"), "mode": meta.get("mode", ""), "updated": meta.get("updated"), "files": file_urls(cid, meta),
            "problems": meta.get("problems", [])}


# ---------------- board self-assessment (anonymous survey) ----------------
# Responses carry no token, email or time and sit at a random position, so none can be traced to an invitation; the hashes
# (for refusing duplicates) are a set kept apart from the responses.

class DuplicateResponse(Exception):
    pass


def load_survey(cid: str) -> dict:
    with lock(cid), session_scope() as s:
        invites = [{"token": i.token, "email": i.email, "created": i.created, "responded": i.responded}
                   for i in s.scalars(select(SurveyInvite).where(SurveyInvite.company_id == cid).order_by(SurveyInvite.seq))]
        responses = [{"answers": r.answers, "ratings": r.ratings}
                     for r in s.scalars(select(SurveyResponse).where(SurveyResponse.company_id == cid).order_by(SurveyResponse.position, SurveyResponse.id))]
        out: dict[str, Any] = {"invites": invites, "responses": responses}
        hashes = sorted(s.scalars(select(SurveyHash.hash).where(SurveyHash.company_id == cid)))
        if hashes: out["hashes"] = hashes
        used = s.scalar(select(Company.survey_used).where(Company.id == cid))
        if used is not None: out["used"] = used
        return out


def add_invites(cid: str, emails: list[str]) -> list[dict]:
    with lock(cid), session_scope() as s:
        rows = list(s.scalars(select(SurveyInvite).where(SurveyInvite.company_id == cid)))
        have = {i.email.lower() for i in rows}; seq = max((i.seq for i in rows), default=0); new = []
        for e in emails:
            if e.lower() in have: continue
            seq += 1
            inv = SurveyInvite(token=secrets.token_urlsafe(18), company_id=cid, seq=seq, email=e, created=time.strftime("%Y-%m-%d"), responded=False)
            s.add(inv); new.append({"token": inv.token, "email": e, "created": inv.created, "responded": False}); have.add(e.lower())
        if len(rows) + len(new) > MAX_INVITES:
            raise ValueError(f"at most {MAX_INVITES} invitations per survey ({len(rows)} already sent)")  # rolled back by session_scope
        return new


def remove_invite(cid: str, token: str) -> bool:
    with lock(cid), session_scope() as s:
        r = s.execute(delete(SurveyInvite).where(SurveyInvite.company_id == cid, SurveyInvite.token == token, SurveyInvite.responded.is_(False)))
        return bool(r.rowcount)


def find_invite(token: str) -> tuple[str, dict] | None:
    with session_scope() as s:
        i = s.get(SurveyInvite, token)
        return (i.company_id, {"token": i.token, "email": i.email, "created": i.created, "responded": i.responded}) if i else None


def response_hash(answers: dict, ratings: dict) -> str:
    a = {str(k): " ".join(str(v).split()).casefold() for k, v in answers.items() if str(v).strip()}
    return hashlib.sha256(json.dumps({"a": a, "r": {str(k): v for k, v in ratings.items()}}, sort_keys=True).encode()).hexdigest()


def add_response(cid: str, answers: dict, ratings: dict, token: str | None = None) -> None:
    """Store one anonymous response. With a token, the invitation is marked as used (it cannot answer twice).
    Raises DuplicateResponse for a response identical to one already stored; KeyError for an unknown token; ValueError if used."""
    with lock(cid), session_scope() as s:
        inv = None
        if token:
            inv = s.scalar(select(SurveyInvite).where(SurveyInvite.token == token, SurveyInvite.company_id == cid))
            if inv is None: raise KeyError(token)
            if inv.responded: raise ValueError("already responded")
        h = response_hash(answers, ratings)
        if s.get(SurveyHash, (cid, h)) is not None: raise DuplicateResponse(h)
        if inv: inv.responded = True
        s.add(SurveyHash(company_id=cid, hash=h))
        s.add(SurveyResponse(company_id=cid, position=random.random(), answers=answers, ratings=ratings))


def response_ids(cid: str) -> list[int]:
    """Ids of the stored responses in their (random) stored order, so a list position says nothing about who answered when."""
    with session_scope() as s:
        return list(s.scalars(select(SurveyResponse.id).where(SurveyResponse.company_id == cid).order_by(SurveyResponse.position, SurveyResponse.id)))


def remove_response(cid: str, rid: int) -> bool:
    """Delete one anonymous response and its duplicate-check hash (so the same answers can be added again). The invitation
    it came from is not touched: a response carries no link to one."""
    with lock(cid), session_scope() as s:
        r = s.scalar(select(SurveyResponse).where(SurveyResponse.id == rid, SurveyResponse.company_id == cid))
        if r is None: return False
        h = s.get(SurveyHash, (cid, response_hash(r.answers, r.ratings)))
        if h is not None: s.delete(h)
        s.delete(r)
        return True


def set_used(cid: str, n: int) -> None:
    """Record how many responses the inside-out run on file used."""
    with lock(cid), session_scope() as s:
        s.execute(update(Company).where(Company.id == cid).values(survey_used=n))


def response_count(cid: str) -> int:
    with session_scope() as s:
        return s.scalar(select(func.count()).select_from(SurveyResponse).where(SurveyResponse.company_id == cid)) or 0

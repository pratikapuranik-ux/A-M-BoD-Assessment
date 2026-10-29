"""Companies on disk: <BOARD_DATA_DIR or ./data>/companies/<id>/{meta.json, outside_in_run.json, inside_out_run.json?, prior_<period>.json*, out/}."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import threading
import time
import uuid
from typing import Any

import convert

ROOT = convert.ROOT
STAGE_FILE = {"outside_in": "outside_in_run.json", "inside_out": "inside_out_run.json"}
_locks: dict[str, threading.RLock] = {}
_glock = threading.Lock()


def data_dir() -> str:
    return os.environ.get("BOARD_DATA_DIR") or os.path.join(ROOT, "data")


def companies_dir() -> str:
    return os.path.join(data_dir(), "companies")


def valid_id(cid: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", cid or ""))


def company_dir(cid: str) -> str:
    if not valid_id(cid): raise KeyError(cid)
    return os.path.join(companies_dir(), cid)


def out_dir(cid: str) -> str:
    return os.path.join(company_dir(cid), "out")


def run_path(cid: str, stage: str) -> str:
    return os.path.join(company_dir(cid), STAGE_FILE[stage])


def lock(cid: str) -> threading.RLock:
    with _glock: return _locks.setdefault(cid, threading.RLock())


def exists(cid: str) -> bool:
    return valid_id(cid) and os.path.exists(os.path.join(company_dir(cid), "meta.json"))


def list_ids() -> list[str]:
    d = companies_dir()
    return sorted(x for x in os.listdir(d) if exists(x)) if os.path.isdir(d) else []


class StoreError(RuntimeError):
    """A company's files could not be changed; the message is fit to show the user."""


def _read(path: str) -> Any:
    with open(path, encoding="utf-8") as f: return json.load(f)


def _retry(fn, *args, tries: int = 10, wait: float = 0.2):
    """fn(*args), retried while OneDrive, a virus scanner or a reader briefly holds the file (Windows)."""
    for i in range(tries):
        try: return fn(*args)
        except FileNotFoundError: raise
        except OSError:
            if i == tries - 1: raise
            time.sleep(wait)


def _write(path: str, obj: Any) -> None:
    tmp = os.path.join(os.path.dirname(path), f"~{uuid.uuid4().hex[:10]}.tmp")  # unique per writer, and short (Windows MAX_PATH)
    try:
        with open(tmp, "w", encoding="utf-8") as f: json.dump(obj, f, indent=1)  # ASCII-escaped, safe for the skill scripts
        _retry(os.replace, tmp, path)
    finally:
        if os.path.exists(tmp): os.remove(tmp)


def _remove(path: str) -> None:
    try: _retry(os.remove, path)
    except FileNotFoundError: pass


def load_meta(cid: str) -> dict:
    return _read(os.path.join(company_dir(cid), "meta.json"))


def save_meta(cid: str, meta: dict) -> None:
    meta["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S"); _write(os.path.join(company_dir(cid), "meta.json"), meta)


def read_run(cid: str, stage: str) -> dict | None:
    p = run_path(cid, stage)
    return _read(p) if os.path.exists(p) else None


def write_run(cid: str, stage: str, run: dict) -> None:
    _write(run_path(cid, stage), run)


def prior_paths(cid: str) -> list[str]:
    d = company_dir(cid)
    return sorted(os.path.join(d, f) for f in os.listdir(d) if re.fullmatch(r"prior_.+\.json", f))


def write_prior(cid: str, run: dict) -> str:
    period = re.sub(r"[^A-Za-z0-9-]+", "_", str(run.get("run", {}).get("period") or "unknown"))
    p = os.path.join(company_dir(cid), f"prior_{period}.json"); _write(p, run); return p


def latest_prior(cid: str) -> dict | None:
    ps = prior_paths(cid)
    return _read(ps[-1]) if ps else None


def file_path(cid: str, key: str) -> str | None:
    name = (load_meta(cid).get("files") or {}).get(key)
    p = os.path.join(out_dir(cid), name) if name else None
    return p if p and os.path.exists(p) else None


def file_urls(cid: str, meta: dict | None = None) -> dict:
    meta = meta or load_meta(cid)
    return {k: f"/api/companies/{cid}/files/{k}" for k, n in (meta.get("files") or {}).items() if os.path.exists(os.path.join(out_dir(cid), n))}


_idlock = threading.Lock()


def unique_id(base: str) -> str:
    base = convert.slug(base); cid, n = base, 2
    while exists(cid): cid = f"{base}-{n}"; n += 1
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


def _rmtree(d: str) -> bool:
    """Remove a folder, retrying while OneDrive or a virus scanner briefly holds it. True if it is gone."""
    for i in range(6):
        try: shutil.rmtree(d); return True
        except FileNotFoundError: return True
        except OSError: time.sleep(0.4 * (i + 1))
    shutil.rmtree(d, ignore_errors=True)
    return not os.path.exists(d)


def _clear(cid: str) -> None:
    """Leftovers of a deleted company are removed, else moved aside to <id>.deleted-<time> (never listed); never adopted."""
    d = company_dir(cid)
    if not os.path.isdir(d) or _rmtree(d): return
    try: os.rename(d, f"{d}.deleted-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}")
    except OSError as e: raise StoreError(f"the folder left by a deleted company '{cid}' is still in use (OneDrive or another program); close it and try again") from e


def create(oi: dict, io: dict | None = None, priors: list[dict] | None = None, source: str = "imported", cid: str | None = None) -> str:
    comp = convert.company_of(oi)
    with _idlock:
        cid = cid or unique_id(convert.company_id(comp))
        with lock(cid):
            if not exists(cid): _clear(cid)
            os.makedirs(os.path.join(company_dir(cid), "out"), exist_ok=True)
            write_run(cid, "outside_in", oi)
            if io: write_run(cid, "inside_out", io)
            for p in priors or []: write_prior(cid, p)
            save_meta(cid, {"id": cid, "name": comp["name"], "short": convert.subj_short(comp), "ticker": comp.get("ticker", ""),
                            "period": oi.get("run", {}).get("period", ""), "mode": oi.get("run", {}).get("mode", ""), "source": source,
                            "created": time.strftime("%Y-%m-%dT%H:%M:%S"), "files": {}})
    return cid


def delete(cid: str) -> None:
    """The answers go first, then meta.json (the company leaves the list); the folder follows, even if OneDrive holds it briefly."""
    with lock(cid):
        d = company_dir(cid)
        for f in ("survey.json", "survey.prev.json", "meta.json"): _remove(os.path.join(d, f))
        if not _rmtree(d): logging.getLogger(__name__).warning("could not remove all of %s; it is cleared on next use", d)


def view(cid: str, mode: str | None = None) -> dict:
    with lock(cid):
        meta = load_meta(cid); oi = read_run(cid, "outside_in"); io = read_run(cid, "inside_out"); priors = [_read(p) for p in prior_paths(cid)]
    m = dict(meta, files=file_urls(cid, meta))
    if mode: m["mode"] = mode
    return convert.to_view(oi, io, priors[-1] if priors else None, m, priors)


def _period(run: dict | None) -> str:
    return str(((run or {}).get("run") or {}).get("period") or "")


def check_period(cid: str, period: str) -> None:
    """ValueError unless `period` is the current one or later than every assessment on file."""
    with lock(cid):
        have = [_period(read_run(cid, "outside_in"))] + [_period(_read(x)) for x in prior_paths(cid)]
    if late := sorted(p for p in have if p and period < p):
        raise ValueError(f"{period} is earlier than the {late[-1]} assessment on file; choose {late[-1]} to refresh it, or a later period")


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
            if cur_io: _retry(os.replace, run_path(cid, "inside_out"), run_path(cid, "inside_out").replace(".json", ".prev.json"))
            for p in (survey_path(cid), survey_path(cid).replace(".json", ".prev.json")): _remove(p)  # a new quarter, a new survey
        write_run(cid, "outside_in", oi)
        meta.pop("problems", None)
        meta.update(period=new, mode=oi.get("run", {}).get("mode", ""), source=source); save_meta(cid, meta)
    return backup


def restore(cid: str, backup: dict) -> None:
    """Undo a same-period new_period()."""
    with lock(cid):
        write_run(cid, "outside_in", backup["outside_in"]); _write(os.path.join(company_dir(cid), "meta.json"), backup["meta"])


def summary(cid: str) -> dict:
    with lock(cid):
        meta = load_meta(cid); oi = read_run(cid, "outside_in") or {}; io = read_run(cid, "inside_out")
        ps = prior_paths(cid); prior = _read(ps[-1]) if ps else None
    comp = convert.company_of(oi); ov = convert._overall(comp)
    iov = convert._overall(convert.company_of(io), "board_io") if io else {}
    hist = oi.get("history") or []
    prior_period = (prior or {}).get("run", {}).get("period") or (hist[-1]["period"] if hist else None)
    return {"id": cid, "name": comp["name"], "short": convert.subj_short(comp), "ticker": comp.get("ticker", ""), "period": oi.get("run", {}).get("period", ""),
            "peers": [convert.subj_short(p) for p in convert.peers_of(oi)], "stages": {"outside_in": True, "inside_out": bool(io)},
            "grades": {"oi": ov.get("grade"), "io": iov.get("grade")}, "labels": {"oi": ov.get("label"), "io": iov.get("label")},
            "avg": {"oi": ov.get("numeric_average"), "io": iov.get("numeric_average")},
            "has_prior": bool(prior_period), "prior_period": prior_period,
            "source": meta.get("source", "imported"), "mode": meta.get("mode", ""), "updated": meta.get("updated"), "files": file_urls(cid, meta),
            "problems": meta.get("problems", [])}


# ---------------- board self-assessment (anonymous survey) ----------------
# survey.json: {"invites": [{"token", "email", "created", "responded"}], "responses": [{"answers", "ratings"}],
#               "hashes": [sha256 of each response, sorted], "used": responses the last inside-out run used}.
# Responses carry no token, email or time and are inserted at a random position, so none can be traced to an invitation;
# the hashes (for refusing duplicates) are a sorted set kept apart from the responses.
MAX_INVITES = 200


class DuplicateResponse(Exception):
    pass


def survey_path(cid: str) -> str:
    return os.path.join(company_dir(cid), "survey.json")


def load_survey(cid: str) -> dict:
    with lock(cid):
        p = survey_path(cid)
        return _read(p) if os.path.exists(p) else {"invites": [], "responses": []}


def add_invites(cid: str, emails: list[str]) -> list[dict]:
    import secrets
    with lock(cid):
        s = load_survey(cid); have = {i["email"].lower() for i in s["invites"]}; new = []
        for e in emails:
            if e.lower() in have: continue
            inv = {"token": secrets.token_urlsafe(18), "email": e, "created": time.strftime("%Y-%m-%d"), "responded": False}
            s["invites"].append(inv); new.append(inv); have.add(e.lower())
        if len(s["invites"]) > MAX_INVITES: raise ValueError(f"at most {MAX_INVITES} invitations per survey ({len(s['invites']) - len(new)} already sent)")
        _write(survey_path(cid), s)
    return new


def remove_invite(cid: str, token: str) -> bool:
    with lock(cid):
        s = load_survey(cid); n = len(s["invites"])
        s["invites"] = [i for i in s["invites"] if not (i["token"] == token and not i["responded"])]
        _write(survey_path(cid), s)
    return len(s["invites"]) < n


def find_invite(token: str) -> tuple[str, dict] | None:
    for cid in list_ids():
        for i in load_survey(cid)["invites"]:
            if i["token"] == token: return cid, i
    return None


def response_hash(answers: dict, ratings: dict) -> str:
    a = {str(k): " ".join(str(v).split()).casefold() for k, v in answers.items() if str(v).strip()}
    return hashlib.sha256(json.dumps({"a": a, "r": {str(k): v for k, v in ratings.items()}}, sort_keys=True).encode()).hexdigest()


def add_response(cid: str, answers: dict, ratings: dict, token: str | None = None) -> None:
    """Store one anonymous response. With a token, the invitation is marked as used (it cannot answer twice).
    Raises DuplicateResponse for a response identical to one already stored."""
    import random
    with lock(cid):
        s = load_survey(cid)
        if token:
            inv = next((i for i in s["invites"] if i["token"] == token), None)
            if inv is None: raise KeyError(token)
            if inv["responded"]: raise ValueError("already responded")
        hashes = set(s["hashes"]) if "hashes" in s else {response_hash(r["answers"], r["ratings"]) for r in s["responses"]}
        h = response_hash(answers, ratings)
        if h in hashes: raise DuplicateResponse(h)
        if token: inv["responded"] = True
        s["responses"].insert(random.randint(0, len(s["responses"])), {"answers": answers, "ratings": ratings})
        s["hashes"] = sorted(hashes | {h})
        _write(survey_path(cid), s)


def set_used(cid: str, n: int) -> None:
    """Record how many responses the inside-out run on file used."""
    with lock(cid):
        s = load_survey(cid); s["used"] = n; _write(survey_path(cid), s)

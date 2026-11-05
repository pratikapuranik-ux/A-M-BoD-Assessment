"""Rules 16 and 17 (skill v1.3): the retrieval log, the fact sheet, source eligibility and indicator time windows.

Port of skill/scripts/retrieval_checks.py and init_run.py. Pure logic: the spec is skill/assets/retrieval_spec.json. The checks apply to
outside-in evidence and cells (the `board` lens); board documents and questionnaire answers are not public sources and are not typed or
windowed. Issues are (subject, where, message) tuples, like the rest of the engine.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

from .skill import FW, IND_IDS


def _load_spec() -> dict:
    here = Path(__file__).resolve()
    for p in (os.environ.get("BOARD_SKILL_DIR") and Path(os.environ["BOARD_SKILL_DIR"]) / "assets" / "retrieval_spec.json",
              here.parents[3] / "skill" / "assets" / "retrieval_spec.json", here.parents[2] / "skill" / "assets" / "retrieval_spec.json"):
        if p and p.exists(): return json.loads(p.read_text(encoding="utf-8"))
    raise FileNotFoundError("retrieval_spec.json not found in skill/assets")


SPEC: dict = _load_spec()
RULE_VERSION = "1.3"  # the first rule version that carries the retrieval log and the fact sheet
INSIDE = {"inside_out", "self_assessment"}  # not public sources: not typed or windowed
NO_WINDOW = {"silence", "searched_record"}
W24, W36, W60 = set(FW["windows"]["behaviour_24m"]), set(FW["windows"]["behaviour_36m"]), set(FW["windows"]["trend_5y"])
BEHAVIOUR = W24 | W36
FIVE_YEAR_LOOKBACK = {"2.4"}  # committee structure is judged across five proxies (Rule 5)
ITEM_STATUS = ("found", "searched_none", "unavailable", "not_applicable")
Issue = tuple[str, str, str]


def applies(run: dict) -> bool:
    """Runs on v1.2 predate the log: they are still shown and re-graded, but not held to Rules 16-17."""
    return str((run.get("run") or {}).get("rule_version")) == RULE_VERSION


def pdate(s) -> dt.date | None:
    if not s: return None
    s = str(s)[:10]
    for fmt, n in (("%Y-%m-%d", 10), ("%Y-%m", 7), ("%Y", 4)):
        try: return dt.datetime.strptime(s[:n], fmt).date()
        except ValueError: pass
    return None


def months_before(d: dt.date, m: int) -> dt.date:
    y, mo = divmod(d.month - 1 - m, 12)
    return dt.date(d.year + y, mo + 1, min(d.day, 28))


def window_months(iid: str) -> int:
    return 24 if iid in W24 else 36 if iid in W36 else 60 if (iid in W60 or iid in FIVE_YEAR_LOOKBACK) else 24


def _domain(url: str) -> str:
    try: h = urlparse(url or "").hostname or ""
    except ValueError: return ""
    return h[4:] if h.startswith("www.") else h


def _dom_match(h: str, doms) -> bool:
    return any(h == d or h.endswith("." + d) for d in doms)


def effective_date(item: dict) -> dt.date | None:
    return pdate(item.get("event_date")) or pdate(item.get("date"))


# ---------------------------------------------------------------- the checklist handed to a subject (init_run.py)

def sector_for(*names: str) -> str:
    """The sector pack for a set of company names: the energy pack when any of them is an oil, gas or integrated energy company."""
    env = (os.environ.get("BOARD_SECTOR") or "").strip().lower()
    if env in SPEC["sector_packs"]: return env
    pat = re.compile(r"chevron|exxon|shell|\bbp\b|british petroleum|totalenergies|conoco|equinor|\beni\b|repsol|occidental|marathon|valero|phillips 66|"
                     r"\boil\b|petrol|\bgas\b|energy|resources|hess|devon|eog|apache|petro", re.I)
    return "energy" if any(pat.search(n or "") for n in names) else "general"


def pack_of(sector: str) -> dict:
    return SPEC["sector_packs"].get(sector) or SPEC["sector_packs"]["general"]


def checklist(name: str, as_of: dt.date, sector: str) -> str:
    """The retrieval log and fact sheet for one subject, as the text of its research prompt: what to search, with the queries
    filled in and the dates every sweep must cover."""
    pack = pack_of(sector); es_from = months_before(as_of, SPEC["event_sweep_months"]); r4_from = months_before(as_of, 36)
    lines = [f"Retrieval log and fact sheet (Rule 16) for {name}. Fill every entry below and submit it with the scores; none may be left out.", "",
             "retrieval_items: one entry for each of R1 to R8. status is found (list documents; for R1 and R2 list the years covered), searched_none or "
             "unavailable (list the queries or sources tried), or not_applicable (R5 only, with a reason). R4 also needs from, to and filings_reviewed "
             f"(the filing feed from {r4_from} to {as_of}: 36 months for Item 5.02, 24 months for the rest; feed names the feed used)."]
    for it in SPEC["retrieval_items"]: lines.append(f"  {it['id']}: {it['name']}")
    lines += ["", "registers: one entry for each register below: status searched (query, date, hits = evidence codes, or an empty list when nothing was found; "
              "an empty search is also a searched_record evidence item) or not_applicable (with a reason)."]
    for r in pack["registers"]:
        lines.append(f"  {r['id']}: {r['name']}" + (f" (applies if: {r['applies_if']})" if r.get("applies_if") else "") + f"; query: {r['query'].replace('{company}', name)}")
    if pack.get("requires_extra_registers"):
        lines.append(f"  This subject's sector has no built-in pack: name at least {pack['requires_extra_registers']} sector regulator or court register relevant "
                     "to customer harm (1.3), give it an id starting REG-X, and log it here and in extra_registers.")
    lines += ["", f"event_sweep: one entry for each query below, run over the 24 months from {es_from} to {as_of} (from = {es_from}, to = {as_of}); "
              "results_reviewed is the number of results you read and hits the evidence codes it produced."]
    for q in SPEC["event_sweep"]: lines.append(f"  {q['id']}: {q['query'].replace('{company}', name)}  (bears on {', '.join(q['indicators'])})")
    lines += ["", "facts: for each indicator, one entry per field. status found needs a value and the evidence codes; not_disclosed needs where_searched. "
                  "Read proxies, remuneration and governance reports section by section against these fields before scoring."]
    for iid in IND_IDS:
        lines.append(f"  {iid}: " + "; ".join(f"{f} ({h})" for f, h in SPEC["fact_sheet"][iid]))
    return "\n".join(lines)


# ---------------------------------------------------------------- Rule 17: source eligibility, windows, the recent flag

def check_sources(run: dict, problems: list, warnings: list) -> None:
    S = SPEC["sources"]; meta = run.get("run") or {}
    pack = pack_of(meta.get("sector") or "general")
    trade = set(pack.get("trade_press", [])) | set(meta.get("extra_trade_press") or [])
    trade_doms = list(pack.get("trade_press_domains", []))
    for eid, e in (run.get("evidence") or {}).items():
        if e.get("evidence_class") in INSIDE: continue
        where = f"evidence {eid}"
        st = e.get("source_type"); cls = e.get("evidence_class", "direct"); h = _domain(e.get("url"))
        if h and _dom_match(h, S["blocked_domains"]):
            problems.append(("sources", where, f"domain {h} is excluded by the guardrails (social media, forum, blog or review site)")); continue
        if st not in S["source_types"]:
            problems.append(("sources", where, f"source_type must be one of {S['source_types']}")); continue
        rule_type = st
        if st == "data_platform" and e.get("underlying_source_type") in S["source_types"]: rule_type = e["underlying_source_type"]
        if cls not in S["class_allowed"][rule_type]:
            problems.append(("sources", where, f"evidence_class '{cls}' not allowed for source_type '{rule_type}' (allowed: {S['class_allowed'][rule_type]})"))
        if rule_type == "approved_news":
            outlet = e.get("outlet")
            if outlet not in S["approved_news"]:
                problems.append(("sources", where, f"outlet {outlet!r} is not on the approved news list; re-type as 'other' (indirect) or cite the approved outlet"))
            elif h and not _dom_match(h, S["approved_news"][outlet]):
                warnings.append(("sources", where, f"{outlet} item is a syndicated copy on {h}; cite the original where reachable"))
        if rule_type == "trade_press":
            ok = e.get("outlet") in trade or (h and _dom_match(h, trade_doms))
            if not ok and (trade or trade_doms):
                problems.append(("sources", where, f"{e.get('outlet') or h!r} is not recognised trade press for this sector; re-type it as 'other' (indirect)"))


def check_windows_and_recent(run: dict, problems: list, warnings: list) -> None:
    meta = run.get("run") or {}; as_of = pdate(meta.get("as_of")); ev = run.get("evidence") or {}
    if not as_of: return
    for eid, e in ev.items():
        if e.get("evidence_class") in INSIDE: continue
        d = effective_date(e)
        if not d: problems.append(("sources", f"evidence {eid}", "date (YYYY-MM or YYYY-MM-DD) required")); continue
        if d > as_of: problems.append(("sources", f"evidence {eid}", f"dated {d} after run.as_of {as_of}"))
        rec = (as_of - d).days <= 90
        if bool(e.get("recent")) != rec: e["recent"] = rec
    for s in run.get("subjects", []):
        for iid, c in (s.get("indicators") or {}).items():
            cell = (c or {}).get("board") or {}
            if cell.get("score") is None: continue
            start = months_before(as_of, window_months(iid))
            for eid in cell.get("evidence") or []:
                e = ev.get(eid)
                if not e or e.get("evidence_class") in NO_WINDOW | INSIDE: continue
                if iid in BEHAVIOUR and not e.get("event_date"):
                    problems.append((s["name"], iid, f"{eid}: behaviour indicator ({window_months(iid)}-month window) needs event_date on each evidence item (the date of the event itself; the document date when they are the same)")); continue
                d = effective_date(e)
                if d and d < start:
                    problems.append((s["name"], iid, f"{eid} dated {d} is outside the {window_months(iid)}-month window (from {start}); use evidence inside the window or score on what the window shows"))


# ---------------------------------------------------------------- Rule 16: the log and the fact sheet

def check_retrieval_log(run: dict, problems: list, warnings: list) -> None:
    meta = run.get("run") or {}; as_of = pdate(meta.get("as_of")); tol = dt.timedelta(days=SPEC["as_of_tolerance_days"])
    sector = meta.get("sector"); pack = SPEC["sector_packs"].get(sector); ev = run.get("evidence") or {}
    if not as_of: problems.append(("run", "run.as_of", "required (YYYY-MM-DD): the date every sweep must reach")); return
    if not pack: problems.append(("run", "run.sector", f"must be one of {list(SPEC['sector_packs'])}")); return
    extra = meta.get("extra_registers") or []
    regs = [r["id"] for r in pack["registers"]] + [r.get("id") for r in extra]
    if pack.get("requires_extra_registers") and len(extra) < pack["requires_extra_registers"]:
        problems.append(("run", "run.extra_registers", f"sector '{sector}' needs at least {pack['requires_extra_registers']} sector-specific register"))
    unavailable_txt = " ".join((run.get("coverage") or {}).get("documents_unavailable", []))
    for s in run.get("subjects", []):
        name = s["name"]; log = s.get("retrieval_log")
        if not log: problems.append((name, "retrieval_log", "missing (Rule 16): submit the retrieval log and fact sheet with the scores")); continue
        items = log.get("items") or {}
        for it in SPEC["retrieval_items"]:
            rid = it["id"]; x = items.get(rid); w = f"retrieval_log.{rid}"
            if not x: problems.append((name, w, f"not logged: {it['name']}")); continue
            stt = x.get("status")
            if stt not in ITEM_STATUS: problems.append((name, w, f"status {stt!r} not final (found / searched_none / unavailable / not_applicable)")); continue
            if stt == "found" and not x.get("documents"): problems.append((name, w, "found needs documents listed"))
            if stt in ("searched_none", "unavailable") and not x.get("queries"): problems.append((name, w, f"{stt} needs the queries or sources tried"))
            if stt == "not_applicable" and not (it.get("may_be_not_applicable") and x.get("reason")):
                problems.append((name, w, "not_applicable is allowed only for R5 with a reason"))
            if stt == "unavailable" and name not in unavailable_txt and name.split()[0] not in unavailable_txt:
                warnings.append((name, w, "unavailable item not recorded in coverage.documents_unavailable"))
            if stt == "found" and it.get("needs_years") and len(set(x.get("years") or [])) < it["needs_years"]:
                warnings.append((name, w, f"only {len(set(x.get('years') or []))} of {it['needs_years']} years covered; record the gap in coverage and mark affected trend cells"))
            if stt == "found" and it.get("min_count") and len(x.get("documents") or []) < it["min_count"]:
                warnings.append((name, w, f"{len(x.get('documents') or [])} documents; minimum is {it['min_count']}"))
            if rid == "R4" and stt == "found":
                f, t = pdate(x.get("from")), pdate(x.get("to"))
                if not (f and t): problems.append((name, w, "filing sweep needs from and to dates"))
                else:
                    if f > months_before(as_of, it["sweep_months"]) + tol: problems.append((name, w, f"filing sweep starts {f}; must start by {months_before(as_of, it['sweep_months'])} (36 months for departures)"))
                    if t < as_of - tol: problems.append((name, w, f"filing sweep ends {t}; must reach run.as_of {as_of}"))
                if not isinstance(x.get("filings_reviewed"), int): problems.append((name, w, "filings_reviewed (count) required"))
        rl = log.get("registers") or {}
        for rid in regs:
            x = rl.get(rid); w = f"registers.{rid}"
            if not x: problems.append((name, w, "register not logged")); continue
            if x.get("status") == "not_applicable":
                if not x.get("reason"): problems.append((name, w, "not_applicable needs a reason"))
            elif x.get("status") == "searched":
                if not (x.get("query") and x.get("date")): problems.append((name, w, "searched needs query and date"))
                bad = [e for e in x.get("hits") or [] if e not in ev]
                if bad: problems.append((name, w, f"hits not in evidence: {bad}"))
            else: problems.append((name, w, "status must be searched or not_applicable"))
        es = log.get("event_sweep") or {}; start = months_before(as_of, SPEC["event_sweep_months"])
        for q in SPEC["event_sweep"]:
            x = es.get(q["id"]); w = f"event_sweep.{q['id']}"
            if not x: problems.append((name, w, f"not run: {q['query'].replace('{company}', name)}")); continue
            if "{company}" in (x.get("query") or "{company}"): problems.append((name, w, "query text missing or template not filled"))
            f, t = pdate(x.get("from")), pdate(x.get("to"))
            if not (f and t): problems.append((name, w, "from and to dates required")); continue
            if f > start + tol: problems.append((name, w, f"starts {f}; must cover 24 months from {start}"))
            if t < as_of - tol: problems.append((name, w, f"ends {t}; must reach run.as_of {as_of}"))
            if not isinstance(x.get("results_reviewed"), int): problems.append((name, w, "results_reviewed (count) required"))
            bad = [e for e in x.get("hits") or [] if e not in ev]
            if bad: problems.append((name, w, f"hits not in evidence: {bad}"))
        facts = s.get("facts") or {}
        for iid in IND_IDS:
            for field, _hint in SPEC["fact_sheet"][iid]:
                x = (facts.get(iid) or {}).get(field); w = f"facts.{iid}.{field}"
                if not x: problems.append((name, w, "not recorded")); continue
                stt = x.get("status")
                if stt == "found":
                    if not x.get("value"): problems.append((name, w, "found needs a value"))
                    if not x.get("evidence"): problems.append((name, w, "found needs evidence ids"))
                    bad = [e for e in x.get("evidence") or [] if e not in ev]
                    if bad: problems.append((name, w, f"evidence ids not in evidence list: {bad}"))
                elif stt == "not_disclosed":
                    if not x.get("where_searched"): problems.append((name, w, "not_disclosed needs where_searched"))
                else: problems.append((name, w, f"status {stt!r} not final (found / not_disclosed)"))


def check_run(run: dict, problems: list, warnings: list) -> None:
    """Rules 16 and 17 on a v1.3 run; a no-op for earlier rule versions."""
    if not applies(run): return
    check_retrieval_log(run, problems, warnings)
    check_sources(run, problems, warnings)
    check_windows_and_recent(run, problems, warnings)


def log_from_lists(sub: dict) -> tuple[dict, dict]:
    """A subject's submitted lists (as the model's tool returns them) as the run file's dict-of-dicts log and fact sheet."""
    def pick(x, *keys): return {k: x[k] for k in keys if x.get(k) not in (None, "", [], -1)}
    items = {x["id"]: pick(x, "status", "documents", "queries", "years", "from", "to", "filings_reviewed", "feed", "reason") for x in sub.get("retrieval_items", [])}
    regs = {x["id"]: {**pick(x, "status", "query", "date", "reason"), "hits": list(x.get("hits") or [])} for x in sub.get("registers", [])}
    es = {x["id"]: {**pick(x, "query", "from", "to", "results_reviewed"), "hits": list(x.get("hits") or [])} for x in sub.get("event_sweep", [])}
    facts: dict[str, dict] = {}
    for f in sub.get("facts", []):
        facts.setdefault(f["indicator"], {})[f["field"]] = pick(f, "status", "value", "evidence", "where_searched")
    return {"items": items, "registers": regs, "event_sweep": es}, facts

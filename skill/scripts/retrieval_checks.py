"""retrieval_checks.py - mechanical checks added in rules v1.3 (outside-in).

Called by grade.py. Enforces:
  R16  retrieval log: every Rule 14 item, every sector-pack register and every event-sweep query is
       logged per subject, and the sweeps run up to run.as_of
  R16  fact sheet: every must-extract fact for every indicator is recorded per subject as found
       (with evidence) or not disclosed (with where it was searched)
  R17  source eligibility: each evidence item declares a source_type; its evidence_class must be
       allowed for that type; news must come from the approved list; recognised trade press only;
       blocked domains never
  R17  time windows: evidence cited in a scored cell must fall inside the indicator's window (2.4 uses five years)
       (event_date where the event predates the document; required for behaviour indicators)
  R17  recent flag: recomputed from run.as_of (event or document within 90 days)
  R19  reconciliation: no cell left pending re-research, no stale synthesis text
"""
import json, os, datetime as dt
from urllib.parse import urlparse
from common import FW, IND_IDS

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = json.load(open(os.path.join(HERE, "..", "assets", "retrieval_spec.json")))
W24, W36, W60 = set(FW["windows"]["behaviour_24m"]), set(FW["windows"]["behaviour_36m"]), set(FW["windows"]["trend_5y"])
BEHAVIOUR = W24 | W36
NO_WINDOW = {"silence", "searched_record"}
INSIDE = {"inside_out", "self_assessment"}   # evidence of the inside-out stage: not typed or windowed like public sources


def pdate(s):
    if not s: return None
    s = str(s)[:10]
    for fmt, n in (("%Y-%m-%d", 10), ("%Y-%m", 7), ("%Y", 4)):
        try: return dt.datetime.strptime(s[:n], fmt).date()
        except ValueError: pass
    return None


def months_before(d, m):
    y, mo = divmod(d.month - 1 - m, 12)
    return dt.date(d.year + y, mo + 1, min(d.day, 28))


FIVE_YEAR_LOOKBACK = {"2.4"}   # committee structure is judged across five proxies (framework, Rule 5)


def window_months(iid):
    return 24 if iid in W24 else 36 if iid in W36 else 60 if (iid in W60 or iid in FIVE_YEAR_LOOKBACK) else 24


def domain(url):
    try: h = urlparse(url or "").hostname or ""
    except ValueError: return ""
    return h[4:] if h.startswith("www.") else h


def dom_match(h, doms):
    return any(h == d or h.endswith("." + d) for d in doms)


def effective_date(item):
    return pdate(item.get("event_date")) or pdate(item.get("date"))


def check_sources(run, problems, warnings):
    S = SPEC["sources"]; pack = SPEC["sector_packs"].get(run["run"].get("sector"), {})
    trade = set(pack.get("trade_press", [])) | set(run["run"].get("extra_trade_press", []))
    trade_doms = list(pack.get("trade_press_domains", []))
    for eid, e in run.get("evidence", {}).items():
        if e.get("evidence_class") in INSIDE: continue   # board documents and questionnaire answers are not public sources (inside-out stage)
        where = f"evidence {eid}"
        st = e.get("source_type"); cls = e.get("evidence_class", "direct"); h = domain(e.get("url"))
        if h and dom_match(h, S["blocked_domains"]):
            problems.append(("sources", where, f"domain {h} is excluded by the guardrails (social media, forum, blog or review site)")); continue
        if st not in S["source_types"]:
            problems.append(("sources", where, f"source_type must be one of {S['source_types']}")); continue
        rule_type = st
        if st == "data_platform" and e.get("underlying_source_type") in S["source_types"]:
            rule_type = e["underlying_source_type"]
        if cls not in S["class_allowed"][rule_type]:
            problems.append(("sources", where, f"evidence_class '{cls}' not allowed for source_type '{rule_type}' (allowed: {S['class_allowed'][rule_type]})"))
        if rule_type == "approved_news":
            outlet = e.get("outlet")
            if outlet not in S["approved_news"]:
                problems.append(("sources", where, f"outlet {outlet!r} is not on the approved news list; re-type as 'other' (indirect) or cite the approved outlet"))
            elif h and not dom_match(h, S["approved_news"][outlet]):
                warnings.append(("sources", where, f"{outlet} item is a syndicated copy on {h}; cite the original where reachable"))
        if rule_type == "trade_press":
            ok = e.get("outlet") in trade or (h and dom_match(h, trade_doms))
            if not ok and (trade or trade_doms):
                problems.append(("sources", where, f"{e.get('outlet') or h!r} is not recognised trade press for this sector; add it to run.extra_trade_press (and note why under coverage.notes) or re-type as 'other'"))
            elif not ok:
                warnings.append(("sources", where, "trade press outlet not in a sector pack; confirm it is recognised"))
            if cls == "direct": warnings.append(("sources", where, "trade press is direct evidence for event facts only; check the rationale uses it that way"))


def check_windows_and_recent(run, problems, warnings):
    as_of = pdate(run["run"].get("as_of")); ev = run.get("evidence", {})
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
                if not e or e.get("evidence_class") in NO_WINDOW: continue
                if iid in BEHAVIOUR and not e.get("event_date"):
                    problems.append((s["name"], iid, f"{eid}: behaviour indicator ({window_months(iid)}-month window) needs event_date on each evidence item")); continue
                d = effective_date(e)
                if d and d < start:
                    problems.append((s["name"], iid, f"{eid} dated {d} is outside the {window_months(iid)}-month window (from {start})"))


def check_retrieval_log(run, problems, warnings):
    meta = run["run"]; as_of = pdate(meta.get("as_of")); tol = dt.timedelta(days=SPEC["as_of_tolerance_days"])
    sector = meta.get("sector"); pack = SPEC["sector_packs"].get(sector)
    ev = run.get("evidence", {})
    if not as_of: problems.append(("run", "run.as_of", "required (YYYY-MM-DD): the date every sweep must reach")); return
    if not pack: problems.append(("run", "run.sector", f"must be one of {list(SPEC['sector_packs'])}")); return
    regs = [r["id"] for r in pack["registers"]] + [r.get("id") for r in meta.get("extra_registers", [])]
    if pack.get("requires_extra_registers") and len(meta.get("extra_registers", [])) < pack["requires_extra_registers"]:
        problems.append(("run", "run.extra_registers", f"sector '{sector}' needs at least {pack['requires_extra_registers']} sector-specific register"))
    unavailable_txt = " ".join(run.get("coverage", {}).get("documents_unavailable", []))
    for s in run.get("subjects", []):
        name = s["name"]; log = s.get("retrieval_log")
        if not log: problems.append((name, "retrieval_log", "missing (Rule 16): run init_run.py and fill it as you research")); continue
        items = log.get("items", {})
        for it in SPEC["retrieval_items"]:
            rid = it["id"]; x = items.get(rid); w = f"retrieval_log.{rid}"
            if not x: problems.append((name, w, f"not logged: {it['name']}")); continue
            stt = x.get("status")
            if stt not in ("found", "searched_none", "unavailable", "not_applicable"):
                problems.append((name, w, f"status {stt!r} not final (found / searched_none / unavailable / not_applicable)")); continue
            if stt == "found" and not x.get("documents"): problems.append((name, w, "found needs documents listed"))
            if stt in ("searched_none", "unavailable") and not x.get("queries"): problems.append((name, w, f"{stt} needs the queries or sources tried"))
            if stt == "not_applicable" and not (it.get("may_be_not_applicable") and x.get("reason")):
                problems.append((name, w, "not_applicable is allowed only for R5 with a reason"))
            if stt == "unavailable" and name not in unavailable_txt:
                warnings.append((name, w, "unavailable item not recorded in coverage.documents_unavailable"))
            if stt == "found" and it.get("needs_years") and len(set(x.get("years", []))) < it["needs_years"]:
                warnings.append((name, w, f"only {len(set(x.get('years', [])))} of {it['needs_years']} years covered; record the gap in coverage and mark affected trend cells"))
            if stt == "found" and it.get("min_count") and len(x.get("documents", [])) < it["min_count"]:
                warnings.append((name, w, f"{len(x.get('documents', []))} documents; minimum is {it['min_count']}"))
            if rid == "R4" and stt == "found":
                f, t = pdate(x.get("from")), pdate(x.get("to"))
                if not (f and t): problems.append((name, w, "filing sweep needs from and to dates"))
                else:
                    if f > months_before(as_of, it["sweep_months"]) + tol: problems.append((name, w, f"filing sweep starts {f}; must start by {months_before(as_of, it['sweep_months'])} (36 months for departures)"))
                    if t < as_of - tol: problems.append((name, w, f"filing sweep ends {t}; must reach run.as_of {as_of}"))
                if not isinstance(x.get("filings_reviewed"), int): problems.append((name, w, "filings_reviewed (count) required"))
        # registers (R6)
        rl = log.get("registers", {})
        for rid in regs:
            x = rl.get(rid); w = f"registers.{rid}"
            if not x: problems.append((name, w, "register not logged")); continue
            if x.get("status") == "not_applicable":
                if not x.get("reason"): problems.append((name, w, "not_applicable needs a reason"))
            elif x.get("status") == "searched":
                if not (x.get("query") and x.get("date")): problems.append((name, w, "searched needs query and date"))
                bad = [e for e in x.get("hits", []) if e not in ev]
                if bad: problems.append((name, w, f"hits not in evidence: {bad}"))
            else: problems.append((name, w, "status must be searched or not_applicable"))
        # event sweep
        es = log.get("event_sweep", {}); start = months_before(as_of, SPEC["event_sweep_months"])
        for q in SPEC["event_sweep"]:
            x = es.get(q["id"]); w = f"event_sweep.{q['id']}"
            if not x: problems.append((name, w, f"not run: {q['query']}")); continue
            if "{company}" in (x.get("query") or "{company}"): problems.append((name, w, "query text missing or template not filled"))
            f, t = pdate(x.get("from")), pdate(x.get("to"))
            if not (f and t): problems.append((name, w, "from and to dates required")); continue
            if f > start + tol: problems.append((name, w, f"starts {f}; must cover 24 months from {start}"))
            if t < as_of - tol: problems.append((name, w, f"ends {t}; must reach run.as_of {as_of}"))
            if not isinstance(x.get("results_reviewed"), int): problems.append((name, w, "results_reviewed (count) required"))
            bad = [e for e in x.get("hits", []) if e not in ev]
            if bad: problems.append((name, w, f"hits not in evidence: {bad}"))
        # fact sheet
        facts = s.get("facts", {})
        for iid in IND_IDS:
            for field, _hint in SPEC["fact_sheet"][iid]:
                x = (facts.get(iid) or {}).get(field); w = f"facts.{iid}.{field}"
                if not x: problems.append((name, w, "not recorded")); continue
                stt = x.get("status")
                if stt == "found":
                    if not x.get("value"): problems.append((name, w, "found needs a value"))
                    if not x.get("evidence"): problems.append((name, w, "found needs evidence ids"))
                    bad = [e for e in x.get("evidence", []) if e not in ev]
                    if bad: problems.append((name, w, f"evidence ids not in evidence list: {bad}"))
                elif stt == "not_disclosed":
                    if not x.get("where_searched"): problems.append((name, w, "not_disclosed needs where_searched"))
                else: problems.append((name, w, f"status {stt!r} not final (found / not_disclosed)"))


def check_reconciliation(run, problems, warnings):
    rec = run.get("run", {}).get("reconciliation")
    for s in run.get("subjects", []):
        for iid, c in (s.get("indicators") or {}).items():
            if ((c or {}).get("board") or {}).get("pending_recon"):
                problems.append((s["name"], iid, "pending re-research from reconciliation: research, then score or mark not assessable and remove pending_recon"))
    if rec and rec.get("stale_text"):
        problems.append(("run", "reconciliation.stale_text", "rewrite these fields for the reconciled scores, then empty the list: " + ", ".join(rec["stale_text"])))


def run_checks(run, problems, warnings):
    check_reconciliation(run, problems, warnings)
    check_retrieval_log(run, problems, warnings)
    check_sources(run, problems, warnings)
    check_windows_and_recent(run, problems, warnings)

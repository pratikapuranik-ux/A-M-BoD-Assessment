"""Retrieval tasks (cfg.PIPELINE "tasks"): the Rule 14 and Rule 16 research of one subject as short independent conversations.

Why: one long conversation per subject re-reads everything it has gathered at every step, so cost grows with the square of the research,
and completeness of the retrieval log rests on the model remembering every entry. Here each retrieval item, the sector registers and each
event-sweep query is its own small task. The engine writes the log from them (query text, date ranges and result counts are its own, not
the model's), numbers the evidence, and hands the scoring conversation a ledger to score from. Rules, checks and the log format are unchanged.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from concurrent.futures import as_completed
from pathlib import Path

import structlog

from . import settings as cfg
from .checks import _check_evidence, _dups, _merge
from .client import ResearchError, ResearchInvalid
from .conversation import Conv
from .progress import narrate, phases
from .tools import TASK_KEYS, TASK_TOOL, render_prompt, web_tools
from app.domain import retrieval
from app.services.usage import Pool

log = structlog.get_logger("agents.tasks")
_SLOTS = threading.BoundedSemaphore(cfg.TASK_CALLS)  # retrieval tasks running at once, across every subject
ITEM_STATUS = retrieval.ITEM_STATUS


def _instructions(t: dict) -> str:
    if t["kind"] == "item":
        extra = ("Read the latest proxy statement in full (pay discussion, governance guidelines, director and committee sections, board evaluation) and the "
                 "earlier years for renewal, committee and evaluation changes, section by section. " if t["key"] == "R2" else
                 "Read the cash-flow statements of five fiscal years. " if t["key"] == "R1" else "")
        return (f"{t['text']}\n{extra}If a PDF or page cannot be fetched, try another route before giving up: the investor-relations HTML version, the SEC EDGAR "
                f"filing index, a regulator or exchange page, or a reputable mirror of the same filing. Record a document in documents_unavailable only after those "
                f"routes failed.\nLog entry: retrieval_items with one entry for {t['items'][0]}: status found (list the documents you read in documents), searched_none "
                f"or unavailable (list the queries or sources you tried in queries), or not_applicable (R5 only, with a reason). Use -1 for filings_reviewed and an empty "
                f"string for feed where they do not apply.")
    if t["kind"] == "registers":
        regs = "\n".join(f"  {r['id']}: {r['name']}" + (f" (applies if: {r['applies_if']})" if r.get("applies_if") else "") + f"; query: {r['query']}" for r in t["registers"])
        need = (f"\nThis subject's sector has no built-in pack: name at least {t['need_extra']} sector regulator or court register relevant to customer harm (1.3), give it "
                f"an id starting REG-X, search it, and list it in extra_registers and in registers." if t["need_extra"] else "")
        return (f"{t['text']}\nRun each search below with web_search and review the results.\n{regs}{need}\nLog: registers with one entry per register above (and per extra "
                f"register): status searched, with hits = the refs of the evidence items it produced (an empty list when nothing was found), or not_applicable with a reason. "
                f"An empty search is also recorded as an evidence item with evidence_class searched_record and a search_log naming the query and the date. Also submit "
                f"retrieval_items with one entry for R6: status found (list the registers searched in documents) or unavailable (queries).")
    return (f"Event sweep {t['sweep']}: run this query with web_search over the 24 months from {t['frm']} to {t['to']} (rephrase or add terms where that covers the range "
            f"better): {t['query']}\nReview the results. Record each event that bears on indicators {', '.join(t['indicators'])} as an evidence item, with event_date the date "
            f"of the event. Log: event_sweep with one entry, id {t['sweep']}, hits = the refs of the evidence items it produced (an empty list when it surfaced nothing; then "
            f"add no evidence).")


def _problems(t: dict, data: dict, meta: dict, counts: dict) -> list[str]:
    p: list[str] = []; ev = data.get("evidence") or []; refs = [e.get("ref") for e in ev]
    if not all(refs): p.append("every evidence item needs a ref")
    if d := _dups(refs): p.append(f"evidence refs used more than once: {d}")
    p += _check_evidence([dict(e, code=e.get("ref") or "?") for e in ev])
    m = dict(meta, extra_trade_press=list(meta.get("extra_trade_press") or []) + list(data.get("extra_trade_press") or []))
    run = {"run": m, "evidence": {e.get("ref"): dict(e) for e in ev}, "subjects": []}; iss: list = []; warn: list = []
    retrieval.check_sources(run, iss, warn); retrieval.check_windows_and_recent(run, iss, warn)
    p += [f"{w}: {msg}" for _, w, msg in iss]
    rs = set(refs)
    if t["kind"] in ("item", "registers"):
        got = {x.get("id"): x for x in data.get("retrieval_items") or []}
        for rid in t["items"]:
            x = got.get(rid)
            if not x: p.append(f"retrieval_items needs an entry for {rid}"); continue
            stt = x.get("status")
            if stt not in ITEM_STATUS: p.append(f"{rid}: status must be one of {list(ITEM_STATUS)}")
            elif stt == "found" and not x.get("documents"): p.append(f"{rid}: found needs the documents listed")
            elif stt in ("searched_none", "unavailable") and not x.get("queries"): p.append(f"{rid}: {stt} needs the queries or sources tried")
            elif stt == "not_applicable" and not (rid == "R5" and x.get("reason")): p.append(f"{rid}: not_applicable is allowed only for R5, with a reason")
            if rid == "R4" and stt == "found" and (x.get("filings_reviewed") or 0) < 0: p.append("R4: filings_reviewed (a count) is required")
    if t["kind"] == "registers":
        rg = {x.get("id"): x for x in data.get("registers") or []}
        extra = [x.get("id") for x in data.get("extra_registers") or []]
        for rid in [r["id"] for r in t["registers"]] + extra:
            x = rg.get(rid)
            if not x: p.append(f"registers needs an entry for {rid}"); continue
            if x.get("status") == "not_applicable" and not x.get("reason"): p.append(f"{rid}: not_applicable needs a reason")
            if x.get("status") == "searched" and (bad := [h for h in x.get("hits") or [] if h not in rs]): p.append(f"{rid}: hits {bad} are not refs of your evidence items")
        if len(extra) < t["need_extra"]: p.append(f"name at least {t['need_extra']} sector register in extra_registers")
        if not counts["web_search"]: p.append("run the register searches with web_search")
    if t["kind"] == "sweep":
        x = next((x for x in data.get("event_sweep") or [] if x.get("id") == t["sweep"]), None)
        if not x: p.append(f"event_sweep needs an entry with id {t['sweep']}")
        elif bad := [h for h in x.get("hits") or [] if h not in rs]: p.append(f"hits {bad} are not refs of your evidence items")
        if not counts["web_search"]: p.append("run the query with web_search before you submit")
    return p


CACHE_DAYS = 2


def _cache_file(subject, ctx: dict, t: dict, names: list[str]) -> Path:
    from app.services import storage
    key = json.dumps([1, subject.name, subject.ticker, subject.role, t["key"], ctx["meta"]["as_of"], cfg.TASK_MODEL or subject.model or "", cfg.TASK_EFFORT or "", cfg.TASK_SEARCHES, cfg.TASK_FETCHES,
                      sorted(names) if t["kind"] == "item" and t["key"] in ("R1", "R2") else []], sort_keys=True)
    return storage.root() / "_tasks" / (hashlib.sha256(key.encode()).hexdigest()[:32] + ".json")


def _run_task(subject, ctx: dict, t: dict, names: list[str], band, i: int) -> dict:
    """One retrieval task, kept safe: a finished task is read back from disk when the same one was done today; a task whose answer cannot be made valid (or that
    fails in our own code) is recorded as not covered, with the reason, instead of ending the whole run and losing everything paid for so far. Failures that
    mean the run cannot go on (a rejected key, no quota, a stop requested) still stop it."""
    f = _cache_file(subject, ctx, t, names) if cfg.TASK_CACHE else None
    if f is not None and f.is_file() and time.time() - f.stat().st_mtime < CACHE_DAYS * 86400:
        try:
            r = json.loads(f.read_text(encoding="utf-8")); r["task"] = t; r["cached"] = True
            band.note(i, f"{subject.short}: {t['title']} found from earlier today"); return r
        except (OSError, ValueError): pass
    try:
        r = _run_task_live(subject, ctx, t, names, band, i)
    except ResearchInvalid as e:
        reason = str(e)[:300]
    except ResearchError as e:
        if "without submitting" not in str(e): raise  # key, quota, rate limit, stop: the run cannot go on
        reason = str(e)[:300]
    except Exception as e:  # noqa: BLE001 - a bug in handling one task's answer must not cost the other 100
        if ctx.get("stop") is not None and ctx["stop"].is_set(): raise
        log.error("task_failed", subject=subject.name, task=t["key"], error=f"{type(e).__name__}: {e}")
        reason = f"{type(e).__name__}: {str(e)[:200]}"
    else:
        if f is not None:
            try: f.parent.mkdir(parents=True, exist_ok=True); f.write_text(json.dumps({"data": r["data"], "counts": r["counts"]}, ensure_ascii=False), encoding="utf-8")
            except OSError: pass
        return r
    log.warning("task_not_covered", subject=subject.name, task=t["key"], reason=reason)
    band.note(i, f"{subject.short}: {t['title']} could not be completed and is recorded as not covered")
    return {"task": t, "data": {}, "counts": {"web_search": 0, "web_fetch": 0, "results": 0}, "failed": reason}


def _run_task_live(subject, ctx: dict, t: dict, names: list[str], band, i: int) -> dict:
    meta = ctx["meta"]; counts = {"web_search": 0, "web_fetch": 0, "results": 0}
    docs = (f"The A&M team also supplied these documents on {subject.name}: {'; '.join(names)}. They count toward R1 and R2 for the years they cover (check the file names "
            "and the first pages); search the web only for the years and items they do not cover, and list them in documents when you rely on them." if names and t["kind"] == "item"
            and t["key"] in ("R1", "R2") else "")
    content = render_prompt("task.md", today=ctx["today"], as_of=meta["as_of"], name=subject.name, ticker=subject.ticker or "n/a",
                            role="the company being assessed" if subject.role == "company" else "peer", title=t["title"],
                            behaviour_from=meta["document_window"]["behaviour_from"], trend_from=meta["document_window"]["trend_from"],
                            search_budget=cfg.TASK_SEARCHES, fetch_budget=cfg.TASK_FETCHES, instructions=_instructions(t), docs_note=docs,
                            indicators=", ".join(t["indicators"]))

    def on_block(b):
        k = getattr(b, "type", "")
        if k == "server_tool_use" and b.name in counts:
            counts[b.name] += 1; band.note(i, narrate(subject.short, b.name, getattr(b, "input", None)))
        elif k == "web_search_tool_result" and isinstance(getattr(b, "content", None), list): counts["results"] += len(b.content)
    on_phase = phases(lambda m: band.note(i, m), {"thinking": f"Weighing {t['title']} for {subject.short}", TASK_TOOL["name"]: f"Writing up {t['title']} for {subject.short}"})
    conv = Conv(f"{t['title']} for {subject.short}", web_tools(cfg.TASK_SEARCHES, cfg.TASK_FETCHES) + [TASK_TOOL], content, on_block, on_phase,
                model=cfg.TASK_MODEL or subject.model, effort=cfg.TASK_EFFORT)
    conv.stop = ctx.get("stop"); got: dict = {}

    def accept(inp):
        merged = _merge(got or None, inp, TASK_KEYS)
        p = _problems(t, merged, meta, counts)
        got.clear(); got.update(merged)
        return p
    with _SLOTS: conv.submit(TASK_TOOL["name"], accept)
    return {"task": t, "data": got, "counts": counts}


def run_subject(subject, ctx: dict, band, i: int) -> dict:
    """Runs every retrieval task of one subject and returns the seed of its submission: evidence (numbered), the retrieval log lists, the
    extra registers and trade press, documents_unavailable, and the summed counts."""
    plan = retrieval.task_plan(subject.name, ctx["today_date"], ctx["meta"]["sector"]); names = (ctx.get("doc_names") or {}).get(i) or []
    band.set(i, 0.02, f"Planning {len(plan)} retrieval tasks for {subject.short}")
    out: dict[str, dict] = {}
    with Pool(max_workers=min(len(plan), cfg.TASK_CALLS)) as pool:
        futs = {pool.submit(_run_task, subject, ctx, t, names, band, i): t["key"] for t in plan}
        for n, f in enumerate(as_completed(futs), 1):
            out[futs[f]] = f.result()
            band.set(i, 0.8 * n / len(plan), f"{subject.short}: {n} of {len(plan)} retrieval tasks done")
    return assemble([out[t["key"]] for t in plan], subject.prefix, ctx["meta"], subject.short)


def assemble(results: list[dict], prefix: str, meta: dict, short: str = "") -> dict:
    """The tasks' results, in plan order, as one submission seed. Evidence is numbered prefix01, prefix02, ... (the same document read by two tasks
    keeps one number) and the log entries' refs become those codes."""
    ev: list[dict] = []; seen: dict[tuple, str] = {}
    seed: dict = {"evidence": ev, "retrieval_items": [], "registers": [], "event_sweep": [], "extra_registers": [], "extra_trade_press": [], "documents_unavailable": []}
    counts = {"web_search": 0, "web_fetch": 0, "results": 0}
    for r in results:
        t, d = r["task"], r["data"]; code_of: dict[str, str] = {}
        for k in counts: counts[k] += (r.get("counts") or {}).get(k, 0)
        if r.get("failed"):  # not covered: the log still names it, and the report's coverage says so
            why = f"{t['title']} could not be completed ({r['failed'][:140]})"
            seed["documents_unavailable"].append(why)
            for rid in t["items"]: seed["retrieval_items"].append({"id": rid, "status": "unavailable", "documents": [], "queries": [why], "years": [], "filings_reviewed": -1, "feed": "", "reason": ""})
            if t["kind"] == "registers":
                for rg in t.get("registers", []): seed["registers"].append({"id": rg["id"], "status": "searched", "hits": [], "reason": "", "query": rg["query"], "date": t["date"]})
            if t["kind"] == "sweep": seed["event_sweep"].append({"id": t["sweep"], "query": t["query"], "from": t["frm"], "to": t["to"], "results_reviewed": 0, "hits": []})
            continue
        for e in d.get("evidence") or []:
            if not isinstance(e, dict) or not e.get("ref"): continue
            url = (e.get("url") or "").strip().lower(); key = (url, e.get("event_date") or e.get("date")) if url else None
            if key and key in seen: code_of[e["ref"]] = seen[key]; continue
            code = f"{prefix}{len(ev) + 1:02d}"; code_of[e["ref"]] = code
            if key: seen[key] = code
            ev.append({"code": code, **{k: v for k, v in e.items() if k != "ref"}})
        hits = lambda x: [code_of[h] for h in (x.get("hits") or []) if h in code_of]
        for x in d.get("retrieval_items") or []:
            if not isinstance(x, dict) or x.get("id") not in t["items"]: continue
            y = dict(x)
            if x["id"] == "R4" and x.get("status") == "found": y.update({"from": t["frm"], "to": t["to"]})
            seed["retrieval_items"].append(y)
        for x in (d.get("registers") or []) if t.get("kind") == "registers" else []:  # only the registers task answers these; a stray list from another task is ignored
            if not isinstance(x, dict) or not x.get("id"): continue
            q = next((rg["query"] for rg in t.get("registers", []) if rg["id"] == x["id"]), "") or next((rg.get("query") for rg in d.get("extra_registers") or [] if isinstance(rg, dict) and rg.get("id") == x["id"]), "")
            seed["registers"].append({**x, "query": q, "date": t.get("date", ""), "hits": hits(x)})
        for x in d.get("event_sweep") or []:
            if isinstance(x, dict) and x.get("id") == t.get("sweep"):
                seed["event_sweep"].append({"id": x["id"], "query": t["query"], "from": t["frm"], "to": t["to"], "results_reviewed": (r.get("counts") or {}).get("results", 0), "hits": hits(x)})
        for k in ("extra_registers", "extra_trade_press", "documents_unavailable"):
            seed[k] += [x for x in d.get(k) or [] if x not in seed[k]]
    if len(ev) > 999: raise ResearchError(f"The retrieval tasks for {short or prefix} produced {len(ev)} evidence items; at most 999 can be numbered.")
    seed["counts"] = counts
    return seed


def ledger_text(seed: dict) -> str:
    """The evidence the tasks found, as the text the scoring step reads: one line per item."""
    lines = []
    for e in seed["evidence"]:
        when = e.get("event_date") or e.get("date") or ""
        lines.append(f"{e['code']} | {when} | {e.get('evidence_class')} | {e.get('source_type')}{('/' + e['outlet']) if e.get('outlet') else ''} | {e.get('document')} | "
                     f"\"{(e.get('excerpt') or e.get('search_log') or '')[:160]}\" | {e.get('url') or 'searched record'}")
    return "\n".join(lines) if lines else "(no evidence items were found)"

#!/usr/bin/env python3
"""init_run.py - start a run file with the v1.3 retrieval log and fact sheet for every subject.

Usage:
    python init_run.py out.json --company "Chevron:CVX" --peer "ExxonMobil:XOM" --peer "BP:BP" \
        --sector energy --as-of 2026-10-28 [--period 2026-Q4]
    python init_run.py existing_run.json --add        # add missing log / fact skeletons to an existing run

Every entry starts as status "todo"; grade.py blocks until each is set to a final status, so
both runs of the same company search the same items, run the same queries and look for the same facts.
"""
import json, sys, argparse, os
from common import FW, IND_IDS
from retrieval_checks import SPEC, months_before, pdate


def skeleton(company, sector, as_of, extra_registers=()):
    a = pdate(as_of); pack = SPEC["sector_packs"][sector]
    regs = list(pack["registers"]) + list(extra_registers)
    es_from, fs_from = str(months_before(a, SPEC["event_sweep_months"])), str(months_before(a, 36))
    return {
        "items": {it["id"]: {"status": "todo", "name": it["name"], "documents": [], "queries": [], **({"years": []} if it.get("needs_years") else {}),
                             **({"from": fs_from, "to": as_of, "filings_reviewed": None, "feed": " / ".join(pack["filing_feeds"])} if it["id"] == "R4" else {})}
                  for it in SPEC["retrieval_items"]},
        "registers": {r["id"]: {"status": "todo", "name": r["name"], "query": r["query"].format(company=company), "date": None, "hits": [],
                                **({"applies_if": r["applies_if"]} if r.get("applies_if") else {})} for r in regs},
        "event_sweep": {q["id"]: {"query": q["query"].format(company=company), "from": es_from, "to": as_of, "results_reviewed": None, "hits": []}
                        for q in SPEC["event_sweep"]},
    }


def fact_skeleton():
    return {iid: {f: {"status": "todo", "hint": h, "value": "", "evidence": [], "where_searched": ""} for f, h in SPEC["fact_sheet"][iid]} for iid in IND_IDS}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("out"); ap.add_argument("--company"); ap.add_argument("--peer", action="append", default=[])
    ap.add_argument("--sector", default="general"); ap.add_argument("--as-of"); ap.add_argument("--period"); ap.add_argument("--add", action="store_true")
    a = ap.parse_args()
    if a.add:
        run = json.load(open(a.out)); meta = run["run"]
        for s in run["subjects"]:
            sk = skeleton(s["name"], meta["sector"], meta["as_of"], meta.get("extra_registers", [])); log = s.setdefault("retrieval_log", {})
            for k, v in sk.items():
                for kk, vv in v.items(): log.setdefault(k, {}).setdefault(kk, vv)
            fs = s.setdefault("facts", {})
            for iid, flds in fact_skeleton().items():
                for f, v in flds.items(): fs.setdefault(iid, {}).setdefault(f, v)
    else:
        if not (a.company and a.peer and a.as_of): ap.error("--company, at least one --peer and --as-of are required")
        if a.sector not in SPEC["sector_packs"]: ap.error(f"--sector must be one of {list(SPEC['sector_packs'])}")
        if a.sector == "general": print("Note: sector 'general' needs run.extra_registers; add them, then run init_run.py <file> --add")
        def subj(spec, role):
            n, _, t = spec.partition(":")
            return {"name": n, "ticker": t, "role": role, "indicators": {}, "retrieval_log": skeleton(n, a.sector, a.as_of), "facts": fact_skeleton()}
        q = a.period or f"{a.as_of[:4]}-Q{(int(a.as_of[5:7]) - 1) // 3 + 1}"
        run = {"run": {"run_date": a.as_of, "as_of": a.as_of, "period": q, "rule_version": FW["rule_version"], "sector": a.sector, "extra_registers": [], "extra_trade_press": []},
               "user_documents": [], "subjects": [subj(a.company, "company")] + [subj(p, "peer") for p in a.peer],
               "evidence": {}, "coverage": {"documents_unavailable": [], "notes": ""}}
    json.dump(run, open(a.out, "w"), indent=1)
    n = sum(1 for s in run["subjects"] for v in s["retrieval_log"].values() for _ in v) + sum(1 for s in run["subjects"] for i in s["facts"].values() for _ in i)
    print(f"{a.out}: {len(run['subjects'])} subjects, {n} log and fact entries to complete")


if __name__ == "__main__":
    main()

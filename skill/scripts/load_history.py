#!/usr/bin/env python3
"""
load_history.py - ingest prior run files into the current run's "history" block.

Usage:
    python load_history.py current_run.json prior_run_1.json [prior_run_2.json ...]

Each prior file is a run.json produced by this skill (outside-in or inside-out stage; a prior inside-out
file carries both grades and both are kept). The newest four quarters are retained (Rule: max 4).
A prior inside-out file supplies the prior period's actions for status tracking. History entries are
compact: period, stage, simulated flag, dimension grades and averages per lens, overall per lens,
indicator scores per lens, peer dimension grades, and actions.
"""
import json, sys
from common import *


def summarise(prior):
    comp = company_of(prior); c = comp.get("computed") or {}
    lenses = [l for l in ("board", "board_io") if l in (c.get("overall") or {})]
    h = {"period": period_label(prior), "stage": stage_of(prior), "simulated": bool(prior.get("run", {}).get("simulated")),
         "run_date": prior.get("run", {}).get("run_date"), "lenses": lenses,
         "dimensions": {d: {l: {"grade": c["dimensions"][d][l]["grade"], "average": c["dimensions"][d][l]["average"]} for l in lenses} for d in DIMS},
         "overall": {l: {"grade": c["overall"][l].get("grade"), "provisional": c["overall"][l].get("provisional")} for l in lenses},
         "indicators": {i: {l: ((comp["indicators"].get(i) or {}).get(l) or {}).get("score") for l in lenses} for i in IND_IDS},
         "indicator_rationale": {i: {l: ((comp["indicators"].get(i) or {}).get(l) or {}).get("rationale") for l in lenses} for i in IND_IDS},
         "peers": {p["name"]: {d: p["computed"]["dimensions"][d]["board"]["grade"] for d in DIMS} | {"overall": p["computed"]["overall"]["board"].get("grade")} for p in peers_of(prior) if p.get("computed")},
         "actions": prior.get("actions", []),
         "key_metrics": prior.get("key_metrics", [])}
    return h


def main():
    if len(sys.argv) < 3: print(__doc__); sys.exit(2)
    cur = json.load(open(sys.argv[1]))
    hist = [summarise(json.load(open(p))) for p in sys.argv[2:]]
    # keep newest per period (an inside-out file supersedes an outside-in file for the same period)
    by = {}
    for h in hist:
        if h["period"] not in by or h["stage"] == "inside_out": by[h["period"]] = h
    hist = sorted(by.values(), key=lambda h: h["period"])[-FW["max_history_quarters"]:]
    cur["history"] = hist
    write_json(sys.argv[1], cur)
    print("history loaded:", [f"{h['period']} ({h['stage']}{', simulated' if h['simulated'] else ''})" for h in hist])


if __name__ == "__main__":
    main()

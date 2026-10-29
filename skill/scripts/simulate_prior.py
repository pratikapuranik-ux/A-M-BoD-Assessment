#!/usr/bin/env python3
"""
simulate_prior.py - create a simulated prior-quarter outside-in run for prototype testing.

Usage:
    python simulate_prior.py current_run.json out_prior_run.json [--seed 7]

Takes the current graded outside-in run and produces a plausible prior quarter with MINOR movements:
about a quarter of the company's indicator scores shift by one point (either direction), peers shift
less, every evidence item and rationale is marked simulated, three to four prior actions with target
dates and measures are added, and run.simulated = true. Then render it with build_docx.py so the
tester receives a prior report, and load it with load_history.py.
"""
import json, sys, copy, random
from common import *


def main():
    if len(sys.argv) < 3: print(__doc__); sys.exit(2)
    seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 7
    random.seed(seed)
    cur = json.load(open(sys.argv[1])); prior = copy.deepcopy(cur)
    period = period_label(cur); pp = prev_quarter(period)
    prior["run"].update({"period": pp, "stage": "outside_in", "simulated": True, "consistency_run": 1,
                         "run_date": f"{pp[:4]}-{int(pp[-1]) * 3:02d}-28", "note": "SIMULATED prior-quarter run for prototype testing"})
    prior.pop("history", None); prior.pop("prior_actions_status", None); prior.pop("back_on_track", None)
    for s in prior["subjects"]:
        s.pop("computed", None); rate = 0.25 if s["role"] == "company" else 0.12
        for iid, blk in s["indicators"].items():
            for lens in list(blk):
                if lens != "board": blk.pop(lens); continue
                c = blk["board"]
                if c.get("score") is not None and random.random() < rate:
                    delta = random.choice([-1, 1]); ns = max(1, min(5, c["score"] + delta))
                    if ns in (2, 4): ns = c["score"] + 2 * delta if 1 <= c["score"] + 2 * delta <= 5 else c["score"]
                    if ns != c["score"]:
                        c["score"] = ns
                        c["rationale"] = f"[SIMULATED {pp}] " + (c.get("rationale") or "")
                if c.get("score") in (1, 5) and len(c.get("evidence", [])) < 2:
                    c["score"] = 3
        if s["role"] == "company":
            s["assessment_text"] = {d: f"[SIMULATED {pp}] " + v for d, v in (s.get("assessment_text") or {}).items()}
    for e in prior["evidence"].values():
        e["simulated"] = True; e["recent"] = False
        e["document"] = e["document"] + f" [simulated {pp}]"
    prior["headline"] = f"[SIMULATED {pp}] " + (cur.get("headline") or "")
    prior["headline_findings"] = [f"[SIMULATED {pp}] " + f for f in cur.get("headline_findings", [])]
    prior["actions"] = [
        {"id": f"{pp}-A1", "heading": "Add a customer-harm watch list to board packs", "description": "Management to add a standing one-page watch list of key customers actively unhappy or escalating, with status of remediation, to every board pack.", "measures": ["Watch list present in each pack", "Number of key-customer escalations closed within 60 days"], "target_by": f"{period}"},
        {"id": f"{pp}-A2", "heading": "Schedule directors' frontline sessions without management", "description": "Two structured director sessions with customers and frontline staff per year, without management present, with findings minuted.", "measures": ["Sessions held per year", "Findings minuted and actions tracked"], "target_by": f"{period}"},
        {"id": f"{pp}-A3", "heading": "Adopt a stated liquidity trigger framework", "description": "Board to approve early-warning liquidity triggers (headroom, leverage, maturity concentration) that mandate a board discussion when breached.", "measures": ["Framework approved and disclosed", "Quarters with trigger review minuted"], "target_by": f"{period}"},
        {"id": f"{pp}-A4", "heading": "Retire one standing report and one committee workstream", "description": "Governance committee to identify one standing report and one committee workstream that no longer earn their place and retire them.", "measures": ["Items retired", "Board pack page count"], "target_by": f"{period}"}]
    prior["key_metrics"] = [{"metric": "Free cash flow conversion", "why": "Tests whether cash, not EPS, is driving decisions"}, {"metric": "Key-customer escalations open > 60 days", "why": "Leading indicator of customer-harm reaching the board late"}]
    prior["coverage"] = {"documents_unavailable": [], "consistency_result": "Simulated run; no consistency test", "notes": "SIMULATED prior quarter generated for prototype testing. All scores, evidence and actions are synthetic."}
    json.dump(prior, open(sys.argv[2], "w"), indent=1)
    print(f"Simulated prior run written to {sys.argv[2]} (period {pp}). Next: python scripts/grade.py {sys.argv[2]}; python scripts/build_docx.py {sys.argv[2]} '<Company> {pp} Day1-Day2 (SIMULATED).docx'")


if __name__ == "__main__":
    main()

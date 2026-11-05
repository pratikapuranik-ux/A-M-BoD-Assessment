#!/usr/bin/env python3
"""apply_recon.py - apply the user's reconciliation decisions to produce one reconciled run (Rule 19).

Usage:
    python apply_recon.py run_a.json run_b.json recon_plan.json reconciled.json

run_a is the base. For each item in the plan, item["decision"] must be set (by the user) to one of:
    "recommended"   take item["recommendation"], or item["analyst_recommendation"] for judgement items
    "keep_a"        keep the base run's cell
    "adopt_b"       copy run B's cell, the evidence it cites and its fact-sheet entries (evidence ids get a -B suffix)
    "re_research"   clear the cell and mark it pending; grade.py blocks until it is re-researched and scored
plan["decided_by"] records who decided. Synthesis text touched by any change is listed in
run.reconciliation.stale_text; grade.py blocks until it is rewritten and the list emptied.
"""
import json, sys, re, copy, datetime as dt
from common import DIM_OF

CHOICES = {"recommended", "keep_a", "adopt_b", "re_research"}


def key(s): return (s.get("ticker") or s.get("name") or "").upper()


def main():
    if len(sys.argv) < 5: print(__doc__); sys.exit(2)
    pa, pb, pp, out = sys.argv[1:5]
    a, b, plan = json.load(open(pa)), json.load(open(pb)), json.load(open(pp))
    r = copy.deepcopy(a); ev_b = b.get("evidence", {}); ev = r.setdefault("evidence", {})
    S = {key(s): s for s in r["subjects"]}; SB = {key(s): s for s in b["subjects"]}
    errors, decisions, stale = [], [], set(); comp = next(key(s) for s in r["subjects"] if s.get("role") == "company")

    def remap(eid):
        new = f"{eid}-B"
        if eid in ev_b and new not in ev: ev[new] = dict(ev_b[eid], reconciled_from=pb)
        return new

    for it in plan["items"]:
        d = it.get("decision")
        if d not in CHOICES: errors.append(f"{it['id']}: decision {d!r} not one of {sorted(CHOICES)}"); continue
        choice = d
        if d == "recommended":
            choice = it.get("recommendation") or it.get("analyst_recommendation")
            if choice not in ("keep_a", "adopt_b", "re_research"): errors.append(f"{it['id']}: no recommendation to accept (judgement item needs analyst_recommendation)"); continue
        k, iid = key({"ticker": it.get("ticker"), "name": it["subject"]}), it["indicator"]
        s, sb = S.get(k), SB.get(k)
        if not s or not sb: errors.append(f"{it['id']}: subject not in both runs"); continue
        cur = s["indicators"].setdefault(iid, {}).get("board") or {}
        copied = []
        if choice == "adopt_b":
            cb = copy.deepcopy(((sb.get("indicators") or {}).get(iid) or {}).get("board") or {})
            ids = cb.get("evidence") or []
            mp = {e: remap(e) for e in ids}; copied += list(mp.values())
            cb["evidence"] = [mp[e] for e in ids]
            cb["rationale"] = re.sub(r"\[(E[\w-]+)\]", lambda m: f"[{mp.get(m.group(1), m.group(1))}]", cb.get("rationale", ""))
            cb["reconciled"] = {"from": pb, "replaced_score": cur.get("score")}
            s["indicators"][iid]["board"] = cb
            fb = copy.deepcopy(((sb.get("facts") or {}).get(iid)) or {})
            for f, x in fb.items():
                x["evidence"] = [remap(e) for e in x.get("evidence", [])]; copied += x["evidence"]
            if fb: s.setdefault("facts", {})[iid] = fb
        elif choice == "re_research":
            s["indicators"][iid]["board"] = {"score": None, "confidence": None, "evidence": [], "pending_recon": True, "pre_recon": cur,
                                             "rationale": f"Pending re-research after reconciliation: {it.get('reason','')}"}
        if choice != "keep_a":
            dim = DIM_OF[iid]
            if k == comp: stale |= {f"indicator_summary.{iid}", f"assessment_text.{dim}", f"scorecard_evidence.{dim}", f"peer_row_summary.{dim}"}
            else: stale |= {f"{s['name']}.summary", f"peer_row_summary.{dim}", f"peer_paragraphs.{s['name']}"}
        decisions.append({"item": it["id"], "subject": it["subject"], "indicator": iid, "decision": d, "applied": choice,
                          "basis": it.get("basis"), "recommendation": it.get("recommendation") or it.get("analyst_recommendation"),
                          "reason": it.get("analyst_reason") or it.get("reason"), "score_a": it.get("score_a"), "score_b": it.get("score_b"),
                          "evidence_copied": sorted(set(copied))})
    if errors:
        print("Not applied:"); [print("  -", e) for e in errors]; sys.exit(1)
    if any(x["applied"] != "keep_a" for x in decisions):
        stale |= {"headline", "overall_summary", "what_drives", "peer_position"}
    n_b = sum(1 for x in decisions if x["applied"] == "adopt_b"); n_r = sum(1 for x in decisions if x["applied"] == "re_research")
    r["run"]["reconciliation"] = {"base": pa, "other": pb, "date": dt.date.today().isoformat(), "decided_by": plan.get("decided_by", "user"),
                                  "decisions": decisions, "stale_text": sorted(stale)}
    cov = r.setdefault("coverage", {})
    cov["notes"] = (cov.get("notes", "") + f" Reconciled with a second run ({pb}): {n_b} cells adopted from it, {n_r} re-researched, "
                    f"{len(decisions) - n_b - n_r} kept; decisions taken by {plan.get('decided_by', 'user')}.").strip()
    json.dump(r, open(out, "w"), indent=1)
    print(f"{out}: {len(decisions)} decisions ({n_b} adopted from B, {n_r} re-research, {len(decisions) - n_b - n_r} kept)")
    if stale: print("Rewrite before grading, then remove from run.reconciliation.stale_text:\n  " + "\n  ".join(sorted(stale)))
    if n_r: print(f"{n_r} cells pending re-research: grade.py blocks until they are scored or marked not assessable.")


if __name__ == "__main__":
    main()

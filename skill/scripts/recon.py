"""recon.py - shared logic for the reconciliation workflow (Rule 19).

build_plan(run_a, run_b) lists every cell that differs between two runs and attaches a recommendation:
  basis "rule_check"  one run's cell breaks a mechanical rule (evidence minimum, source eligibility,
                      time window) and the other's does not -> adopt the clean cell
  basis "evidence"    one run assessed the cell and the other could not, or one run's fact sheet holds
                      facts for the indicator that the other lacks (and nothing the other lacks) -> adopt
                      the more complete run
  basis "merge"       each run holds facts the other lacks -> re-research recommended
  basis "judgement"   same evidence, different reading of the anchor -> no mechanical answer; the analyst
                      writes a recommendation with reasons and the user decides
Nothing in the plan is applied until the user has chosen (apply_recon.py).
"""
import copy
from common import IND_IDS
import grade as G
import retrieval_checks as RC

PEER_RELATIVE = {"3.2", "5.1", "6.1", "6.2"}


def key(s): return (s.get("ticker") or s.get("name") or "").upper()
def cell(s, iid): return ((s.get("indicators") or {}).get(iid) or {}).get("board") or {}


def cell_issues(run):
    """Map (subject key, indicator) -> rule problems on that cell, including problems on the evidence it cites."""
    r = copy.deepcopy(run); ev = r.get("evidence", {}); out = {}
    by_ev = {}
    for s in r.get("subjects", []):
        for iid in IND_IDS:
            for e in cell(s, iid).get("evidence") or []: by_ev.setdefault(e, []).append((key(s), iid))
    name_key = {s["name"]: key(s) for s in r.get("subjects", [])}
    for s in r.get("subjects", []):
        for iid in IND_IDS:
            p, w = [], []
            if cell(s, iid): G.validate_cell(s["name"], iid, cell(s, iid), ev, p, w)
            if p: out.setdefault((key(s), iid), []).extend(m for _, _, m in p)
    p, w = [], []
    if r.get("run", {}).get("as_of"):
        RC.check_sources(r, p, w); RC.check_windows_and_recent(r, p, w)
    for who, where, msg in p:
        if who == "sources" and where.startswith("evidence "):
            for k in by_ev.get(where.split(" ", 1)[1], []): out.setdefault(k, []).append(f"{where}: {msg}")
        elif who in name_key:
            out.setdefault((name_key[who], where), []).append(msg)
    return out


def found_facts(s, iid):
    return {f: x for f, x in ((s.get("facts") or {}).get(iid) or {}).items() if (x or {}).get("status") == "found"}


def build_plan(a, b, label_a="A", label_b="B"):
    ia, ib = cell_issues(a), cell_issues(b)
    peers_a = sorted(key(s) for s in a["subjects"] if s.get("role") == "peer")
    peers_b = sorted(key(s) for s in b["subjects"] if s.get("role") == "peer")
    skip = PEER_RELATIVE if peers_a != peers_b else set()
    B = {key(s): s for s in b["subjects"]}; items = []
    for sa in a["subjects"]:
        sb = B.get(key(sa))
        if not sb: continue
        k = key(sa)
        for iid in IND_IDS:
            ca, cb = cell(sa, iid), cell(sb, iid)
            if ca.get("score") == cb.get("score"): continue
            it = {"id": f"{k}-{iid}", "subject": sa["name"], "ticker": sa.get("ticker"), "indicator": iid,
                  "score_a": ca.get("score"), "score_b": cb.get("score"),
                  "rationale_a": ca.get("rationale", ""), "rationale_b": cb.get("rationale", ""),
                  "issues_a": ia.get((k, iid), []), "issues_b": ib.get((k, iid), []), "decision": None}
            if iid in skip:
                it.update({"basis": "not_comparable", "recommendation": "keep_a",
                           "reason": "Peer sets differ, so this peer-relative cell is not comparable; keep the base run's cell."})
                items.append(it); continue
            fa, fb = found_facts(sa, iid), found_facts(sb, iid)
            only_a, only_b = sorted(set(fa) - set(fb)), sorted(set(fb) - set(fa))
            it["facts_only_a"], it["facts_only_b"] = only_a, only_b
            if it["issues_a"] and not it["issues_b"]:
                rec, basis, why = "adopt_b", "rule_check", f"Run {label_a}'s cell fails a mechanical rule: " + "; ".join(it["issues_a"][:2])
            elif it["issues_b"] and not it["issues_a"]:
                rec, basis, why = "keep_a", "rule_check", f"Run {label_b}'s cell fails a mechanical rule: " + "; ".join(it["issues_b"][:2])
            elif it["issues_a"] and it["issues_b"]:
                rec, basis, why = "re_research", "rule_check", "Both cells fail mechanical rules; neither can be adopted as it stands."
            elif ca.get("score") is None and cb.get("score") is not None:
                rec, basis, why = "adopt_b", "evidence", f"Run {label_b} met the evidence minimum where run {label_a} marked the cell not assessable."
            elif cb.get("score") is None and ca.get("score") is not None:
                rec, basis, why = "keep_a", "evidence", f"Run {label_a} met the evidence minimum where run {label_b} marked the cell not assessable."
            elif only_b and not only_a:
                rec, basis, why = "adopt_b", "evidence", f"Run {label_b} found facts run {label_a} did not: {', '.join(only_b)}."
            elif only_a and not only_b:
                rec, basis, why = "keep_a", "evidence", f"Run {label_a} found facts run {label_b} did not: {', '.join(only_a)}."
            elif only_a and only_b:
                rec, basis, why = "re_research", "merge", f"Each run holds facts the other lacks ({label_a}: {', '.join(only_a)}; {label_b}: {', '.join(only_b)}); re-research to score on both."
            else:
                rec, basis, why = None, "judgement", "Same facts, different reading of the anchor; no mechanical answer. Analyst to write a recommendation with reasons for the user to decide."
            it.update({"recommendation": rec, "basis": basis, "reason": why})
            items.append(it)
    return {"run_a": label_a, "run_b": label_b, "peer_sets_match": peers_a == peers_b, "items": items}

#!/usr/bin/env python3
"""compare_runs.py - compare two run files of the same assessment (Rule 18 consistency test).

Usage:
    python compare_runs.py run_a.json run_b.json [--out comparison.md] [--record] [--plan recon_plan.json]

Reports, per subject matched by ticker (or name):
  - setup differences (as_of, sector, peer set, rule version) that can explain peer-relative cells
  - indicator scores side by side, flagging gaps of more than one point and assessable/not-assessable flips
  - dimension letters and overall grade changes
  - fact-sheet entries found in one run but not the other, or with different values
  - evidence documents and event-sweep hits present in one run only
Verdict (Rule 18 tolerance): PASS when every common indicator is within one point, no cell flips between
assessed and not assessable, and every dimension letter is unchanged; otherwise REVIEW, with the cells to
re-read listed. --record writes the verdict into run.consistency of both files.
Run-twice is optional (run.consistency.mode = "double"); the script also works on any two runs.
--plan writes a reconciliation plan (recon.py): every differing cell with a recommendation and its basis,
ready for the analyst to complete and the user to decide (Rule 19); apply it with apply_recon.py.
"""
import json, sys, re, datetime as dt
from common import IND_IDS, DIMS, DIM_OF


def key(s): return (s.get("ticker") or s.get("name") or "").upper()
def norm(t): return re.sub(r"[^a-z0-9]+", " ", str(t or "").lower()).strip()
def cell(s, iid): return ((s.get("indicators") or {}).get(iid) or {}).get("board") or {}
def grade(s, d): return (((s.get("computed") or {}).get("dimensions") or {}).get(d) or {}).get("board", {}).get("grade")
def overall(s): return (((s.get("computed") or {}).get("overall") or {}).get("board") or {}).get("grade")


def doc_keys(run, ids):
    ev = run.get("evidence", {}); out = {}
    for e in ids:
        it = ev.get(e)
        if it: out[norm(it.get("url")) or norm(it.get("document"))] = f"{e}: {it.get('document','')[:90]} ({it.get('date','')})"
    return out


def subject_evidence(s):
    ids = set()
    for iid in IND_IDS: ids |= set(cell(s, iid).get("evidence") or [])
    for x in ((s.get("retrieval_log") or {}).get("event_sweep") or {}).values(): ids |= set(x.get("hits") or [])
    for x in ((s.get("retrieval_log") or {}).get("registers") or {}).values(): ids |= set(x.get("hits") or [])
    return ids


def compare(a, b):
    L, flags, ok = [], [], True
    ma, mb = a.get("run", {}), b.get("run", {})
    L.append("## Setup")
    pa = sorted(key(s) for s in a["subjects"] if s.get("role") == "peer"); pb = sorted(key(s) for s in b["subjects"] if s.get("role") == "peer")
    setup = [("as_of", ma.get("as_of") or ma.get("run_date"), mb.get("as_of") or mb.get("run_date")), ("sector", ma.get("sector"), mb.get("sector")),
             ("rule_version", ma.get("rule_version"), mb.get("rule_version")), ("peer set", ", ".join(pa), ", ".join(pb))]
    for k, x, y in setup:
        L.append(f"- {k}: A = {x} | B = {y}" + ("" if x == y else "  **DIFFERS**"))
    if pa != pb: L.append("- Peer sets differ: peer-relative indicators (3.2, 5.1, 6.1, 6.2) are not comparable and are excluded from the verdict.")
    peer_rel = {"3.2", "5.1", "6.1", "6.2"} if pa != pb else set()
    B = {key(s): s for s in b["subjects"]}
    for sa in a["subjects"]:
        sb = B.get(key(sa))
        if not sb: L.append(f"\n## {sa['name']}\nIn run A only."); continue
        L.append(f"\n## {sa['name']} ({sa.get('role')})\n\n| Indicator | A | B | Gap | Flag |\n|---|---|---|---|---|")
        for iid in IND_IDS:
            x, y = cell(sa, iid).get("score"), cell(sb, iid).get("score")
            if x == y: continue
            gap = "" if x is None or y is None else abs(x - y)
            flag = "assessable vs not assessable" if (x is None) != (y is None) else (">1 point" if gap and gap > 1 else "")
            excluded = iid in peer_rel
            if flag and not excluded: ok = False; flags.append(f"{sa['name']} {iid}: {flag}")
            L.append(f"| {iid} | {x if x is not None else 'n/a'} | {y if y is not None else 'n/a'} | {gap} | {flag}{' (peer set differs)' if excluded else ''} |")
        for d in DIMS:
            ga, gb = grade(sa, d), grade(sb, d)
            if ga != gb:
                drivers = [i for i in IND_IDS if DIM_OF[i] == d and cell(sa, i).get("score") != cell(sb, i).get("score")]
                peer_only = bool(drivers) and all(i in peer_rel for i in drivers)
                if not peer_only: ok = False; flags.append(f"{sa['name']} dimension {d}: {ga} vs {gb}")
                L.append(f"\nDimension {d}: A = {ga}, B = {gb} (cells that differ: {', '.join(drivers) or 'none'})" + (" - peer-relative cells only, excluded" if peer_only else ""))
        if overall(sa) != overall(sb): L.append(f"\nOverall: A = {overall(sa)}, B = {overall(sb)}")
        # facts
        fa, fb = sa.get("facts") or {}, sb.get("facts") or {}; rows = []
        for iid in IND_IDS:
            for f in sorted(set(fa.get(iid, {})) | set(fb.get(iid, {}))):
                x, y = fa.get(iid, {}).get(f) or {}, fb.get(iid, {}).get(f) or {}
                sx, sy = x.get("status"), y.get("status")
                if sx == sy == "found" and norm(x.get("value")) != norm(y.get("value")): rows.append((iid, f, "values differ", x.get("value"), y.get("value")))
                elif sx != sy and "found" in (sx, sy): rows.append((iid, f, "found in " + ("A" if sx == "found" else "B") + " only", x.get("value") or sx, y.get("value") or sy))
        if rows:
            L.append("\n**Fact-sheet differences** (re-read the source for each)\n\n| Indicator | Fact | Difference | A | B |\n|---|---|---|---|---|")
            for r in rows: L.append("| " + " | ".join(str(c)[:140].replace("|", "/") for c in r) + " |")
        da, db = doc_keys(a, subject_evidence(sa)), doc_keys(b, subject_evidence(sb))
        only_a, only_b = [da[k] for k in da if k not in db], [db[k] for k in db if k not in da]
        if only_a or only_b:
            L.append("\n**Evidence in one run only**")
            for t in only_a[:40]: L.append(f"- A only: {t}")
            for t in only_b[:40]: L.append(f"- B only: {t}")
    verdict = "PASS" if ok else "REVIEW"
    head = [f"# Consistency comparison: {verdict}", "", "Tolerance (Rule 18): every indicator within one point, no assessable / not-assessable flip, dimension letters unchanged.", ""]
    if flags: head += ["Cells to re-read against the fact sheet before either result stands:", ""] + [f"- {f}" for f in flags] + [""]
    return verdict, flags, "\n".join(head + L)


def main():
    if len(sys.argv) < 3: print(__doc__); sys.exit(2)
    pa, pb = sys.argv[1], sys.argv[2]; a, b = json.load(open(pa)), json.load(open(pb))
    verdict, flags, md = compare(a, b)
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None
    if out: open(out, "w").write(md); print(f"Comparison written to {out}")
    else: print(md)
    if "--plan" in sys.argv:
        from recon import build_plan
        pp = sys.argv[sys.argv.index("--plan") + 1]; import os; plan = build_plan(a, b, os.path.basename(pa), os.path.basename(pb))
        json.dump(plan, open(pp, "w"), indent=1)
        n = {}
        for it in plan["items"]: n[it["basis"]] = n.get(it["basis"], 0) + 1
        print(f"Reconciliation plan written to {pp}: {len(plan['items'])} cells " + str(n))
    if "--record" in sys.argv:
        stamp = dt.date.today().isoformat()
        for p, r, other in ((pa, a, pb), (pb, b, pa)):
            r.setdefault("run", {}).setdefault("consistency", {}).update({"compared_with": other, "verdict": verdict, "flags": flags, "date": stamp})
            json.dump(r, open(p, "w"), indent=1)
    print(f"\nVerdict: {verdict} ({len(flags)} flags)")


if __name__ == "__main__":
    main()

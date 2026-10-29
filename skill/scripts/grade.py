#!/usr/bin/env python3
"""
grade.py (rules v1.2, board-only) - compute grades from a run JSON and validate the scoring rules.

Usage:
    python grade.py run.json            # validate, compute, write "computed" back into run.json
    python grade.py run.json --check    # validate only

Stage-aware: an outside-in run scores the "board" cell of every indicator; an inside-out run keeps the
outside-in "board" cell untouched and adds a "board_io" cell (post inside-out). Both are graded and the
outputs show them side by side. Peers are never re-scored in the inside-out stage.
Enforces rules 2-7, 10, 16 and Part D (inside-out evidence) mechanically; exit 1 on blocking violations.
"""
import json, sys
from common import *

STRONG = set(FW["strong_classes"]); WEAK = {"searched_record", "silence"}
CAPPED = dict(FW["silence_capped"]); CAPPED.update(FW["searched_record_capped"])


def validate_cell(name, iid, lens, cell, evidence, problems, warnings, stage):
    where = f"{iid}/{lens}"
    if cell is None or cell.get("score") is None:
        if (cell or {}).get("na_cause") not in FW["na_causes"]:
            problems.append((name, where, f"not assessable: na_cause must be one of {FW['na_causes']}"))
        if not ((cell or {}).get("rationale") or "").strip():
            problems.append((name, where, "not assessable: rationale must list what was searched (Rule 15)"))
        return
    s = cell["score"]
    if s not in (1, 2, 3, 4, 5):
        problems.append((name, where, f"score {s!r} is not an integer 1-5")); return
    ev = cell.get("evidence", []) or []
    missing = [e for e in ev if e not in evidence]
    if missing:
        problems.append((name, where, f"evidence ids not in evidence list: {missing}")); return
    items = [evidence[e] for e in ev]; classes = [it.get("evidence_class", "direct") for it in items]
    bad = [c for c in classes if c not in FW["evidence_classes"]]
    if bad: problems.append((name, where, f"unknown evidence_class {bad}"))
    if lens == "board_io":
        io = [c for c in classes if c in ("inside_out", "self_assessment")]
        if not io and not cell.get("carried_forward"): problems.append((name, where, "post inside-out score must cite at least one inside_out or self_assessment item, or set carried_forward: true with the outside-in score unchanged"))
        if classes and all(c == "self_assessment" for c in classes) and cell.get("confidence") == "High":
            problems.append((name, where, "self-assessment-only cell cannot be High confidence (Part D)"))
    else:
        if any(c in ("inside_out", "self_assessment") for c in classes):
            problems.append((name, where, "outside-in cell may not cite inside_out or self_assessment evidence"))
    docs = {it.get("document", e) for it, e in zip(items, ev)}
    strong = any(c in STRONG or c == "inside_out" for c in classes)
    if s in (1, 5) and not strong and (len(ev) < 2 or len(docs) < 2):
        problems.append((name, where, f"score {s} needs >=2 items from >=2 documents or one strong item (has {len(ev)}/{len(docs)})"))
    if s in (2, 3, 4) and len(ev) < 1: problems.append((name, where, f"score {s} needs >=1 evidence item"))
    if s in (2, 4) and not (cell.get("rationale") or "").strip(): problems.append((name, where, f"score {s} requires a rationale naming the parts of both anchors met"))
    if not (cell.get("rationale") or "").strip(): warnings.append((name, where, "rationale is empty; outputs show rationale, not raw evidence"))
    only_weak = bool(classes) and all(c in WEAK for c in classes)
    if only_weak:
        if iid in CAPPED and s > CAPPED[iid]: problems.append((name, where, f"only silence/searched-record evidence: score capped at {CAPPED[iid]}"))
        elif iid not in CAPPED and iid not in FW["silence_full"]: problems.append((name, where, "silence/searched-record evidence is not scorable for this indicator"))
        if cell.get("confidence") != "Low": problems.append((name, where, "silence/searched-record-only cell must be Low confidence"))
    for it in items:
        if it.get("evidence_class") == "searched_record" and not it.get("search_log"): problems.append((name, where, "searched_record item needs search_log"))
    conf = cell.get("confidence")
    if conf not in ("High", "Medium", "Low"): problems.append((name, where, "confidence must be High, Medium or Low"))
    elif conf == "High":
        direct = sum(1 for c in classes if c in ("direct", "strong_direct", "board_act", "inside_out"))
        if not (direct >= 2 or strong): warnings.append((name, where, "High confidence needs >=2 direct items or one strong item"))


def validate_subject(subj, evidence, lenses, problems, warnings, stage):
    name = subj.get("name", "?"); inds = subj.get("indicators", {})
    use = lenses if subj.get("role") == "company" else ["board"]
    for iid in IND_IDS:
        if iid not in inds: problems.append((name, iid, "missing indicator block")); continue
        for lens in use:
            validate_cell(name, iid, lens, inds[iid].get(lens), evidence, problems, warnings, stage)
    for a, b in FW["scoped_pairs"]:
        for lens in use:
            ea = set((inds.get(a, {}).get(lens) or {}).get("evidence", []) or []); eb = set((inds.get(b, {}).get(lens) or {}).get("evidence", []) or [])
            if ea & eb: problems.append((name, f"{a}/{b} ({lens})", f"evidence {sorted(ea & eb)} primary in both indicators of a scoped pair"))


def compute_subject(subj, lenses, stage):
    inds = subj.get("indicators", {}); out = {"dimensions": {}, "overall": {}, "coverage": {}}
    use = lenses if subj.get("role") == "company" else ["board"]
    for lens in use:
        thr = FW["coverage_threshold"]["inside_out" if lens == "board_io" else "outside_in"]
        for d in DIMS:
            ids = [i for i in IND_IDS if DIM_OF[i] == d]
            scores = [((inds.get(i) or {}).get(lens) or {}).get("score") for i in ids]; scores = [s for s in scores if s is not None]
            n, m = len(scores), len(ids); rec = {"assessed": n, "of": m}
            if n > 0 and meets(n, m, thr):
                avg = sum(scores) / n; g, label = to_grade(avg)
                rec.update({"average": round(avg, 2), "grade": g, "label": label, "reported": True})
            else:
                rec.update({"average": None, "grade": None, "label": "Insufficient evidence", "reported": False})
            out["dimensions"].setdefault(d, {})[lens] = rec
        letters = [out["dimensions"][d][lens]["grade"] for d in DIMS if out["dimensions"][d][lens]["reported"]]
        o = {"dimensions_reported": len(letters), "provisional": False}
        if len(letters) >= 3:
            avg = sum(LV[l] for l in letters) / len(letters); r = round_midpoint_down(avg)
            o.update({"grade": VL[r], "numeric_average": round(avg, 2), "provisional": len(letters) == 3, "label": next(b["label"] for b in FW["grade_scale"] if b["grade"] == VL[r])})
        else:
            o.update({"grade": None, "numeric_average": None, "label": "No overall grade (fewer than 3 dimensions reported)"})
        out["overall"][lens] = o
        cells = [((inds.get(i) or {}).get(lens) or {}) for i in IND_IDS]
        split = {k: 0 for k in FW["na_causes"]}; split["unspecified"] = 0
        for c in cells:
            if c.get("score") is None: split[c.get("na_cause") if c.get("na_cause") in split else "unspecified"] += 1
        out["coverage"][lens] = {"assessed": sum(1 for c in cells if c.get("score") is not None), "of": len(IND_IDS), "not_assessable": split}
    return out


def main():
    if len(sys.argv) < 2: print(__doc__); sys.exit(2)
    path = sys.argv[1]; check_only = "--check" in sys.argv
    run = json.load(open(path)); evidence = run.get("evidence", {}); problems, warnings = [], []
    meta = run.get("run", {}); stage = stage_of(run)
    if stage not in FW["stages"]: problems.append(("run", "run.stage", f"must be one of {list(FW['stages'])}"))
    if meta.get("mode") not in FW["run_modes"]: problems.append(("run", "run.mode", f"must be one of {list(FW['run_modes'])}"))
    if str(meta.get("rule_version")) != str(FW["rule_version"]): problems.append(("run", "run.rule_version", f"must be {FW['rule_version']}"))
    if not meta.get("period") or "-Q" not in str(meta.get("period")): problems.append(("run", "run.period", "must be set as YYYY-Qn"))
    lenses, labels = lenses_for(run); subs = run.get("subjects", [])
    if sum(1 for s in subs if s.get("role") == "company") != 1: problems.append(("run", "subjects", "exactly one subject must have role 'company'"))
    peers = peers_of(run)
    if not (2 <= len(peers) <= FW["max_peers"]): problems.append(("run", "peers", f"peer set should be 2-{FW['max_peers']} listed peers (has {len(peers)})"))
    for a in run.get("actions", []):
        if not a.get("heading") or not a.get("description"): problems.append(("run", "actions", "each action needs heading and description"))
        if not a.get("target_by"): warnings.append(("run", f"action '{a.get('heading','')[:30]}'", "no target_by; status cannot be tracked next quarter"))
    if len(run.get("actions", [])) > 5: problems.append(("run", "actions", "maximum five actions"))
    for pa in run.get("prior_actions_status", []):
        if pa.get("status") not in FW["action_statuses"]: problems.append(("run", "prior_actions_status", f"status must be one of {FW['action_statuses']}"))
    for s in subs:
        validate_subject(s, evidence, lenses, problems, warnings, stage); s["computed"] = compute_subject(s, lenses, stage)
    # history consistency
    for h in run.get("history", []):
        if h.get("period") == meta.get("period"): problems.append(("run", "history", "history contains the current period"))
    print(f"\n=== GRADES (rules v{FW['rule_version']}, stage {stage}, period {meta.get('period')}) ===")
    for s in subs:
        c = s["computed"]; use = lenses if s["role"] == "company" else ["board"]
        print(f"\n{s['name']} ({s['role']})  " + "  ".join(f"{labels[l]}: {c['coverage'][l]['assessed']}/{c['coverage'][l]['of']}" for l in use))
        for d in DIMS: print(f"  {d:<4}" + "".join(f"{(c['dimensions'][d][l]['grade'] or '-')} (avg {c['dimensions'][d][l]['average']})".ljust(22) for l in use))
        print("  Overall: " + " | ".join(f"{labels[l]} {c['overall'][l].get('grade') or '-'}{' (prov.)' if c['overall'][l]['provisional'] else ''}" for l in use))
    print(f"\n=== RULE CHECK: {len(problems)} blocking, {len(warnings)} warnings ===")
    for w in problems: print("  BLOCK [%s] %s: %s" % w)
    for w in warnings: print("  WARN  [%s] %s: %s" % w)
    if not check_only: write_json(path, run); print(f"\nComputed grades written to {path}")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()

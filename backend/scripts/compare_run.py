"""Compare an assessment the app produced with a reference built with the skill (a dashboard HTML, or a run.json).

    python scripts/compare_run.py <reference.html|run.json> <company-id>        # an assessment stored by the app (outside-in run)
    python scripts/compare_run.py <reference.html|run.json> <other.html|run.json>

Prints, per company, every indicator where the two disagree (reference score, app score, difference), then the exact-match rate, the mean
absolute difference, the dimension grades side by side, and how each run cited its evidence: items from supplied documents against the web,
how many distinct supplied documents were cited, and the labels used. Nothing is written.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def load(src: str) -> dict:
    p = Path(src)
    if p.is_file() and p.suffix.lower() in (".html", ".htm"):
        t = p.read_text(encoding="utf-8", errors="replace"); i = t.index("const RUN=") + len("const RUN=")
        return json.JSONDecoder().raw_decode(t[i:])[0]
    if p.is_file(): return json.loads(p.read_text(encoding="utf-8"))
    from app.services import repo
    run = repo.read_run(src, "outside_in")
    if not run: raise SystemExit(f"No outside-in run found for '{src}'.")
    return run


def norm(n: str) -> str:
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\b(inc|corp|corporation|plc|ltd|limited|group|company|holdings|international|the)\b", "", (n or "").lower()))


def match(a: list[dict], b: list[dict]):
    for s in a:
        k = norm(s["name"])
        t = next((x for x in b if norm(x["name"]) == k or (len(k) > 3 and (k in norm(x["name"]) or norm(x["name"]) in k))), None)
        yield s, t


def score(s: dict, i: str):
    c = ((s.get("indicators") or {}).get(i) or {}).get("board") or {}
    return c.get("score")


def grades(s: dict) -> dict:
    d = ((s.get("computed") or {}).get("dimensions")) or {}
    return {k: (v.get("board") or {}).get("grade") for k, v in d.items()}


def citations(run: dict, s: dict) -> Counter:
    ev = run.get("evidence") or {}; c: Counter = Counter(); docs: set = set()
    codes = {e for ind in (s.get("indicators") or {}).values() for e in ((ind.get("board") or {}).get("evidence") or [])}
    for k in codes:
        e = ev.get(k) or {}; url = e.get("url") or ""
        supplied = e.get("source_origin") in ("provided", "user_public") or url.lower().startswith(("provided:", "uploaded:"))
        c["supplied" if supplied else "web"] += 1
        if supplied: docs.add(re.sub(r"^(provided|uploaded):\s*", "", url, flags=re.I) or e.get("document", ""))
    c["distinct supplied documents"] = len(docs)
    return c, sorted(docs)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__); return 2
    ref, new = load(argv[0]), load(argv[1])
    ids = sorted({i for s in ref["subjects"] for i in (s.get("indicators") or {})}, key=lambda x: [int(p) for p in x.split(".")])
    tot = same = 0; absd = 0.0
    for s, t in match(ref["subjects"], new["subjects"]):
        print(f"\n=== {s['name']} ({s['role']})" + ("" if t else "  : not found in the app's run"))
        if not t: continue
        for i in ids:
            a, b = score(s, i), score(t, i)
            if a is None and b is None: continue
            tot += 1; same += a == b
            if a is not None and b is not None: absd += abs(a - b)
            if a != b: print(f"  {i:4} skill {a if a is not None else 'n/a'}  app {b if b is not None else 'n/a'}  diff {('' if a is None or b is None else b - a)}")
        ga, gb = grades(s), grades(t)
        print("  dimension grades (skill / app): " + "  ".join(f"{k}:{ga.get(k) or '-'}/{gb.get(k) or '-'}" for k in sorted(ga)))
        for label, run, sub in (("skill", ref, s), ("app  ", new, t)):
            c, docs = citations(run, sub)
            print(f"  evidence cited, {label}: supplied documents {c['supplied']}, web {c['web']}, distinct supplied documents {c['distinct supplied documents']}")
            if sub["role"] == "company" and docs: print("      " + "; ".join(docs[:12]) + (" ..." if len(docs) > 12 else ""))
    if tot: print(f"\nIndicator scores compared: {tot}; identical {same} ({same / tot:.0%}); mean absolute difference {absd / tot:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

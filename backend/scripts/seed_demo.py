"""Attach demo extras to the EXISTING `chevron` company: one earlier-quarter prior and three director survey responses.

    cd backend; .\\.venv\\Scripts\\python.exe scripts\\seed_demo.py [--dry-run] [--base http://127.0.0.1:8000]

Never imports, replaces, deletes or edits chevron or its stage runs. Safe to re-run: it only adds what is missing.
The prior keeps its simulated labelling (run.simulated and the "[SIMULATED 2026-Q3]" text), so reports show it as simulated.
Responses are generic board-governance prose posted through the survey API (no invite tokens consumed).
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db import session_scope  # noqa: E402
from app.models import PriorRun  # noqa: E402
from app.services import repo  # noqa: E402

CID, WANT = "chevron", 3
PRIOR = ROOT / "tests" / "fixtures" / "prior_2026-Q3_simulated_run.json"

THEMES = [
    "board agenda time", "strategy oversight", "risk escalation", "director onboarding", "committee reporting", "succession planning",
    "capital allocation challenge", "management information quality", "shareholder engagement", "conflicts handling", "culture signals", "evaluation follow-up",
]
RESPONSES = [
    ("The board is engaged and well prepared, though papers often arrive late", [4, 3, 4, 3, 4, 3]),
    ("Discussion is open but dominated by a few voices; follow-up on decisions is uneven", [3, 3, 2, 4, 3, 3]),
    ("Committees do solid work; the full board sometimes re-opens matters already settled", [4, 4, 3, 2, 3, 4]),
]


def responses() -> list[dict]:
    out = []
    for i, (lead, ratings) in enumerate(RESPONSES):
        answers = {str(k): f"{lead}. On {THEMES[k - 1]}, my view {i + 1}: " + ["it works reasonably but could be sharper", "we need clearer ownership and timelines", "practice is sound, evidence of follow-through is thin"][(i + k) % 3] + "." for k in range(1, 13)}
        out.append({"answers": answers, "ratings": {str(d): r for d, r in enumerate(ratings, 1)}})
    return out


def call(base: str, method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(base.rstrip("/") + path, method=method, data=json.dumps(body).encode() if body is not None else None, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)
    except urllib.error.HTTPError as e: raise SystemExit(f"{method} {path} failed: {e.code} {e.read().decode()[:300]}")
    except urllib.error.URLError as e: raise SystemExit(f"cannot reach the backend at {base}: {e.reason}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="say what would be added; change nothing")
    ap.add_argument("--prior-only", action="store_true", help="add the earlier-quarter prior and rebuild the reports; skip the survey responses")
    ap.add_argument("--rebuild", action="store_true", help="rebuild the reports from the priors already on file")
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    a = ap.parse_args()
    tag = "[dry run] " if a.dry_run else ""

    if not repo.exists(CID): raise SystemExit(f"company '{CID}' does not exist yet. Finish the real research run first; this script never creates it.")
    oi = repo.read_run(CID, "outside_in")
    current = ((oi or {}).get("run") or {}).get("period") or ""
    prior = json.load(open(PRIOR, encoding="utf-8"))
    pp = str(prior["run"]["period"]); key = repo._prior_key(prior)
    have = {str(p.get("run", {}).get("period")) for p in repo.priors(CID)}

    if pp in have: print(f"{tag}prior {pp}: already on file, left as is")
    elif not current or pp >= current: print(f"{tag}prior {pp}: skipped, not earlier than {CID}'s current period '{current}'")
    else:
        print(f"{tag}prior {pp}: adding (simulated labelling kept)")
        if not a.dry_run:
            with session_scope() as s: s.add(PriorRun(company_id=CID, period=key, run=copy.deepcopy(prior)))
    if not a.dry_run and (a.rebuild or pp not in have):  # load the priors into the stored runs as history and re-render the reports, so the trend shows in the Word report; no research is run
        from app.services import runs
        runs.prepare(CID); runs.build_all(CID, {"oi", "io"})
        print(f"{tag}reports rebuilt with the trend")
    if a.prior_only: return print(f"{tag}done (prior only).")

    n = call(a.base, "GET", f"/api/companies/{CID}/survey")["responses"]
    need = max(0, WANT - n)
    print(f"{tag}survey responses: {n} on file, adding {need}")
    if need and 0 < n < WANT and not a.dry_run: print("  note: topping up to three from a partial set")
    for r in responses()[n:n + need] if need else []:
        if a.dry_run: continue
        st = call(a.base, "POST", f"/api/companies/{CID}/survey/responses", r)
        print(f"  added; responses now {st['responses']}")
    print(f"{tag}done. chevron's stage runs were not touched.")


if __name__ == "__main__":
    main()

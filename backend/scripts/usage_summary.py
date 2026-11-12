"""Totals storage/logs/usage.jsonl per job (one research or inside-out run) and estimates its cost.

    python scripts/usage_summary.py                 all jobs
    python scripts/usage_summary.py --job b1638fb39e8d
    python scripts/usage_summary.py --since "2026-11-06 09:00"
    python scripts/usage_summary.py --prices my_prices.json

Prices are USD per million tokens and are an ESTIMATE: check them against the Anthropic price list before you quote them.
Cache reads are priced at 10% of input and cache writes at 2x input (the app caches for one hour); web search at USD 10 per 1,000
searches. A file given with --prices overrides any of these: {"models": {"claude-opus-5": {"in": 5, "out": 25}}, "search_per_1000": 10}.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

PRICES = {"claude-opus-5": (5.0, 25.0), "claude-opus-5-5": (4.0, 20.0), "claude-sonnet-5": (2.0, 10.0), "claude-sonnet-5-5": (2.0, 10.0)}
CACHE_READ, CACHE_WRITE, SEARCH_PER_1000 = 0.10, 2.0, 10.0
FIELDS = ("input", "cache_read", "cache_write", "output", "web_search", "web_fetch", "calls")


def ledger() -> Path:
    root = os.environ.get("BOARD_STORAGE_DIR") or str(Path(__file__).resolve().parents[1] / "storage")
    return Path(root) / "logs" / "usage.jsonl"


def cost(row: dict, prices: dict, search: float) -> float:
    p_in, p_out = prices.get(row["model"], prices.get("_default", (5.0, 25.0)))
    return (row["input"] * p_in + row["cache_read"] * p_in * CACHE_READ + row["cache_write"] * p_in * CACHE_WRITE + row["output"] * p_out) / 1e6 \
        + row["web_search"] * search / 1000


def kind(step: str) -> str:
    s = step.lower()
    for key, name in (("fact sheet", "fact sheets"), ("condens", "condensing"), ("reconcil", "reconciliation"), ("audit", "audit"),
                      ("ocr", "ocr / scans"), ("read", "document reading")):
        if key in s: return name
    return "research and write-up"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--job"); ap.add_argument("--since"); ap.add_argument("--file"); ap.add_argument("--prices")
    a = ap.parse_args()
    prices = dict(PRICES); search = SEARCH_PER_1000
    if a.prices:
        extra = json.loads(Path(a.prices).read_text(encoding="utf-8"))
        prices.update({k: (v["in"], v["out"]) for k, v in extra.get("models", {}).items()}); search = extra.get("search_per_1000", search)
    f = Path(a.file) if a.file else ledger()
    if not f.exists(): print(f"No ledger at {f}. Run an assessment first."); return 1
    rows = [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
    rows = [r for r in rows if (not a.job or r["job"] == a.job) and (not a.since or r["ts"] >= a.since)]
    if not rows: print("No matching calls."); return 1
    jobs: dict[str, list[dict]] = defaultdict(list)
    for r in rows: jobs[r["job"] or "(no job)"].append(r)
    grand = 0.0
    for job, rs in jobs.items():
        runs = sorted({r["runs"] for r in rs}); tot = defaultdict(float); by_model = defaultdict(lambda: defaultdict(float)); by_kind = defaultdict(float)
        for r in rs:
            c = cost(r, prices, search); tot["cost"] += c; by_kind[kind(r["step"])] += c
            for k in FIELDS[:-1]: tot[k] += r[k]; by_model[r["model"]][k] += r[k]
            by_model[r["model"]]["calls"] += 1; by_model[r["model"]]["cost"] += c
        billed_in = tot["input"] + tot["cache_read"] + tot["cache_write"]
        print(f"\nJob {job}   {rs[0]['ts']} to {rs[-1]['ts']}   consistency runs: {'/'.join(map(str, runs))}   model calls: {len(rs)}")
        print(f"  tokens: input {tot['input']:,.0f}  cache read {tot['cache_read']:,.0f}  cache write {tot['cache_write']:,.0f}  output {tot['output']:,.0f}")
        print(f"  all input tokens {billed_in:,.0f}, of which read from cache {tot['cache_read'] / billed_in:.0%}" if billed_in else "  no input tokens")
        print(f"  web searches {tot['web_search']:,.0f}   web fetches {tot['web_fetch']:,.0f}")
        for m, v in by_model.items():
            print(f"    {m}: {v['calls']:.0f} calls, in {v['input']:,.0f} / cache read {v['cache_read']:,.0f} / cache write {v['cache_write']:,.0f} / out {v['output']:,.0f}  ~ ${v['cost']:,.2f}")
        for k, v in sorted(by_kind.items(), key=lambda kv: -kv[1]): print(f"    {k}: ~ ${v:,.2f}")
        print(f"  ESTIMATED COST ~ ${tot['cost']:,.2f}"); grand += tot["cost"]
    if len(jobs) > 1: print(f"\nAll jobs ~ ${grand:,.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

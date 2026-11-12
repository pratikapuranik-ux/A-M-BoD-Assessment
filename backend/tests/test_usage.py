"""The token ledger: rows carry the job mark, also from worker threads, and the summary totals them."""
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace as NS

from app.services import storage, usage


def _ledger() -> Path:
    return storage.root() / "logs" / "usage.jsonl"


def _rows() -> list[dict]:
    return [json.loads(x) for x in _ledger().read_text(encoding="utf-8").splitlines()] if _ledger().exists() else []


def _u(**kw):
    base = dict(input_tokens=10, output_tokens=5, cache_read_input_tokens=100, cache_creation_input_tokens=20,
                server_tool_use=NS(web_search_requests=3, web_fetch_requests=1))
    return NS(**{**base, **kw})


def test_record_writes_one_row_with_job_and_counts():
    _ledger().unlink(missing_ok=True)
    usage.scope("job1"); usage.record("Chevron research", "claude-opus-5", _u())
    r = _rows()[-1]
    assert (r["job"], r["step"], r["model"]) == ("job1", "Chevron research", "claude-opus-5")
    assert (r["input"], r["cache_read"], r["cache_write"], r["output"], r["web_search"], r["web_fetch"]) == (10, 100, 20, 5, 3, 1)


def test_pool_keeps_the_job_mark_in_worker_threads():
    _ledger().unlink(missing_ok=True)
    usage.scope("job2")
    with usage.Pool(max_workers=2) as pool:
        list(pool.map(lambda i: usage.record(f"s{i}", "claude-sonnet-5", _u()), range(3)))
    assert [r["job"] for r in _rows()] == ["job2"] * 3


def test_record_never_raises_without_usage():
    usage.record("x", None, None)


def test_summary_totals_a_job():
    _ledger().unlink(missing_ok=True)
    usage.scope("job3"); usage.record("fact sheet for A", "claude-sonnet-5", _u()); usage.record("Chevron research", "claude-opus-5", _u())
    out = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[1] / "scripts" / "usage_summary.py"), "--file", str(_ledger()), "--job", "job3"],
                         capture_output=True, text=True)
    assert out.returncode == 0 and "model calls: 2" in out.stdout and "ESTIMATED COST" in out.stdout and "web searches 6" in out.stdout


def test_schema_rejection_wordings_fall_back_to_plain_tools():
    from app.agents.conversation import schema_too_big
    assert schema_too_big("The compiled grammar is too large, which would cause performance issues. Simplify your tool schemas or reduce the number of strict tools.")
    assert schema_too_big("Schema is too complex for compilation") and not schema_too_big("prompt is too long")


def test_context_tokens_uses_the_last_iteration_not_the_billing_total():
    from app.agents.conversation import context_tokens
    it = lambda n: NS(type="message", input_tokens=1, cache_read_input_tokens=n, cache_creation_input_tokens=0)
    assert context_tokens(NS(iterations=[it(100), it(200), it(300)], input_tokens=3, cache_read_input_tokens=600, cache_creation_input_tokens=0)) == 301
    # no per-iteration figures: 4 searches, totals 1,000,000 over 5 iterations from a 100,000 start -> about 300,000 at the end
    u = NS(input_tokens=0, cache_read_input_tokens=1_000_000, cache_creation_input_tokens=0, server_tool_use=NS(web_search_requests=4, web_fetch_requests=0))
    assert context_tokens(u, 100_000) == 300_000
    assert context_tokens(NS(input_tokens=5, cache_read_input_tokens=50, cache_creation_input_tokens=5)) == 60


def test_old_search_results_are_trimmed_but_stay_valid():
    from app.agents.conversation import Conv, trim_search
    res = lambda n: {"type": "web_search_tool_result", "tool_use_id": f"t{n}", "content": [{"type": "web_search_result", "url": f"u{k}", "title": "t", "encrypted_content": "x" * 50} for k in range(10)]}
    c = Conv("t", [], "start"); c.messages += [{"role": "assistant", "content": [res(n)]} for n in range(6)]
    assert c.prune_searches(2) == 4
    lens = [len(m["content"][0]["content"]) for m in c.messages[1:]]
    assert lens == [3, 3, 3, 3, 10, 10] and c.prune_searches(2) == 0
    assert trim_search({"type": "text"}) == {"type": "text"}

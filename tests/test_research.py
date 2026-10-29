"""Control-flow tests for server/research.py with a scripted fake Anthropic client (no network, no API key).

Run from the project root:  python -m pytest tests/test_research.py -q
"""
import base64, copy, json, re, sys, threading
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from server import research as R  # noqa: E402

EX = json.loads((ROOT / "skill" / "example_runs" / "outside_in_run.json").read_text(encoding="utf-8"))
COMPANY, PEERS = EX["subjects"][0], EX["subjects"][1:]
PEER_ARGS = [{"name": p["name"], "ticker": p["ticker"]} for p in PEERS]
PREFIX = {"E": COMPANY, "X": PEERS[0], "B": PEERS[1]}


# ---------------------------------------------------------------- fake SDK objects

def usage(): return NS(input_tokens=10, output_tokens=10, cache_read_input_tokens=0, cache_creation_input_tokens=0)
def msg(content, stop="tool_use", details=None): return NS(content=content, stop_reason=stop, stop_details=details, usage=usage())
def tool_use(name, inp, tid="toolu_1"): return NS(type="tool_use", id=tid, name=name, input=inp)


class FakeStream:
    def __init__(self, m): self.m = m
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def __iter__(self): return iter(NS(type="content_block_stop", content_block=b) for b in self.m.content)
    def get_final_message(self): return self.m


class FakeClient:
    """Routes each request to `model(kw)`, which returns the next message for that conversation."""

    def __init__(self, model):
        self.model, self.calls, self.lock = model, [], threading.Lock()
        self.beta = NS(messages=NS(stream=self.stream))

    def stream(self, **kw):
        with self.lock: self.calls.append({**kw, "messages": copy.deepcopy(kw["messages"])})
        return FakeStream(self.model(kw))


def tools_of(kw): return [t["name"] for t in kw["tools"]]
def first_text(kw):
    c = kw["messages"][0]["content"]
    return c if isinstance(c, str) else "\n".join(b.get("text", "") for b in c if b.get("type") == "text")
def last(kw): return kw["messages"][-1]
def last_text(kw):
    c = last(kw)["content"]
    return c if isinstance(c, str) else "\n".join(str(b.get("content", "")) for b in c)


# ---------------------------------------------------------------- submissions built from the example run

def subject_submission(prefix):
    s = PREFIX[prefix]
    cells = [{"id": i, "score": c["board"]["score"] or 0, "confidence": c["board"]["confidence"] or "None",
              "na_cause": c["board"].get("na_cause") or "none", "evidence": c["board"]["evidence"],
              "rationale": c["board"]["rationale"], "summary": EX["indicator_summary"].get(i, "") if prefix == "E" else ""}
             for i, c in s["indicators"].items()]
    ev = [{"code": k, "document": v["document"], "doc_type": v.get("doc_type", ""), "date": v["date"], "url": v.get("url", ""),
           "excerpt": v.get("excerpt", ""), "evidence_class": v["evidence_class"], "search_log": v.get("search_log", "")}
          for k, v in EX["evidence"].items() if k.startswith(prefix)]
    dims = [{"dimension": d, "assessment_text": s.get("assessment_text", {}).get(d, f"Dimension {d} text."),
             "limitations": s.get("limitations", {}).get(d, "Public information only.")} for d in R.DIMS]
    return {"indicators": cells, "evidence": ev, "dimensions": dims,
            "comparables": [{"metric": "Capex to depreciation", "value": "0.9x", "evidence": f"{prefix}01"}], "documents_unavailable": []}


def empty_patch(): return {"indicators": [], "evidence": [], "dimensions": [], "comparables": [], "documents_unavailable": []}


def synthesis():
    return {"headline": EX["headline"], "overall_summary": EX["overall_summary"]["board"], "what_moved": EX["what_moved"],
            "headline_findings": EX["headline_findings"], "key_metrics": EX["key_metrics"], "peer_position": EX["peer_position"],
            "peer_summary_lines": EX["peer_summary_lines"],
            "scorecard_headline": [{"key": k, "text": v} for k, v in EX["scorecard_headline"].items()],
            "peer_row_summary": [{"dimension": k, "text": v} for k, v in EX["peer_row_summary"].items()],
            "peer_summaries": [{"ticker": p["ticker"], "summary": p["summary"]} for p in PEERS],
            "actions": [{k: a[k] for k in ("heading", "description", "measures", "target_by")} for a in EX["actions"]],
            "additional_information_needed": EX["additional_information_needed"]}


def broken_for_grade(sub):
    """Passes research.py's own checks but breaks Rule 3 in grade.py: a 5 on one direct item."""
    sub = copy.deepcopy(sub)
    c = next(c for c in sub["indicators"] if c["id"] == "1.1")
    c.update(score=5, evidence=["E01"], confidence="Medium")
    return sub


def make_model(company_first=None, company_fix=None, synth_first=None):
    """A scripted model. Company: pause_turn, then `company_first`, then fixes; peers submit valid work at once."""
    def model(kw):
        names = tools_of(kw)
        if "submit_synthesis" in names:
            if len(kw["messages"]) == 1: return msg([tool_use("submit_synthesis", synth_first or synthesis(), "toolu_s1")])
            return msg([tool_use("submit_synthesis", synthesis(), "toolu_s2")])
        prefix = re.search(r"Evidence code prefix: ([A-Z])", first_text(kw)).group(1)
        n = len(kw["messages"])
        if prefix == "E" and n == 1:
            return msg([NS(type="server_tool_use", id="srv1", name="web_search", input={"query": "Chevron proxy statement DEF 14A 2026"}),
                        NS(type="web_search_tool_result", tool_use_id="srv1", content=[])], stop="pause_turn")
        if prefix == "E" and last(kw)["role"] == "assistant":
            return msg([NS(type="server_tool_use", id="srv2", name="web_fetch", input={"url": "https://www.sec.gov/cvx-10-k.htm"}),
                        NS(type="web_fetch_tool_result", tool_use_id="srv2", content={}),
                        tool_use("submit_subject_assessment", company_first or subject_submission("E"), "toolu_e1")])
        text = last_text(kw)
        if "not accepted" in text:
            return msg([tool_use("submit_subject_assessment", subject_submission(prefix), f"toolu_{prefix}2")])
        if "grade.py reported" in text and prefix == "E":
            return msg([tool_use("submit_subject_assessment", company_fix(text) if company_fix else empty_patch(), "toolu_e3")])
        if "grade.py reported" in text or "peer-relative" in text:
            return msg([tool_use("submit_subject_assessment", empty_patch(), f"toolu_{prefix}4")])
        return msg([tool_use("submit_subject_assessment", subject_submission(prefix), f"toolu_{prefix}1")])
    return model


@pytest.fixture
def fake(monkeypatch):
    def install(model):
        client = FakeClient(model)
        monkeypatch.setattr(R, "_client", lambda: client)
        return client
    return install


def recorder():
    events = []
    return events, lambda pct, m: events.append((pct, m))


def assert_progress(events):
    pcts = [p for p, _ in events]
    assert pcts == sorted(pcts), "progress must be monotonic"
    assert pcts[0] >= 0 and pcts[-1] == 100


# ---------------------------------------------------------------- tests

def test_outside_in_pause_turn_validation_retry_and_progress(fake):
    bad = subject_submission("E")
    bad["evidence"][0]["excerpt"] = "this excerpt is far too long to be a fair quote because it runs past fifteen words easily"
    client = fake(make_model(company_first=bad))
    events, cb = recorder()
    run = R.run_outside_in(COMPANY["name"], "CVX", PEER_ARGS, "2026-Q4", "director_request", cb)

    assert run["run"]["stage"] == "outside_in" and run["run"]["rule_version"] == "1.2" and run["run"]["simulated"] is False
    assert [s["role"] for s in run["subjects"]] == ["company", "peer", "peer"]
    assert all(len(s["indicators"]) == 22 and "computed" in s for s in run["subjects"])
    assert run["scorecard_headline"]["7"] and len(run["actions"]) <= 5 and run["actions"][0]["id"] == "2026-Q4-A1"
    assert all(p["summary"] for p in run["subjects"][1:])
    assert {k[0] for k in run["evidence"]} == {"E", "X", "B"}

    e_calls = [k for k in client.calls if "Evidence code prefix: E" in first_text(k)]
    assert e_calls[1]["messages"][-1]["role"] == "assistant", "pause_turn resumes with the paused turn, no extra user message"
    retry = e_calls[2]["messages"][-1]["content"][0]
    assert retry["type"] == "tool_result" and retry["is_error"] and "under 15 words" in retry["content"]
    for k in client.calls:
        assert k["model"] == "claude-opus-5" and k["fallbacks"] == "default" and k["betas"] == ["server-side-fallback-2026-07-01"]
        assert k["thinking"] == {"type": "adaptive"} and k["system"][0]["cache_control"]["type"] == "ephemeral"
    research = [k for k in client.calls if "submit_subject_assessment" in tools_of(k)]
    assert all(k["tools"][0]["type"] == "web_search_20260209" and k["tools"][1]["type"] == "web_fetch_20260209" for k in research)
    assert not any(t.get("type", "").startswith("code_execution") for k in client.calls for t in k["tools"])

    assert_progress(events)
    msgs = [m for _, m in events]
    assert "Searching for Chevron's proxy statements" in msgs and "Reading Chevron's annual report and accounts" in msgs


def test_grade_problems_are_parsed_from_a_real_grade_run():
    run = copy.deepcopy(EX)
    run["subjects"][0]["indicators"]["1.1"]["board"].update(score=5, evidence=["E01"])
    run["actions"] = run["actions"] * 2
    problems, graded = R._grade(run)
    assert (COMPANY["name"], "1.1/board", "score 5 needs >=2 items from >=2 documents or one strong item (has 1/1)") in problems
    assert ("run", "actions", "maximum five actions") in problems
    assert "computed" in graded["subjects"][0]
    assert R._grade(copy.deepcopy(EX))[0] == []


def test_grade_fix_loop_feeds_blocking_problems_back(fake):
    seen = []

    def fix(text):
        seen.append(text)
        orig = next(c for c in subject_submission("E")["indicators"] if c["id"] == "1.1")
        return {**empty_patch(), "indicators": [orig]}

    client = fake(make_model(company_first=broken_for_grade(subject_submission("E")), company_fix=fix))
    events, cb = recorder()
    run = R.run_outside_in(COMPANY["name"], "CVX", PEER_ARGS, "2026-Q4", "internal_dry_run", cb)
    assert "1.1/board: score 5 needs >=2 items" in seen[0] and "peer-relative" in seen[0]
    assert run["subjects"][0]["indicators"]["1.1"]["board"]["score"] == COMPANY["indicators"]["1.1"]["board"]["score"]
    assert_progress(events)


def test_grade_fix_loop_gives_up_after_three_rounds(fake):
    broken = broken_for_grade(subject_submission("E"))
    fake(make_model(company_first=broken, company_fix=lambda t: {**empty_patch(), "indicators": [c for c in broken["indicators"] if c["id"] == "1.1"]}))
    with pytest.raises(R.ResearchInvalid) as e:
        R.run_outside_in(COMPANY["name"], "CVX", PEER_ARGS, "2026-Q4", "director_request", None)
    assert any(w == "1.1/board" for _, w, _ in e.value.problems)


def test_json_validation_retries_are_bounded(fake):
    bad = subject_submission("E"); bad["indicators"] = bad["indicators"][:10]

    def model(kw):
        return msg([tool_use("submit_subject_assessment", bad)])
    client = fake(model)
    with pytest.raises(R.ResearchInvalid, match="breaks the rules"):  # the first subject to fail is reported, whichever it is
        R.run_outside_in(COMPANY["name"], "CVX", PEER_ARGS, "2026-Q4", "director_request", None)
    # the company and its peers run in parallel; each subject's retries are bounded, and a failure stops the others
    per = {}
    for kw in client.calls: per[first_text(kw)] = per.get(first_text(kw), 0) + 1
    assert max(per.values()) <= R.MAX_JSON_RETRIES + 1 and sum(per.values()) <= (1 + len(PEER_ARGS)) * (R.MAX_JSON_RETRIES + 1)


def test_refusal_raises_clear_error(fake):
    fake(lambda kw: msg([], stop="refusal", details=NS(category="cyber", explanation=None)))
    with pytest.raises(R.ResearchRefused, match=r"declined .*\(cyber\)"):
        R.run_outside_in(COMPANY["name"], "CVX", PEER_ARGS, "2026-Q4", "director_request", None)


def test_fallback_partial_is_trimmed_before_echo():
    content = [NS(type="thinking"), NS(type="server_tool_use", id="a"), NS(type="text"), NS(type="tool_use", id="t"),
               NS(type="fallback"), NS(type="thinking"), NS(type="text")]
    assert [b.type for b in R._echo(content)] == ["text", "fallback", "thinking", "text"]


def test_input_validation():
    with pytest.raises(ValueError): R.run_outside_in("X", "X", PEER_ARGS[:1], "2026-Q4", "director_request", None)
    with pytest.raises(ValueError): R.run_outside_in("X", "X", PEER_ARGS, "2026Q4", "director_request", None)
    with pytest.raises(ValueError): R.run_outside_in("X", "X", PEER_ARGS, "2026-Q4", "for_fun", None)


def test_research_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_CONFIG_DIR", str(tmp_path))
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE", "ANTHROPIC_IDENTITY_TOKEN", "ANTHROPIC_IDENTITY_TOKEN_FILE"):
        monkeypatch.delenv(k, raising=False)
    ok, why = R.research_enabled()
    assert not ok and "ANTHROPIC_API_KEY" in why
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-real-key")
    assert R.research_enabled()[0]
    monkeypatch.setattr(R, "anthropic", None)
    assert R.research_enabled() == (False, "Install the anthropic package on the server (pip install anthropic) to enable live research.")


def test_real_sdk_request_and_stream_parsing(monkeypatch):
    """Drives the real SDK over a mock HTTP transport: wire shape of the request and SSE parsing of the reply."""
    import anthropic, httpx2
    seen = []

    def sse(*events): return "".join(f"event: {e['type']}\ndata: {json.dumps(e)}\n\n" for e in events)

    def handler(request):
        seen.append((dict(request.headers), json.loads(request.content)))
        inp = json.dumps({"x": 1})
        body = sse({"type": "message_start", "message": {"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5",
                                                         "content": [], "stop_reason": None, "stop_sequence": None,
                                                         "usage": {"input_tokens": 5, "output_tokens": 1}}},
                   {"type": "content_block_start", "index": 0, "content_block": {"type": "tool_use", "id": "toolu_9", "name": "t", "input": {}}},
                   {"type": "content_block_delta", "index": 0, "delta": {"type": "input_json_delta", "partial_json": inp}},
                   {"type": "content_block_stop", "index": 0},
                   {"type": "message_delta", "delta": {"stop_reason": "tool_use", "stop_sequence": None}, "usage": {"output_tokens": 9}},
                   {"type": "message_stop"})
        return httpx2.Response(200, headers={"content-type": "text/event-stream"}, text=body)

    client = anthropic.Anthropic(api_key="test-not-a-real-key", max_retries=0,
                                 http_client=anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler)))
    monkeypatch.setattr(R, "_client", lambda: client)
    blocks, got = [], []
    conv = R._Conv("smoke", R.WEB_TOOLS + [R._tool("t", "test tool", R._obj(x={"type": "integer"}))], "hello", blocks.append)
    conv.submit("t", lambda inp: got.append(inp) or [])
    headers, body = seen[0]
    assert "server-side-fallback-2026-07-01" in headers["anthropic-beta"]
    assert body["fallbacks"] == "default" and body["model"] == "claude-opus-5" and body["thinking"] == {"type": "adaptive"}
    assert body["cache_control"] == R.CACHE and body["system"][0]["cache_control"] == R.CACHE
    assert body["tools"][-1]["strict"] is True and body["stream"] is True
    assert got == [{"x": 1}] and [b.type for b in blocks] == ["tool_use"] and conv.pending == ["toolu_9"]


# ---------------------------------------------------------------- inside-out

PRIOR = sorted(EX["history"], key=lambda h: h["period"])[-1]["actions"]


def io_submission(cells_override=None):
    cells = [{"id": i, "score": 0, "confidence": "None", "na_cause": "none", "evidence": [],
              "rationale": "Carried forward: the board documents add nothing here.", "carried_forward": True} for i in R.IND_IDS]
    cells[0] = {"id": "1.1", "score": 4, "confidence": "Medium", "na_cause": "none", "evidence": ["E01", "IO01"],
                "rationale": "Outside-in showed volumes [E01]; the minutes add a standing customer item [IO01].", "carried_forward": False}
    for c in cells_override or []:
        cells[R.IND_IDS.index(c["id"])] = c
    status = [{"id": a["id"], "status": "behind" if n == 0 else "completed", "evidence_note": "Minuted [IO01].", "metrics_note": "n/a"}
              for n, a in enumerate(PRIOR)]
    return {"cells": cells,
            "documents": [{"code": c, "date": "2026-10-01", "excerpt": "Customer outcomes added as a standing item"} for c in ("IO01", "IO04", "IO14")],
            "headline": "Inside view headline", "overall_summary": "Post inside-out grade C (outside-in C).", "what_moved": "Customer item [IO01].",
            "better": ["Customer item [IO01]."], "worse": ["Pay downside untested [SA02]."],
            "headline_findings": ["One [IO01].", "Two [IO04].", "Three [SA01]."],
            "io_change_notes": [{"id": "1.1", "note": "Outside-in volumes [E01]; minutes add [IO01]."}],
            "actions": [{"heading": "Put a customer measure into pay", "description": "Committee to add it [IO04].", "measures": ["Weight"], "target_by": "2027-Q1"}],
            "prior_actions_status": status,
            "back_on_track": [{"id": PRIOR[0]["id"], "what_happened": "Slipped.", "impact": "Late signals.", "root_cause": "No owner.",
                               "prevention": "Name an owner.", "measures": ["Owner named"]}],
            "additional_information_needed": []}


def test_inside_out_documents_rule19_retry_and_grade(fake):
    sa_only = {"id": "1.4", "score": 5, "confidence": "High", "na_cause": "none", "evidence": ["SA02"],
               "rationale": "Outside-in showed no customer metric; the director says it reduced pay [SA02].", "carried_forward": False}

    def model(kw):
        if len(kw["messages"]) == 1: return msg([tool_use("submit_inside_out", io_submission([sa_only]), "toolu_i1")])
        return msg([tool_use("submit_inside_out", io_submission([{**sa_only, "score": 3, "confidence": "Medium"}]), "toolu_i2")])

    client = fake(model)
    docs = [{"slot": 1, "name": "minutes.txt", "text": "Minutes: customer outcomes added as a standing item.", "pdf_b64": None},
            {"slot": 4, "name": "governance.pdf", "text": None, "pdf_b64": base64.b64encode(b"%PDF-1.4 fake").decode()},
            {"slot": 0, "name": "chair notes.txt", "text": "Executive session notes.", "pdf_b64": None}]
    events, cb = recorder()
    run = R.run_inside_out(EX, docs, {"1": "A lost-contract debrief changed pricing.", "2": "Customer satisfaction at 10%.", "3": " "},
                           {"1": 3, "2": 7}, cb)

    retry = client.calls[1]["messages"][-1]["content"][0]
    assert retry["is_error"] and "cannot lift a score above 3" in retry["content"] and "High confidence" in retry["content"]
    content = client.calls[0]["messages"][0]["content"]
    assert any(b["type"] == "document" and b["source"]["type"] == "base64" for b in content)
    assert run["run"]["stage"] == "inside_out" and run["run"]["simulated"] is False and run["run"]["period"] == "2026-Q4"
    assert {k for k in run["evidence"] if k[:2] in ("IO", "SA")} == {"IO01", "IO04", "IO14", "SA01", "SA02"}
    assert run["evidence"]["SA02"]["question"] and run["evidence"]["IO14"]["source_origin"] == "inside_out"
    comp = run["subjects"][0]["indicators"]
    assert comp["1.1"]["board"] == COMPANY["indicators"]["1.1"]["board"], "outside-in cells stay unchanged"
    assert comp["1.1"]["board_io"]["score"] == 4 and comp["1.4"]["board_io"]["score"] == 3
    assert comp["2.1"]["board_io"]["carried_forward"] and comp["2.1"]["board_io"]["score"] == comp["2.1"]["board"]["score"]
    assert all("board_io" not in c for p in run["subjects"][1:] for c in p["indicators"].values()), "peers are never re-scored"
    assert run["self_ratings"] == {"1": 3}
    assert [b["id"] for b in run["back_on_track"]] == [PRIOR[0]["id"]] and run["prior_actions_status"][0]["heading"]
    assert run["subjects"][0]["computed"]["overall"]["board_io"]["grade"]
    assert_progress(events)


def test_rejected_submission_is_kept_as_draft_for_partial_corrections():
    # Claude is told empty fields keep what it sent before; a correction that resends only the fixed indicator
    # must still be checked against the evidence list from the rejected first submission (live Foundry run, 28 Oct 2026)
    s = R._Subject(COMPANY["name"], COMPANY.get("ticker", ""), "company", "E")
    full = subject_submission("E"); bad = copy.deepcopy(full); bad["indicators"][0]["rationale"] = ""
    assert any("rationale is empty" in p for p in s.accept(bad)) and s.data is None
    fix = dict(empty_patch(), indicators=[full["indicators"][0]])
    assert s.accept(fix) == [] and len(s.data["indicators"]) == 22 and s.data["evidence"]


def test_invalid_draft_items_are_dropped_so_a_fix_can_pass():
    # X1 breaks the prefix rule; merging alone would keep it in the draft for ever, so resubmitting with X02 could never pass
    s = R._Subject("Peer plc", "PR", "peer", "X")
    ev = lambda code: {"code": code, "document": "Doc", "doc_type": "", "date": "2026-01", "url": "http://x", "excerpt": "short", "evidence_class": "direct", "search_log": ""}
    cells = [{"id": i, "score": 3, "confidence": "Medium", "na_cause": "none", "evidence": ["X01"], "rationale": "r", "summary": "s"} for i in R.IND_IDS]
    dims = [{"dimension": d, "assessment_text": "t", "limitations": ""} for d in R.DIMS]
    assert any("'X1' must use the prefix X" in p for p in s.accept({**empty_patch(), "indicators": cells, "evidence": [ev("X01"), ev("X1")], "dimensions": dims}))
    assert s.accept({**empty_patch(), "evidence": [ev("X02")]}) == [] and [e["code"] for e in s.data["evidence"]] == ["X01", "X02"]


def test_inside_out_draft_drops_unknown_documents_and_actions():
    draft = {"documents": [{"code": "IO01"}, {"code": "IO99"}], "prior_actions_status": [{"id": "A1"}, {"id": "nope"}]}
    R._drop(draft, "documents", "code", {"IO99"}); R._drop(draft, "prior_actions_status", "id", {"nope"})
    assert draft == {"documents": [{"code": "IO01"}], "prior_actions_status": [{"id": "A1"}]}


def test_checks_tolerate_missing_fields_without_strict_schema():
    p = R._synth_check({"scorecard_headline": [{}], "peer_summaries": [{"ticker": None}], "actions": [{}], "headline_findings": [None]}, [], set(), "2026-Q4")
    assert any("headline is empty" in x for x in p)
    base = copy.deepcopy(EX)
    for s in base["subjects"]: s.pop("computed", None)
    run = R._assemble_io(base, {"cells": [{"id": "1.1", "score": 3, "evidence": ["E01"]}, {"id": "9.9"}], "io_change_notes": [{"id": "1.1"}]},
                         {"IO01": {"date": "2026-10-01", "document": "Minutes"}}, {}, [], {}, "2026-Q4")
    assert run["subjects"][0]["indicators"]["1.1"]["board_io"]["score"] == 3 and run["evidence"]["IO01"]["excerpt"] == ""
    assert R._scrub({"a": ["x\x0by", {"b": "\x00z"}], "n": 3}) == {"a": ["xy", {"b": "z"}], "n": 3}


def _api_err(kind, status, body=None):
    import anthropic, httpx2
    resp = httpx2.Response(status, request=httpx2.Request("POST", "https://api.example/v1/messages"))
    return getattr(anthropic, kind)("busy", response=resp, body=body)


def test_busy_service_is_retried_with_backoff(fake, monkeypatch):
    monkeypatch.setattr(R, "RETRY_WAITS", (0, 0, 0, 0))
    errs = [_api_err("RateLimitError", 429), _api_err("APIStatusError", 529, {"type": "error", "error": {"type": "overloaded_error"}}), _api_err("InternalServerError", 500)]

    def model(kw):
        if errs: raise errs.pop(0)
        return msg([tool_use("t", {"x": 1})])
    client = fake(model); said = []
    on_phase = R._phases(said.append, {}); got = []
    R._Conv("smoke", [R._tool("t", "test", R._obj(x={"type": "integer"}))], "hi", None, on_phase).submit("t", lambda inp: got.append(inp) or [])
    assert got == [{"x": 1}] and len(client.calls) == 4 and said.count(f"{R.PROVIDER} is busy, retrying in 0s") == 3


def test_retries_give_up_with_the_provider_name(fake, monkeypatch):
    monkeypatch.setattr(R, "RETRY_WAITS", (0, 0))
    def model(kw): raise _api_err("APIStatusError", 503)
    client = fake(model)
    with pytest.raises(R.ResearchError) as e: R._Conv("smoke", [], "hi").turn()
    assert len(client.calls) == 3 and R.PROVIDER in str(e.value) and "Anthropic API" not in str(e.value).replace(R.PROVIDER, "")
    def teapot(kw): raise _api_err("APIStatusError", 418)
    client = fake(teapot)
    with pytest.raises(R.ResearchError, match=f"The {R.PROVIDER} API returned an error"): R._Conv("smoke", [], "hi").turn()
    assert len(client.calls) == 1, "only a busy service is retried"


def test_stop_is_checked_inside_the_stream(fake):
    conv = R._Conv("smoke", [], "hi"); conv.stop = threading.Event(); conv.on_block = lambda b: conv.stop.set()
    fake(lambda kw: msg([NS(type="text", text="a"), NS(type="text", text="b")], stop="end_turn"))
    with pytest.raises(R.ResearchError, match="stopped because another part"): conv.turn()


def test_subjects_are_researched_in_parallel(fake):
    started, gate = [], threading.Barrier(1 + len(PEER_ARGS), timeout=5)  # times out unless all subjects are in flight at once
    base = make_model()

    def model(kw):
        if len(kw["messages"]) == 1 and "submit_subject_assessment" in tools_of(kw):
            started.append(first_text(kw)); gate.wait()
        return base(kw)
    fake(model)
    run = R.run_outside_in(COMPANY["name"], "CVX", PEER_ARGS, "2026-Q4", "director_request", None)
    assert len(set(started)) == 1 + len(PEER_ARGS) and len(run["subjects"]) == 1 + len(PEER_ARGS)

"""Control-flow tests for the LangGraph research agents with a scripted fake Anthropic client (no network, no API key).

Run from backend/:  python -m pytest tests/test_research.py
"""
import base64, copy, json, re, sys, threading
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

BACKEND = Path(__file__).resolve().parent.parent
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))
from app.agents import checks as K, client as C, conversation as V, graph as G, grading, nodes as N, progress as P, settings as cfg, tools as T  # noqa: E402

@pytest.fixture(autouse=True)
def single_pass(monkeypatch):
    """The scripted fake-client tests describe one pass: no consistency re-run and no retrieval review unless a test turns them on."""
    monkeypatch.setattr(cfg, "CONSISTENCY_RUNS", 1); monkeypatch.setattr(cfg, "REVIEW_ROUNDS", 0)


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
             "limitations": s.get("limitations", {}).get(d, "Public information only.")} for d in cfg.DIMS]
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
    """Passes the agents' own checks but breaks Rule 10 in grade.py: one evidence item primary in both indicators of a scoped pair."""
    sub = copy.deepcopy(sub)
    by = {c["id"]: c for c in sub["indicators"]}
    by["5.1"]["evidence"] = list(by["3.4"]["evidence"])
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
        monkeypatch.setattr(C, "get_client", lambda: client)
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
    run = G.run_outside_in(COMPANY["name"], "CVX", PEER_ARGS, "2026-Q4", "director_request", cb)

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
    problems, graded = grading.grade_run(run)
    assert (COMPANY["name"], "1.1/board", "score 5 needs >=2 items from >=2 documents or one strong item (has 1/1)") in problems
    assert ("run", "actions", "maximum five actions") in problems
    assert "computed" in graded["subjects"][0]
    assert grading.grade_run(copy.deepcopy(EX))[0] == []


def test_grade_fix_loop_feeds_blocking_problems_back(fake):
    seen = []

    def fix(text):
        seen.append(text)
        orig = next(c for c in subject_submission("E")["indicators"] if c["id"] == "5.1")
        return {**empty_patch(), "indicators": [orig]}

    client = fake(make_model(company_first=broken_for_grade(subject_submission("E")), company_fix=fix))
    events, cb = recorder()
    run = G.run_outside_in(COMPANY["name"], "CVX", PEER_ARGS, "2026-Q4", "internal_dry_run", cb)
    assert "3.4/5.1 (board): evidence" in seen[0] and "peer-relative" in seen[0]
    assert run["subjects"][0]["indicators"]["5.1"]["board"]["evidence"] == COMPANY["indicators"]["5.1"]["board"]["evidence"]
    assert_progress(events)


def test_grade_fix_loop_gives_up_after_three_rounds(fake):
    broken = broken_for_grade(subject_submission("E"))
    fake(make_model(company_first=broken, company_fix=lambda t: {**empty_patch(), "indicators": [c for c in broken["indicators"] if c["id"] == "5.1"]}))
    with pytest.raises(C.ResearchInvalid) as e:
        G.run_outside_in(COMPANY["name"], "CVX", PEER_ARGS, "2026-Q4", "director_request", None)
    assert any(w.startswith("3.4/5.1") for _, w, _ in e.value.problems)


def test_json_validation_retries_are_bounded(fake):
    bad = subject_submission("E"); bad["indicators"] = bad["indicators"][:10]

    def model(kw):
        return msg([tool_use("submit_subject_assessment", bad)])
    client = fake(model)
    with pytest.raises(C.ResearchInvalid, match="breaks the rules"):  # the first subject to fail is reported, whichever it is
        G.run_outside_in(COMPANY["name"], "CVX", PEER_ARGS, "2026-Q4", "director_request", None)
    # the company and its peers run in parallel; each subject's retries are bounded, and a failure stops the others
    per = {}
    for kw in client.calls: per[first_text(kw)] = per.get(first_text(kw), 0) + 1
    assert max(per.values()) <= cfg.MAX_JSON_RETRIES + 1 and sum(per.values()) <= (1 + len(PEER_ARGS)) * (cfg.MAX_JSON_RETRIES + 1)


def test_refusal_raises_clear_error(fake):
    fake(lambda kw: msg([], stop="refusal", details=NS(category="cyber", explanation=None)))
    with pytest.raises(C.ResearchRefused, match=r"declined .*\(cyber\)"):
        G.run_outside_in(COMPANY["name"], "CVX", PEER_ARGS, "2026-Q4", "director_request", None)


def test_fallback_partial_is_trimmed_before_echo():
    content = [NS(type="thinking"), NS(type="server_tool_use", id="a"), NS(type="text"), NS(type="tool_use", id="t"),
               NS(type="fallback"), NS(type="thinking"), NS(type="text")]
    assert [b.type for b in V.echo(content)] == ["text", "fallback", "thinking", "text"]


def test_input_validation():
    with pytest.raises(ValueError): G.run_outside_in("X", "X", PEER_ARGS[:1], "2026-Q4", "director_request", None)
    with pytest.raises(ValueError): G.run_outside_in("X", "X", PEER_ARGS, "2026Q4", "director_request", None)
    with pytest.raises(ValueError): G.run_outside_in("X", "X", PEER_ARGS, "2026-Q4", "for_fun", None)


def test_research_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_CONFIG_DIR", str(tmp_path))
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE", "ANTHROPIC_IDENTITY_TOKEN", "ANTHROPIC_IDENTITY_TOKEN_FILE"):
        monkeypatch.delenv(k, raising=False)
    ok, why = C.research_enabled()
    assert not ok and "ANTHROPIC_API_KEY" in why
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-not-a-real-key")
    assert C.research_enabled()[0]
    monkeypatch.setattr(C, "anthropic", None)
    assert C.research_enabled() == (False, "Install the anthropic package on the server (pip install anthropic) to enable live research.")


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
    monkeypatch.setattr(C, "get_client", lambda: client)
    blocks, got = [], []
    conv = V.Conv("smoke", T.WEB_TOOLS + [T._tool("t", "test tool", T._obj(x={"type": "integer"}))], "hello", blocks.append)
    conv.submit("t", lambda inp: got.append(inp) or [])
    headers, body = seen[0]
    assert "server-side-fallback-2026-07-01" in headers["anthropic-beta"]
    assert body["fallbacks"] == "default" and body["model"] == "claude-opus-5" and body["thinking"] == {"type": "adaptive"}
    assert body["cache_control"] == cfg.CACHE and body["system"][0]["cache_control"] == cfg.CACHE
    assert body["tools"][-1]["strict"] is True and body["stream"] is True
    assert got == [{"x": 1}] and [b.type for b in blocks] == ["tool_use"] and conv.pending == ["toolu_9"]


# ---------------------------------------------------------------- inside-out

PRIOR = sorted(EX["history"], key=lambda h: h["period"])[-1]["actions"]


def io_submission(cells_override=None):
    cells = [{"id": i, "score": 0, "confidence": "None", "na_cause": "none", "evidence": [],
              "rationale": "Carried forward: the board documents add nothing here.", "carried_forward": True} for i in cfg.IND_IDS]
    cells[0] = {"id": "1.1", "score": 4, "confidence": "Medium", "na_cause": "none", "evidence": ["E01", "IO01"],
                "rationale": "Outside-in showed volumes [E01]; the minutes add a standing customer item [IO01].", "carried_forward": False}
    for c in cells_override or []:
        cells[cfg.IND_IDS.index(c["id"])] = c
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
    run = G.run_inside_out(EX, docs, {"1": "A lost-contract debrief changed pricing.", "2": "Customer satisfaction at 10%.", "3": " "},
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
    s = N.Subject(COMPANY["name"], COMPANY.get("ticker", ""), "company", "E")
    full = subject_submission("E"); bad = copy.deepcopy(full); bad["indicators"][0]["rationale"] = ""
    assert any("rationale is empty" in p for p in s.accept(bad)) and s.data is None
    fix = dict(empty_patch(), indicators=[full["indicators"][0]])
    assert s.accept(fix) == [] and len(s.data["indicators"]) == 22 and s.data["evidence"]


def test_invalid_draft_items_are_dropped_so_a_fix_can_pass():
    # X1 breaks the prefix rule; merging alone would keep it in the draft for ever, so resubmitting with X02 could never pass
    s = N.Subject("Peer plc", "PR", "peer", "X")
    ev = lambda code: {"code": code, "document": "Doc", "doc_type": "", "date": "2026-01", "url": "http://x", "excerpt": "short", "evidence_class": "direct", "search_log": ""}
    cells = [{"id": i, "score": 3, "confidence": "Medium", "na_cause": "none", "evidence": ["X01"], "rationale": "r", "summary": "s"} for i in cfg.IND_IDS]
    dims = [{"dimension": d, "assessment_text": "t", "limitations": ""} for d in cfg.DIMS]
    assert any("'X1' must use the prefix X" in p for p in s.accept({**empty_patch(), "indicators": cells, "evidence": [ev("X01"), ev("X1")], "dimensions": dims}))
    assert s.accept({**empty_patch(), "evidence": [ev("X02")]}) == [] and [e["code"] for e in s.data["evidence"]] == ["X01", "X02"]


def test_inside_out_draft_drops_unknown_documents_and_actions():
    draft = {"documents": [{"code": "IO01"}, {"code": "IO99"}], "prior_actions_status": [{"id": "A1"}, {"id": "nope"}]}
    K._drop(draft, "documents", "code", {"IO99"}); K._drop(draft, "prior_actions_status", "id", {"nope"})
    assert draft == {"documents": [{"code": "IO01"}], "prior_actions_status": [{"id": "A1"}]}


def test_checks_tolerate_missing_fields_without_strict_schema():
    p = K._synth_check({"scorecard_headline": [{}], "peer_summaries": [{"ticker": None}], "actions": [{}], "headline_findings": [None]}, [], set(), "2026-Q4")
    assert any("headline is empty" in x for x in p)
    base = copy.deepcopy(EX)
    for s in base["subjects"]: s.pop("computed", None)
    run = K._assemble_io(base, {"cells": [{"id": "1.1", "score": 3, "evidence": ["E01"]}, {"id": "9.9"}], "io_change_notes": [{"id": "1.1"}]},
                         {"IO01": {"date": "2026-10-01", "document": "Minutes"}}, {}, [], {}, "2026-Q4")
    assert run["subjects"][0]["indicators"]["1.1"]["board_io"]["score"] == 3 and run["evidence"]["IO01"]["excerpt"] == ""
    assert V.scrub({"a": ["x\x0by", {"b": "\x00z"}], "n": 3}) == {"a": ["xy", {"b": "z"}], "n": 3}


def _api_err(kind, status, body=None):
    import anthropic, httpx2
    resp = httpx2.Response(status, request=httpx2.Request("POST", "https://api.example/v1/messages"))
    return getattr(anthropic, kind)("busy", response=resp, body=body)


def test_busy_service_is_retried_with_backoff(fake, monkeypatch):
    monkeypatch.setattr(cfg, "RETRY_WAITS", (0, 0, 0, 0))
    errs = [_api_err("RateLimitError", 429), _api_err("APIStatusError", 529, {"type": "error", "error": {"type": "overloaded_error"}}), _api_err("InternalServerError", 500)]

    def model(kw):
        if errs: raise errs.pop(0)
        return msg([tool_use("t", {"x": 1})])
    client = fake(model); said = []
    on_phase = P.phases(said.append, {}); got = []
    V.Conv("smoke", [T._tool("t", "test", T._obj(x={"type": "integer"}))], "hi", None, on_phase).submit("t", lambda inp: got.append(inp) or [])
    assert got == [{"x": 1}] and len(client.calls) == 4 and said.count(f"{cfg.PROVIDER} is busy, retrying in 0s") == 3


def test_retries_give_up_with_the_provider_name(fake, monkeypatch):
    monkeypatch.setattr(cfg, "RETRY_WAITS", (0, 0))
    def model(kw): raise _api_err("APIStatusError", 503)
    client = fake(model)
    with pytest.raises(C.ResearchError) as e: V.Conv("smoke", [], "hi").turn()
    assert len(client.calls) == 3 and cfg.PROVIDER in str(e.value) and "Anthropic API" not in str(e.value).replace(cfg.PROVIDER, "")
    def teapot(kw): raise _api_err("APIStatusError", 418)
    client = fake(teapot)
    with pytest.raises(C.ResearchError, match=f"The {cfg.PROVIDER} API returned an error"): V.Conv("smoke", [], "hi").turn()
    assert len(client.calls) == 1, "only a busy service is retried"


def test_stop_is_checked_inside_the_stream(fake):
    conv = V.Conv("smoke", [], "hi"); conv.stop = threading.Event(); conv.on_block = lambda b: conv.stop.set()
    fake(lambda kw: msg([NS(type="text", text="a"), NS(type="text", text="b")], stop="end_turn"))
    with pytest.raises(C.ResearchError, match="stopped because another part"): conv.turn()


def test_subjects_are_researched_in_parallel(fake):
    started, gate = [], threading.Barrier(1 + len(PEER_ARGS), timeout=5)  # times out unless all subjects are in flight at once
    base = make_model()

    def model(kw):
        if len(kw["messages"]) == 1 and "submit_subject_assessment" in tools_of(kw):
            started.append(first_text(kw)); gate.wait()
        return base(kw)
    fake(model)
    run = G.run_outside_in(COMPANY["name"], "CVX", PEER_ARGS, "2026-Q4", "director_request", None)
    assert len(set(started)) == 1 + len(PEER_ARGS) and len(run["subjects"]) == 1 + len(PEER_ARGS)


# ---------------------------------------------------------------- graph structure and sources

def test_graphs_compile_with_expected_nodes():
    out = G.build_outside_in().get_graph().nodes
    assert {"plan", "research_subject", "calibrate_and_grade", "fix_subject", "synthesis", "final_check", "finalize"} <= set(out)
    assert {"io_prepare", "io_score", "io_check", "io_revise", "io_finalize"} <= set(G.build_inside_out().get_graph().nodes)


def test_sources_fetch_text_retries_transient_errors_and_strips_html():
    import httpx
    from app.services import sources
    calls = []

    def handler(request):
        calls.append(1)
        if len(calls) < 3: return httpx.Response(503)
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<html><script>x()</script><p>Board  met</p></html>")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    import tenacity
    orig = tenacity.nap.time.sleep
    tenacity.nap.time.sleep = lambda s: None
    try:
        assert sources.fetch_text("https://example.com/a", client=client) == "Board met"
    finally:
        tenacity.nap.time.sleep = orig
    assert len(calls) == 3
    with pytest.raises(sources.SourceError): sources.fetch_text("https://www.linkedin.com/x", client=client)
    assert sources.quote_in_text("board MET", "The Board  met today")


# ---------------------------------------------------------------- budgets, skill prompt, audit checks

def test_budgets_and_system_prompt_carry_the_skill():
    assert cfg.SEARCH_USES >= 60 and cfg.FETCH_USES >= 60 and cfg.EFFORT == "high"
    assert [t["max_uses"] for t in T.WEB_TOOLS] == [cfg.SEARCH_USES, cfg.FETCH_USES]
    sysmsg = T.system_blocks()[0]["text"]
    assert '<reference file="SKILL.md">' in sysmsg and "ignore the bash steps" in sysmsg and '<reference file="data_model.md">' in sysmsg
    assert "ceilings, not targets" in T.render_prompt("subject.md", today="t", period="p", name="n", ticker="t", role="r", peerset="s", prefix="E",
                                                      behaviour_from="a", trend_from="b", search_budget=60, fetch_budget=60)


def test_audit_checks_on_not_assessable_and_rule3():
    na = {"id": "1.1", "score": 0, "confidence": "None", "na_cause": "retrieval-limited", "evidence": [], "rationale": "Could not find it."}
    assert any("lists what was searched" in x for x in K._check_cells([na], set(), ids=["1.1"]))
    ok = dict(na, rationale="Searched EDGAR proxy statements 2022-2026 and 8-K Item 5.02 sweep; nothing disclosed.")
    assert not K._check_cells([ok], set(), ids=["1.1"])
    five = {"id": "1.1", "score": 5, "confidence": "Medium", "na_cause": "none", "evidence": ["E01"], "rationale": "r"}
    items = {"E01": {"document": "D", "evidence_class": "searched_record"}}
    assert any("Rule 3" in x for x in K._check_cells([five], {"E01"}, ids=["1.1"], items=items))
    assert not K._check_cells([five], {"E01"}, ids=["1.1"], items={"E01": {"document": "D", "evidence_class": cfg.FW["strong_classes"][0]}})


def test_retrieval_counts_land_in_coverage_notes(fake):
    fake(make_model())
    run = G.run_outside_in(COMPANY["name"], "CVX", PEER_ARGS, "2026-Q4", "director_request", None)
    notes = run["coverage"]["notes"]
    assert "Company" in notes and "1 searches, 1 fetches" in notes and "Peer" in notes

# ---------------------------------------------------------------- retrieval review and Rule 12 consistency

class _StubConv:
    def __init__(self): self.said, self.submitted = [], 0
    def say(self, text, error=False): self.said.append(text)
    def submit(self, tool, accept): self.submitted += 1


class _StubBand:
    def __init__(self): self.ticks = []
    def tick(self, i, msg, done=False): self.ticks.append(msg)


def _subject(role, fetches, unavailable):
    s = N.Subject("Chevron", "CVX", role, "E"); s.conv = _StubConv(); s.counts["web_fetch"] = fetches; s.counts["web_search"] = 9
    s.data = {"documents_unavailable": unavailable}; return s


def test_review_sends_a_thin_subject_back_to_read_more(monkeypatch):
    monkeypatch.setattr(cfg, "REVIEW_ROUNDS", 2)
    s = _subject("company", 8, ["Chevron 2026 proxy statement in full"]); s.review(_StubBand(), 0)
    assert s.conv.submitted == 2, "still below the floor after round one, so a second round"
    assert "8 page reads" in s.conv.said[0] and "Chevron 2026 proxy statement in full" in s.conv.said[0] and "adverse" in s.conv.said[0]


def test_review_leaves_a_well_read_subject_alone(monkeypatch):
    monkeypatch.setattr(cfg, "REVIEW_ROUNDS", 2)
    s = _subject("company", 25, []); s.review(_StubBand(), 0); assert s.conv.submitted == 0
    p = _subject("peer", 12, []); p.review(_StubBand(), 0); assert p.conv.submitted == 0, "a peer's floor is lower"


def test_review_asks_once_about_unavailable_documents_when_reads_are_enough(monkeypatch):
    monkeypatch.setattr(cfg, "REVIEW_ROUNDS", 2)
    s = _subject("company", 25, ["ISS report"]); s.review(_StubBand(), 0); assert s.conv.submitted == 1


def test_review_off(monkeypatch):
    monkeypatch.setattr(cfg, "REVIEW_ROUNDS", 0)
    s = _subject("company", 0, ["x"]); s.review(_StubBand(), 0); assert s.conv.submitted == 0


from app.agents import reconcile as RC, settings as ST  # noqa: E402
IDS = ST.IND_IDS


def _mk(role, name, prefix, scores=None, url="https://x/a", excerpt="ex a"):
    s = N.Subject(name, "T", role, prefix)
    s.data = {"indicators": [{"id": i, "score": (scores or {}).get(i, 3), "confidence": "Medium", "na_cause": "none", "evidence": [f"{prefix}01"],
                              "rationale": f"rationale {i} [{prefix}01]", "summary": f"summary {i} [{prefix}01]"} for i in IDS],
              "evidence": [{"code": f"{prefix}01", "document": "Doc", "doc_type": "t", "date": "2026-01", "url": url, "excerpt": excerpt,
                            "evidence_class": "direct", "search_log": ""}], "dimensions": [], "comparables": [], "documents_unavailable": []}
    s.draft = s.data
    return s


class _ScriptedConv:
    """Stands in for the adjudicator conversation: answers from `choices` {indicator: ('A'|'B', reason)}."""
    choices: dict = {}
    seen: list = []

    def __init__(self, label, tools, content, *a, model=None, **k):
        _ScriptedConv.seen.append({"label": label, "model": model, "prompt": content}); self.stop = None

    def submit(self, tool, accept):
        ids = re.findall(r"^### (\d\.\d) ", _ScriptedConv.seen[-1]["prompt"], re.M)
        problems = accept({"items": [{"indicator": i, "choice": _ScriptedConv.choices[i][0], "reason": _ScriptedConv.choices[i][1]} for i in ids]})
        assert not problems, problems


CTX = {"today": "2026-10-29", "period": "2026-Q4", "peerset": "Chevron (CVX)", "stop": None}


def test_reconciliation_adopts_run_b_where_the_model_recommends_it(monkeypatch):
    a = _mk("company", "Chevron", "E"); b = _mk("company", "Chevron", "E", {"1.4": 4}, url="https://x/b", excerpt="ex b")
    monkeypatch.setattr(RC, "Conv", _ScriptedConv); _ScriptedConv.seen = []
    _ScriptedConv.choices = {"1.4": ("B", "Run B's evidence [E02] shows a 25% weighted measure.")}
    block = RC.reconcile([a], [b], CTX)
    assert block["agreed"] == 21 and block["total"] == 22 and len(block["rows"]) == 1
    row = block["rows"][0]
    assert (row["indicator"], row["a"], row["b"], row["final"], row["chosen"]) == ("1.4", 3, 4, 4, "B") and "[E02]" in row["reason"]
    cell = next(c for c in a.data["indicators"] if c["id"] == "1.4")
    assert cell["score"] == 4 and cell["evidence"] == ["E02"] and "[E02]" in cell["rationale"] and "[E01]" not in cell["rationale"]
    assert [e["code"] for e in a.data["evidence"]] == ["E01", "E02"] and a.data["evidence"][1]["url"] == "https://x/b"
    assert a.recon_note and "1.4 3 -> 4" in a.recon_note
    assert _ScriptedConv.seen[0]["model"] == ST.MODEL, "the adjudicator runs on Run A's model"
    assert "Run A: score 3" in _ScriptedConv.seen[0]["prompt"] and "Run B: score 4" in _ScriptedConv.seen[0]["prompt"]


def test_reconciliation_keeps_run_a_and_drops_run_b_evidence_it_did_not_use(monkeypatch):
    a = _mk("company", "Chevron", "E"); b = _mk("company", "Chevron", "E", {"2.4": 2}, url="https://x/b", excerpt="ex b")
    monkeypatch.setattr(RC, "Conv", _ScriptedConv); _ScriptedConv.seen = []
    _ScriptedConv.choices = {"2.4": ("A", "Run A reads the 2026 proxy charter review; the anchor 3 fits.")}
    block = RC.reconcile([a], [b], CTX)
    assert block["rows"][0]["final"] == 3 and block["rows"][0]["chosen"] == "A"
    assert next(c for c in a.data["indicators"] if c["id"] == "2.4")["score"] == 3
    assert [e["code"] for e in a.data["evidence"]] == ["E01"] and not a.recon_note


def test_reconciliation_reuses_the_same_source_and_skips_agreeing_subjects(monkeypatch):
    a = _mk("company", "Chevron", "E"); b = _mk("company", "Chevron", "E", {"5.2": 4})  # same url and excerpt: one source
    pa, pb = _mk("peer", "Shell", "X"), _mk("peer", "Shell", "X")
    monkeypatch.setattr(RC, "Conv", _ScriptedConv); _ScriptedConv.seen = []
    _ScriptedConv.choices = {"5.2": ("B", "B")}
    block = RC.reconcile([a, pa], [b, pb], CTX)
    assert block["total"] == 44 and block["agreed"] == 43 and len(_ScriptedConv.seen) == 1, "no call for the peer: nothing disputed"
    assert next(c for c in a.data["indicators"] if c["id"] == "5.2")["evidence"] == ["E01"] and len(a.data["evidence"]) == 1


def test_a_reason_may_not_cite_an_unknown_code(monkeypatch):
    a = _mk("company", "Chevron", "E"); b = _mk("company", "Chevron", "E", {"1.1": 2}, url="https://x/b", excerpt="ex b")
    class Bad(_ScriptedConv):
        def submit(self, tool, accept):
            assert accept({"items": [{"indicator": "1.1", "choice": "A", "reason": "see [E99]"}]}), "an unknown code is refused"
            _ScriptedConv.submit(self, tool, accept)
    monkeypatch.setattr(RC, "Conv", Bad); _ScriptedConv.seen = []; _ScriptedConv.choices = {"1.1": ("A", "fine")}
    RC.reconcile([a], [b], CTX)


def test_two_model_run_reconciles_then_finishes_on_run_a(monkeypatch):
    monkeypatch.setattr(cfg, "CONSISTENCY_RUNS", 2)
    calls = []
    def research(company, ticker, peers, period, mode, progress, documents, model):
        calls.append(model)
        s = [_mk("company", "Chevron", "E", {"1.4": 4} if model == ST.MODEL_B else {}, url="https://x/" + model, excerpt=model)]
        return {"ctx": {**CTX, "prog": lambda *a: None}, "subjects": s}
    class Finish:
        def invoke(self, state, config):
            assert state["ctx"]["reconciliation"]["rows"][0]["final"] == 4
            return {"result": {"run": {}, "coverage": {"consistency_result": state["ctx"]["consistency_result"], "notes": state["ctx"]["notes"]}}}
    monkeypatch.setattr(G, "_research_once", research); monkeypatch.setattr(G, "_preflight", lambda m: calls.append("preflight " + m))
    monkeypatch.setattr(G, "_graph", lambda name, build: Finish())
    monkeypatch.setattr(RC, "Conv", _ScriptedConv); _ScriptedConv.seen = []; _ScriptedConv.choices = {"1.4": ("B", "B is better evidenced.")}
    out = G.run_outside_in("Chevron", "CVX", PEER_ARGS, "2026-Q4", "director_request", None)
    assert calls[0] == "preflight " + ST.MODEL_B and sorted(calls[1:]) == sorted([ST.MODEL, ST.MODEL_B])
    assert "1 reconciled" in out["coverage"]["consistency_result"] and ST.MODEL_B in out["coverage"]["notes"]


def test_a_model_that_cannot_be_used_stops_the_run_before_any_research(monkeypatch):
    monkeypatch.setattr(cfg, "CONSISTENCY_RUNS", 2)
    def boom(model): raise C.ResearchError(f"The model {model} is not available")
    monkeypatch.setattr(G, "_preflight", boom)
    monkeypatch.setattr(G, "_research_once", lambda *a, **k: pytest.fail("research must not start"))
    with pytest.raises(C.ResearchError, match="not available"):
        G.run_outside_in("Chevron", "CVX", PEER_ARGS, "2026-Q4", "director_request", None)

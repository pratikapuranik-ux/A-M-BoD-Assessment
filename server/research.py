"""
research.py - live outside-in research and inside-out re-scoring with Claude.

Outside-in: each subject (company first, then peers concurrently) is researched in its own conversation with
web search and web fetch and returns its 22 board cells through a strict client tool; a calibration pass shares
peer-relative comparables across subjects; a synthesis conversation writes the narrative fields. Inside-out:
one conversation reads the board documents and questionnaire answers and returns the board_io cells.
Every run is checked by skill/scripts/grade.py and blocking problems go back to the conversation that caused them.
"""
from __future__ import annotations

import copy, datetime as dt, functools, json, logging, os, re, subprocess, sys, tempfile, threading, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from string import Template
from typing import Callable

try:
    import anthropic
except ImportError:  # research_enabled() reports it
    anthropic = None

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent / "skill"; SCRIPTS = SKILL / "scripts"; REFS = SKILL / "references"; PROMPTS = HERE / "prompts"
FW = json.loads((SKILL / "assets" / "framework.json").read_text(encoding="utf-8"))
IND_IDS = [i["id"] for i in FW["indicators"]]; DIMS = sorted(FW["dimensions"], key=int)
PEER_RELATIVE = FW["peer_relative"]
REF_FILES = ["guardrails.md", "framework.md", "outside_in_overrides.md", "scoring_rules.md", "sources.md", "inside_out_documents.md"]

MODEL = os.environ.get("BOARD_MODEL") or "claude-opus-5"
# Microsoft Foundry (Azure) instead of the Claude API when its key and resource are set. Foundry has no server-side
# fallback, and Azure-hosted deployments take only the basic web tools (BOARD_WEB_TOOLS=latest overrides).
FOUNDRY = bool(os.environ.get("ANTHROPIC_FOUNDRY_API_KEY") and (os.environ.get("ANTHROPIC_FOUNDRY_RESOURCE") or os.environ.get("ANTHROPIC_FOUNDRY_BASE_URL")))
BETAS = [] if FOUNDRY else ["server-side-fallback-2026-07-01"]
LATEST_WEB = (os.environ.get("BOARD_WEB_TOOLS") or ("basic" if FOUNDRY else "latest")) == "latest"
PROVIDER = "Microsoft Foundry" if FOUNDRY else "Anthropic"
EFFORT = "high"
MAX_TOKENS = 64000
HEARTBEAT = 30  # seconds between 'still working' progress lines
SEARCH_USES, FETCH_USES, FETCH_TOKENS = 12, 12, 30000
SEARCH_BUDGET, FETCH_BUDGET = 15, 15
MAX_CONTINUATIONS, MAX_JSON_RETRIES, MAX_FIX_ROUNDS, SUBJECT_WORKERS = 8, 2, 3, 6  # company and up to five peers at once
CACHE = {"type": "ephemeral", "ttl": "1h"}
PEER_PREFIXES = "XBKLN"
BLOCKED = ["facebook.com", "glassdoor.com", "indeed.com", "instagram.com", "linkedin.com", "medium.com",
           "quora.com", "reddit.com", "tiktok.com", "twitter.com", "x.com"]

log = logging.getLogger(__name__)
Progress = Callable[[int, str], None]
PERIOD_RE = re.compile(r"^\d{4}-Q[1-4]$"); DATE_RE = re.compile(r"^\d{4}(-\d{2}(-\d{2})?)?$")
CODE_RE = re.compile(r"^(?:[EXBKLN]\d{2,3}|IO\d{2}|SA\d{2})$")
BLOCK_RE = re.compile(r"^\s*BLOCK \[(.*?)\] (.*?): (.*)$", re.M)
AM_RE = re.compile(r"\bA&M\b|Alvarez", re.I)


class ResearchError(RuntimeError):
    """A research step failed; the message is fit to show the user."""


class ResearchRefused(ResearchError):
    """Claude (and the server-side fallback model) declined the request."""


class ResearchInvalid(ResearchError):
    """The model's output still broke the rules after the allowed fix rounds."""

    def __init__(self, msg, problems=()):
        super().__init__(msg); self.problems = list(problems)


# ---------------------------------------------------------------- client, credentials

_CLIENT, _CLIENT_LOCK = None, threading.Lock()


def research_enabled() -> tuple[bool, str]:
    if anthropic is None:
        return False, "Install the anthropic package on the server (pip install anthropic) to enable live research."
    if FOUNDRY:
        try: anthropic.AnthropicFoundry()
        except (anthropic.AnthropicError, ValueError, OSError) as e: return False, f"The Microsoft Foundry client could not be configured ({e})."
        return True, "Live research is enabled (Microsoft Foundry)."
    try:
        c = anthropic.Anthropic()
    except anthropic.CredentialsError as e:
        return False, f"The server's Anthropic credentials could not be loaded ({e}). Set ANTHROPIC_API_KEY on the server to enable live research."
    except (anthropic.AnthropicError, ValueError, OSError) as e:
        return False, f"The Anthropic client could not be configured ({e})."
    if c.api_key or c.auth_token or c.credentials:
        return True, "Live research is enabled."
    return False, "Set ANTHROPIC_API_KEY on the server to enable live research."


def _client():
    global _CLIENT
    if anthropic is None:
        raise ResearchError("The anthropic package is not installed on the server.")
    with _CLIENT_LOCK:
        if _CLIENT is None:
            _CLIENT = anthropic.AnthropicFoundry(max_retries=4) if FOUNDRY else anthropic.Anthropic(max_retries=4)
    return _CLIENT


@functools.lru_cache(maxsize=1)
def _system():
    parts = [(PROMPTS / "system.md").read_text(encoding="utf-8").strip()]
    for f in REF_FILES:
        text = (REFS / f).read_text(encoding="utf-8")
        if f == "sources.md":  # the file repeats its last four sections verbatim
            h = "## Approved news list"; second = text.find(h, text.find(h) + 1)
            text = text[:second] if second > 0 else text
        parts.append(f'<reference file="{f}">\n{text.strip()}\n</reference>')
    return [{"type": "text", "text": "\n\n".join(parts), "cache_control": CACHE}]


def _prompt(file, **kw):
    return Template((PROMPTS / file).read_text(encoding="utf-8")).substitute(**kw)


def _today():
    return dt.date.today()


# ---------------------------------------------------------------- schemas and tools

S = {"type": "string"}; BOOL = {"type": "boolean"}


def _arr(x): return {"type": "array", "items": x}
def _enum(*v): return {"type": "string", "enum": list(v)}
def _obj(**props): return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}
def _tool(name, desc, schema): return {"name": name, "description": desc, "strict": True, "input_schema": schema}


CELL = dict(id=_enum(*IND_IDS), score={"type": "integer", "enum": [0, 1, 2, 3, 4, 5]},
            confidence=_enum("High", "Medium", "Low", "None"), na_cause=_enum(*FW["na_causes"], "none"),
            evidence=_arr(S), rationale=S)
ACTION = _obj(heading=S, description=S, measures=_arr(S), target_by=S)
OI_CLASSES = [c for c in FW["evidence_classes"] if c not in ("inside_out", "self_assessment")]

SUBJECT_TOOL = _tool("submit_subject_assessment",
    "Submit the scored assessment of one subject's board. Call it once research is complete, with all 22 indicators. "
    "When asked to revise, call it again with only the indicators, evidence items, dimensions and comparables that change; "
    "empty lists keep what was submitted before.",
    _obj(indicators=_arr(_obj(**CELL, summary=S)),
         evidence=_arr(_obj(code=S, document=S, doc_type=S, date=S, url=S, excerpt=S, evidence_class=_enum(*OI_CLASSES), search_log=S)),
         dimensions=_arr(_obj(dimension=_enum(*DIMS), assessment_text=S, limitations=S)),
         comparables=_arr(_obj(metric=S, value=S, evidence=S)),
         documents_unavailable=_arr(S)))
SYNTH_TOOL = _tool("submit_synthesis",
    "Submit the narrative fields of the outside-in run. Call it once with every field; when asked to revise, resubmit "
    "with the fields that change (empty strings and lists keep what was submitted before).",
    _obj(headline=S, overall_summary=S, what_moved=S, headline_findings=_arr(S),
         key_metrics=_arr(_obj(metric=S, why=S, current=S)), peer_position=S, peer_summary_lines=_arr(S),
         scorecard_headline=_arr(_obj(key=_enum(*DIMS, "7"), text=S)),
         peer_row_summary=_arr(_obj(dimension=_enum(*DIMS), text=S)),
         peer_summaries=_arr(_obj(ticker=S, summary=S)), actions=_arr(ACTION), additional_information_needed=_arr(S)))
IO_TOOL = _tool("submit_inside_out",
    "Submit the post inside-out cells and narrative for the company. Call it once with all 22 cells; when asked to "
    "revise, resubmit with what changes (empty strings and lists keep what was submitted before).",
    _obj(cells=_arr(_obj(**CELL, carried_forward=BOOL)), documents=_arr(_obj(code=S, date=S, excerpt=S)),
         headline=S, overall_summary=S, what_moved=S, better=_arr(S), worse=_arr(S), headline_findings=_arr(S),
         io_change_notes=_arr(_obj(id=_enum(*IND_IDS), note=S)), actions=_arr(ACTION),
         prior_actions_status=_arr(_obj(id=S, status=_enum(*FW["action_statuses"]), evidence_note=S, metrics_note=S)),
         back_on_track=_arr(_obj(id=S, what_happened=S, impact=S, root_cause=S, prevention=S, measures=_arr(S))),
         additional_information_needed=_arr(S)))
WEB_TOOLS = [{"type": "web_search_20260209" if LATEST_WEB else "web_search_20250305", "name": "web_search", "max_uses": SEARCH_USES, "blocked_domains": BLOCKED},
             {"type": "web_fetch_20260209" if LATEST_WEB else "web_fetch_20250910", "name": "web_fetch", "max_uses": FETCH_USES,
              "max_content_tokens": FETCH_TOKENS, "blocked_domains": BLOCKED}]
SUBJECT_KEYS = {"indicators": "id", "evidence": "code", "dimensions": "dimension", "comparables": "metric"}
SYNTH_KEYS = {"scorecard_headline": "key", "peer_row_summary": "dimension", "peer_summaries": "ticker"}
IO_KEYS = {"cells": "id", "documents": "code", "io_change_notes": "id", "prior_actions_status": "id", "back_on_track": "id"}


# ---------------------------------------------------------------- progress

class _Progress:
    def __init__(self, cb): self.cb, self.pct, self.lock = cb, 0, threading.Lock()

    def __call__(self, pct, msg):
        with self.lock:
            self.pct = max(self.pct, min(100, int(pct)))
            if self.cb: self.cb(self.pct, msg)


class _Band:
    """Maps the progress of n parallel tasks onto [lo, hi] of the overall bar."""

    def __init__(self, prog, lo, hi, n): self.prog, self.lo, self.hi, self.f, self.lock = prog, lo, hi, [0.0] * n, threading.Lock()

    def tick(self, i, msg, done=False):
        with self.lock:
            self.f[i] = 1.0 if done else min(0.95, self.f[i] + (1 - self.f[i]) * 0.12)
            pct = self.lo + (self.hi - self.lo) * sum(self.f) / len(self.f)
        self.prog(pct, msg)


TOPICS = [(r"def ?14a|proxy", "proxy statements"), (r"10-k|10-q|20-f|annual report", "annual report and accounts"),
          (r"transcript|earnings call|conference call", "earnings call transcripts"),
          (r"moody|fitch|s&p global|credit rating|rating action", "credit rating commentary"),
          (r"\biss\b|glass lewis|say.on.pay", "proxy adviser commentary"),
          (r"recall|enforcement|lawsuit|litigation|court|regulator|settlement|penalt", "regulator and court records"),
          (r"8-k|press release|announce|newsroom", "recent announcements"),
          (r"investor day|capital markets day|presentation", "investor presentations"),
          (r"governance guidelines|charter|bylaw|corporate governance", "governance documents"),
          (r"compensation|incentive|bonus|executive pay", "pay disclosures"),
          (r"capex|capital expenditure|cash flow|buyback|repurchase|dividend|debt|liquidity", "capital and cash disclosures"),
          (r"director|board", "board disclosures"), (r"reuters|bloomberg|wsj|ft\.com|cnbc|news", "press coverage")]


def _short(name):
    n = re.sub(r"\s*\(.*?\)", "", name).strip()
    for _ in range(2):
        n = re.sub(r",?\s+(Corporation|Corp\.?|Incorporated|Inc\.?|p\.l\.c\.|plc|Ltd\.?|Limited|Holdings|Company|Co\.|S\.A\.|SE|AG|N\.V\.)$", "", n, flags=re.I).strip()
    return n or name


def _narrate(short, tool, inp):
    text = " ".join(str(v) for v in (inp or {}).values()).lower()
    topic = next((t for pat, t in TOPICS if re.search(pat, text)), None)
    own = short + ("'" if short.endswith("s") else "'s")
    if tool == "web_fetch":
        return f"Reading {own} {topic}" if topic else f"Reading a source document on {short}"
    return f"Searching for {own} {topic}" if topic else f"Searching public sources on {short}"


# ---------------------------------------------------------------- conversation loop

def _echo(content):
    """Assistant content to send back; after a mid-output fallback, drops blocks the fallback model cannot take."""
    types = [getattr(b, "type", "") for b in content]
    if "fallback" not in types: return list(content)
    cut = len(types) - 1 - types[::-1].index("fallback")
    done = {getattr(b, "tool_use_id", None) for b, t in zip(content, types) if t.endswith("_tool_result")}
    out = []
    for i, b in enumerate(content):
        t = types[i]
        if i < cut and not (t in ("text", "fallback") or t.endswith("_tool_result") or (t == "server_tool_use" and b.id in done)):
            continue
        out.append(b)
    return out


def _phases(say, labels):
    """on_phase callback for _Conv: names what Claude is doing (labels: 'thinking' or a tool name -> text), then repeats it
    with the elapsed minutes while that step runs long."""
    cur = {"msg": None, "t0": 0.0}

    def on_phase(b):
        if b is not None:
            key = "thinking" if getattr(b, "type", "") == "thinking" else getattr(b, "name", None)
            if key in labels: cur.update(msg=labels[key], t0=time.monotonic()); say(cur["msg"])
        elif cur["msg"]:
            mins = int((time.monotonic() - cur["t0"]) // 60)
            say(f"{cur['msg']} ({mins} min so far)" if mins else f"{cur['msg']} (still working)")
    on_phase.say = say
    return on_phase


def _err(e):
    return getattr(e, "message", None) or str(e)


RETRY_WAITS = (15, 30, 60, 90)  # seconds before each app-level retry while the service is busy; tests set zeros
BUSY_STATUS = {429, 500, 502, 503, 529}


def _busy(e):
    """A rate limit, overload, server or connection error: worth waiting for."""
    kinds = tuple(getattr(anthropic, n) for n in ("RateLimitError", "OverloadedError", "InternalServerError", "APIConnectionError") if hasattr(anthropic, n))
    if isinstance(e, kinds): return True
    body = getattr(e, "body", None); err = body.get("error") if isinstance(body, dict) else None
    return isinstance(e, anthropic.APIStatusError) and (e.status_code in BUSY_STATUS or (isinstance(err, dict) and err.get("type") == "overloaded_error"))


def _pause(seconds, stop=None):
    """Sleep, waking early if a parallel step failed (stop is set)."""
    if stop is not None: stop.wait(seconds)
    else: time.sleep(seconds)


def _api_error(e, label):
    if isinstance(e, anthropic.AuthenticationError): return ResearchError(f"The server's {PROVIDER} API key was rejected. Check the key in .env.")
    if isinstance(e, anthropic.PermissionDeniedError): return ResearchError(f"The {PROVIDER} API key lacks access to {MODEL} or to web search ({_err(e)}).")
    if isinstance(e, anthropic.NotFoundError): return ResearchError(f"The model {MODEL} is not available to this {PROVIDER} key ({_err(e)}).")
    if isinstance(e, anthropic.RateLimitError): return ResearchError(f"The {PROVIDER} rate limit was reached; try again in a few minutes.")
    if isinstance(e, anthropic.BadRequestError): return ResearchError(f"The {label} request was rejected: {_err(e)}")
    if _busy(e) and not isinstance(e, anthropic.APIConnectionError): return ResearchError(f"{PROVIDER} stayed busy during {label} after {len(RETRY_WAITS)} retries; try again shortly.")
    if isinstance(e, anthropic.APIStatusError): return ResearchError(f"The {PROVIDER} API returned an error during {label} ({e.status_code}); try again shortly.")
    if isinstance(e, anthropic.APIConnectionError): return ResearchError(f"Could not reach the {PROVIDER} API during {label}; check the server's network.")
    return ResearchError(f"The {PROVIDER} API failed during {label}: {_err(e)}")


CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _scrub(x):
    """Drops control characters from every string (python-docx and the dashboards cannot take them)."""
    if isinstance(x, str): return CTRL_RE.sub("", x)
    if isinstance(x, list): return [_scrub(v) for v in x]
    if isinstance(x, dict): return {k: _scrub(v) for k, v in x.items()}
    return x


class _Conv:
    def __init__(self, label, tools, content, on_block=None, on_phase=None):
        self.label, self.tools, self.on_block, self.on_phase = label, tools, on_block, on_phase
        self.stop = None  # threading.Event shared by parallel steps: set when one fails, so the others stop calling Claude
        self.messages, self.pending, self.strict = [{"role": "user", "content": content}], [], True

    def say(self, text, error=False):
        if self.pending:
            extra = {"is_error": True} if error else {}
            self.messages.append({"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": tid, "content": text if n == 0 else "See the first tool result.", **extra}
                for n, tid in enumerate(self.pending)]})
            self.pending = []
        else:
            self.messages.append({"role": "user", "content": text})

    def _check_stop(self):
        if self.stop is not None and self.stop.is_set(): raise ResearchError(f"The {self.label} step stopped because another part of the research failed.")

    def _stream(self):
        tools = self.tools if self.strict else [{k: v for k, v in t.items() if k != "strict"} for t in self.tools]
        kw = dict(model=MODEL, max_tokens=MAX_TOKENS, system=_system(), tools=tools,
                  messages=self.messages, thinking={"type": "adaptive"}, output_config={"effort": EFFORT}, cache_control=CACHE)
        if not FOUNDRY: kw.update(betas=BETAS, fallbacks="default")
        with _client().beta.messages.stream(**kw) as stream:
            beat = time.monotonic()
            for ev in stream:
                self._check_stop()
                # on_phase(block) when Claude starts thinking or writing; on_phase(None) every HEARTBEAT seconds while it does,
                # so long silent stretches (no searches) still show progress
                if self.on_phase and ev.type == "content_block_start": self.on_phase(getattr(ev, "content_block", None)); beat = time.monotonic()
                elif self.on_phase and time.monotonic() - beat > HEARTBEAT: self.on_phase(None); beat = time.monotonic()
                if self.on_block and ev.type == "content_block_stop" and getattr(ev, "content_block", None) is not None:
                    self.on_block(ev.content_block)
            return stream.get_final_message()

    def _request(self):
        """One streamed request; waits and retries (RETRY_WAITS) while the service is busy or unreachable."""
        for wait in (*RETRY_WAITS, None):
            self._check_stop()
            try:
                return self._stream()
            except Exception as e:
                if anthropic is None or not isinstance(e, anthropic.APIError): raise
                if wait is not None and _busy(e):
                    log.warning("%s: %s busy (%s); retrying in %ss", self.label, PROVIDER, _err(e), wait)
                    if say := getattr(self.on_phase, "say", None): say(f"{PROVIDER} is busy, retrying in {wait}s")
                    _pause(wait, self.stop); continue
                if isinstance(e, anthropic.BadRequestError) and self.strict and "too complex" in _err(e).lower():
                    log.warning("strict schema rejected (%s); retrying without strict", _err(e))
                    self.strict = False
                    return self._request()
                raise _api_error(e, self.label) from e

    def turn(self):
        """One model turn, continuing server-side pauses; returns the final message of the turn."""
        for _ in range(MAX_CONTINUATIONS):
            msg = self._request()
            u = getattr(msg, "usage", None)
            log.info("%s: stop=%s in=%s cache_read=%s cache_write=%s out=%s", self.label, msg.stop_reason,
                     getattr(u, "input_tokens", None), getattr(u, "cache_read_input_tokens", None),
                     getattr(u, "cache_creation_input_tokens", None), getattr(u, "output_tokens", None))
            if msg.stop_reason == "refusal":
                cat = getattr(getattr(msg, "stop_details", None), "category", None)
                raise ResearchRefused(f"Claude declined the {self.label} step{f' ({cat})' if cat else ''}, and so did the "
                                      "fallback model. Nothing was saved; try again or adjust the inputs.")
            self.messages.append({"role": "assistant", "content": _echo(msg.content)})
            if msg.stop_reason != "pause_turn":
                return msg
        raise ResearchError(f"The {self.label} step kept pausing without finishing; try again.")

    def submit(self, tool, accept):
        """Run turns until `tool` is called with input that `accept` takes (it returns a list of problems)."""
        nudges = rejects = 0
        while True:
            msg = self.turn()
            calls = [b for b in msg.content if getattr(b, "type", "") == "tool_use"]
            self.pending = [b.id for b in calls]
            call = next((b for b in reversed(calls) if b.name == tool), None)
            if msg.stop_reason == "max_tokens":
                problems = ["The response hit the output limit before the submission was complete. Submit again, keeping text fields short."]
            elif call is None:
                nudges += 1
                if nudges > 2: raise ResearchError(f"The {self.label} step finished without submitting results.")
                self.say(f"Call the {tool} tool now with your results."); continue
            else:
                problems = accept(_scrub(call.input) if isinstance(call.input, dict) else {})
                if not problems: return
            rejects += 1
            say = getattr(self.on_phase, "say", None)
            if say and rejects <= MAX_JSON_RETRIES: say(f"Checking {self.label}: {len(problems)} point(s) to correct; asking Claude to fix them")
            if rejects > MAX_JSON_RETRIES:
                raise ResearchInvalid(f"The {self.label} step returned output that breaks the rules: " + "; ".join(problems[:5]), problems)
            self.say("The submission was not accepted:\n- " + "\n- ".join(problems[:60]) + f"\nFix these and call {tool} again.", error=True)


# ---------------------------------------------------------------- validation helpers

def _merge(old, new, keys):
    if old is None: return copy.deepcopy(new)
    out = copy.deepcopy(old)
    for field, v in new.items():
        if field in keys:
            if v:
                idx = {x.get(keys[field]): x for x in out.get(field, [])}
                idx.update({x.get(keys[field]): x for x in v})
                out[field] = list(idx.values())
        elif v not in ("", None, []):
            out[field] = copy.deepcopy(v)
    return out


def _drop(draft, field, key, bad):
    """Remove the draft's items whose key is invalid (wrong code prefix, unknown document or action id), so a
    resubmission that leaves them out can pass: a merge alone would keep them forever."""
    if bad: draft[field] = [x for x in draft.get(field, []) if x.get(key) not in bad]


def _cited(text):
    return [c for g in re.findall(r"\[([^\]]+)\]", text or "") for c in re.split(r"[\s,;]+", g) if CODE_RE.match(c)]


def _dups(xs):
    return sorted({x for x in xs if xs.count(x) > 1})


def _check_cells(cells, known, ids=IND_IDS):
    p = []; got = [c.get("id") for c in cells]
    if missing := [i for i in ids if i not in got]: p.append(f"indicators missing: {missing}")
    if d := _dups(got): p.append(f"indicators submitted more than once: {d}")
    for c in cells:
        w = f"indicator {c.get('id')}"
        if not (c.get("rationale") or "").strip(): p.append(f"{w}: rationale is empty")
        if bad := [x for x in (c.get("evidence") or []) + _cited(c.get("rationale")) if x not in known]:
            p.append(f"{w}: cites evidence codes that do not exist {sorted(set(bad))}")
        if c.get("carried_forward"): continue
        if c.get("score") == 0:
            if c.get("na_cause") == "none": p.append(f"{w}: not assessable (score 0) needs an na_cause")
        else:
            if c.get("confidence") == "None": p.append(f"{w}: a score needs confidence High, Medium or Low")
            if not c.get("evidence"): p.append(f"{w}: a score needs at least one evidence item")
    return p


def _check_evidence(items, prefix=None):
    p = []; codes = [e.get("code", "") for e in items]
    if d := _dups(codes): p.append(f"evidence codes used more than once: {d}")
    for e in items:
        c = e.get("code", "")
        if prefix and not re.fullmatch(prefix + r"\d{2,3}", c): p.append(f"evidence code {c!r} must use the prefix {prefix} ({prefix}01, {prefix}02, ...)")
        if len((e.get("excerpt") or "").split()) >= 15: p.append(f"{c}: excerpt must be under 15 words verbatim")
        if not DATE_RE.match(e.get("date") or ""): p.append(f"{c}: date must be YYYY-MM-DD, YYYY-MM or YYYY")
        if "evidence_class" in e:
            if e["evidence_class"] == "searched_record":
                if not (e.get("search_log") or "").strip(): p.append(f"{c}: searched_record items need a search_log")
            elif not (e.get("url") or "").strip(): p.append(f"{c}: every item other than searched_record needs the URL (or platform reference) it came from")
            if not (e.get("document") or "").strip(): p.append(f"{c}: document title is empty")
    return p


def _check_actions(actions, period):
    p = []
    if not 1 <= len(actions) <= 5: p.append(f"actions: give one to five (got {len(actions)})")
    for a in actions:
        h = (a.get("heading") or "")[:40]
        if not (a.get("heading") or "").strip() or not (a.get("description") or "").strip(): p.append("each action needs a heading and description")
        if not a.get("measures"): p.append(f"action '{h}': needs measures")
        if not PERIOD_RE.match(a.get("target_by") or "") or a["target_by"] <= period: p.append(f"action '{h}': target_by must be a quarter (YYYY-Qn) after {period}")
        if AM_RE.search(json.dumps(a)): p.append(f"action '{h}': must not reference A&M or its services")
    return p


def _check_text(fields, known):
    bad = sorted({c for t in fields for c in _cited(t) if c not in known})
    return [f"narrative cites evidence codes that do not exist: {bad}"] if bad else []


def _recent(date, today):
    try:
        d = dt.date.fromisoformat(date if len(date) == 10 else (date + "-01" if len(date) == 7 else ""))
    except ValueError:
        return False
    return 0 <= (today - d).days <= 90


def _cell(c):
    if not c.get("score"):
        return {"score": None, "confidence": None, "evidence": list(c.get("evidence") or []),
                "na_cause": c.get("na_cause") if c.get("na_cause") not in ("none", None) else "retrieval-limited", "rationale": c.get("rationale") or ""}
    return {"score": c["score"], "confidence": c.get("confidence"), "evidence": list(c.get("evidence") or []), "rationale": c.get("rationale") or ""}


def _evidence_item(e, today):
    item = {"document": e.get("document", ""), "doc_type": e.get("doc_type") or "public", "date": e.get("date", ""), "url": e.get("url", ""),
            "excerpt": e.get("excerpt", ""), "evidence_class": e.get("evidence_class", "direct"),
            "source_origin": "provided" if (e.get("url") or "").startswith("provided:") else "public",
            "simulated": False, "recent": _recent(e.get("date") or "", today)}
    if e.get("search_log"): item["search_log"] = e["search_log"]
    return item


# ---------------------------------------------------------------- grade.py

def _grade(run):
    """Run grade.py on a copy of `run`; returns (blocking problems [(name, where, message)], graded run)."""
    fd, path = tempfile.mkstemp(prefix="run_", suffix=".json"); os.close(fd)
    try:
        Path(path).write_text(json.dumps(run, indent=1, ensure_ascii=True), encoding="ascii")
        r = subprocess.run([sys.executable, "grade.py", path], cwd=SCRIPTS, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env={**os.environ, "PYTHONIOENCODING": "utf-8"}, timeout=300)
        problems = [m.groups() for m in BLOCK_RE.finditer(r.stdout)]
        if r.returncode not in (0, 1) or (r.returncode == 1 and not problems):
            raise ResearchError(f"grade.py failed: {(r.stderr or r.stdout).strip()[-600:]}")
        return problems, json.loads(Path(path).read_text(encoding="utf-8"))
    finally:
        os.unlink(path)


def _problem_text(problems):
    return "\n".join(f"- {where}: {msg}" for _, where, msg in problems)


# ---------------------------------------------------------------- outside-in

class _Subject:
    def __init__(self, name, ticker, role, prefix):
        self.name, self.ticker, self.role, self.prefix, self.short = name, ticker or "", role, prefix, _short(name)
        self.data, self.draft, self.conv = None, None, None

    def accept(self, inp):
        # merge into the latest submission even if it was rejected: Claude is told empty fields keep what it sent before,
        # so a correction that resends only the fixed indicators must still see the evidence list from the first try
        merged = self.draft = _merge(self.draft, inp, SUBJECT_KEYS)
        known = {e.get("code") for e in merged.get("evidence", [])}
        p = _check_evidence(merged.get("evidence", []), self.prefix) + _check_cells(merged.get("indicators", []), known)
        dims = [d.get("dimension") for d in merged.get("dimensions", [])]
        if missing := [d for d in DIMS if d not in dims]: p.append(f"dimensions missing assessment_text and limitations: {missing}")
        for d in merged.get("dimensions", []):
            if not (d.get("assessment_text") or "").strip(): p.append(f"dimension {d.get('dimension')}: assessment_text is empty")
        p += _check_text([(d.get("assessment_text") or "") + (d.get("limitations") or "") for d in merged.get("dimensions", [])]
                         + [c.get("summary") or "" for c in merged.get("indicators", [])], known)
        if not p: self.data = merged
        else: _drop(self.draft, "evidence", "code", {e.get("code") for e in merged.get("evidence", []) if not re.fullmatch(self.prefix + r"\d{2,3}", e.get("code") or "")})
        return p

    def research(self, ctx, band, i):
        def on_block(b):
            if getattr(b, "type", "") == "server_tool_use": band.tick(i, _narrate(self.short, b.name, getattr(b, "input", None)))
        on_phase = _phases(lambda m: band.tick(i, m), {"thinking": f"Weighing the evidence on {self.short}",
                                                       SUBJECT_TOOL["name"]: f"Writing up {self.short}'s scores on the 22 indicators"})
        content = _prompt("subject.md", today=ctx["today"], period=ctx["period"], name=self.name, ticker=self.ticker or "n/a",
                          role="the company being assessed" if self.role == "company" else "peer", peerset=ctx["peerset"],
                          prefix=self.prefix, behaviour_from=ctx["meta"]["document_window"]["behaviour_from"],
                          trend_from=ctx["meta"]["document_window"]["trend_from"], search_budget=SEARCH_BUDGET, fetch_budget=FETCH_BUDGET)
        if self.role == "company" and ctx.get("provided"): content = [{"type": "text", "text": content}] + ctx["provided"]
        self.conv = _Conv(f"research on {self.short}", WEB_TOOLS + [SUBJECT_TOOL], content, on_block, on_phase)
        self.conv.stop = ctx.get("stop")
        band.tick(i, f"Starting research on {self.short}")
        self.conv.submit(SUBJECT_TOOL["name"], self.accept)
        band.tick(i, f"Scored {self.short}'s board on all 22 indicators", done=True)

    def revise(self, text):
        self.conv.say(text)
        self.conv.submit(SUBJECT_TOOL["name"], self.accept)

    def to_run(self, today):
        inds = {c["id"]: {"board": _cell(c)} for c in self.data["indicators"]}
        out = {"name": self.name, "ticker": self.ticker, "role": self.role, "indicators": {i: inds[i] for i in IND_IDS}}
        if self.role == "company":
            dims = {d["dimension"]: d for d in self.data["dimensions"]}
            out["assessment_text"] = {d: dims[d]["assessment_text"] for d in DIMS}
            out["limitations"] = {d: dims[d]["limitations"] for d in DIMS}
        return out

    def evidence(self, today):
        return {e["code"]: _evidence_item(e, today) for e in sorted(self.data["evidence"], key=lambda e: e["code"])}


def _calibration(subjects):
    rows = [{"subject": s.name, "comparables": s.data.get("comparables", []),
             "peer_relative_scores": {c["id"]: c["score"] or "not assessable" for c in s.data["indicators"] if c["id"] in PEER_RELATIVE}}
            for s in subjects]
    return ("All subjects in the peer set are now scored. Their comparables and peer-relative scores (3.2, 5.1, 6.1, 6.2) are:\n"
            + json.dumps(rows, indent=1, ensure_ascii=False)
            + "\nCheck your peer-relative scores against this set ('in line with peers' is 3).")


def _synth_check(syn, peers, known, period):
    p = [f"{k} is empty" for k in ("headline", "overall_summary", "what_moved", "peer_position") if not (syn.get(k) or "").strip()]
    if len(syn.get("headline_findings", [])) != 3: p.append("headline_findings must have exactly three items")
    if not 3 <= len(syn.get("key_metrics", [])) <= 6: p.append("key_metrics needs three to six metrics")
    if len(syn.get("peer_summary_lines", [])) != len(peers): p.append(f"peer_summary_lines needs one line per peer ({len(peers)})")
    if missing := [k for k in DIMS + ["7"] if k not in {x.get("key") for x in syn.get("scorecard_headline", [])}]: p.append(f"scorecard_headline missing keys {missing}")
    if missing := [k for k in DIMS if k not in {x.get("dimension") for x in syn.get("peer_row_summary", [])}]: p.append(f"peer_row_summary missing dimensions {missing}")
    tickers = {(x.get("ticker") or "").upper() for x in syn.get("peer_summaries", [])}
    if missing := [s.ticker or s.name for s in peers if (s.ticker or s.name).upper() not in tickers]: p.append(f"peer_summaries missing for {missing}")
    p += _check_actions(syn.get("actions", []), period)
    texts = [syn.get(k) or "" for k in ("headline", "overall_summary", "what_moved", "peer_position")] + syn.get("headline_findings", []) \
        + syn.get("peer_summary_lines", []) + [x.get("text") or "" for x in syn.get("scorecard_headline", []) + syn.get("peer_row_summary", [])] \
        + [x.get("summary") or "" for x in syn.get("peer_summaries", [])] + [a.get("description") or "" for a in syn.get("actions", [])]
    return p + _check_text([t for t in texts if isinstance(t, str)], known)


def _assemble_oi(ctx, subjects, syn):
    today = ctx["today_date"]; company, peers = subjects[0], subjects[1:]
    evidence = {k: v for s in subjects for k, v in s.evidence(today).items()}
    subs = [s.to_run(today) for s in subjects]
    summaries = {x["ticker"].upper(): x["summary"] for x in syn.get("peer_summaries", [])}
    for s, out in zip(peers, subs[1:]):
        out["summary"] = summaries.get((s.ticker or s.name).upper(), "")
    unavailable = [f"{s.short}: {d}" for s in subjects for d in s.data.get("documents_unavailable", [])]
    period = ctx["period"]
    return {
        "run": copy.deepcopy(ctx["meta"]), "headline": syn.get("headline", ""), "subjects": subs, "evidence": evidence,
        "actions": [{"id": f"{period}-A{n}", **a} for n, a in enumerate(syn.get("actions", []), 1)],
        "coverage": {"documents_unavailable": unavailable, "consistency_result": "Outside-in run 1", "notes": ""},
        "overall_summary": {"board": syn.get("overall_summary", "")}, "what_moved": syn.get("what_moved", ""),
        "headline_findings": syn.get("headline_findings", []), "key_metrics": syn.get("key_metrics", []),
        "peer_position": syn.get("peer_position", ""), "peer_summary_lines": syn.get("peer_summary_lines", []),
        "scorecard_headline": {x["key"]: x["text"] for x in sorted(syn.get("scorecard_headline", []), key=lambda x: x["key"])},
        "indicator_summary": {c["id"]: c["summary"] for c in sorted(company.data["indicators"], key=lambda c: IND_IDS.index(c["id"]))},
        "peer_row_summary": {x["dimension"]: x["text"] for x in sorted(syn.get("peer_row_summary", []), key=lambda x: x["dimension"])},
        "change_notes": {}, "prior_actions_status": [],
        "additional_information_needed": syn.get("additional_information_needed", []), "history": [],
    }


def _digest(graded, subjects):
    out = []
    for s, g in zip(subjects, graded["subjects"]):
        c = g["computed"]
        out.append({"name": s.name, "ticker": s.ticker, "role": s.role,
                    "overall": {k: c["overall"]["board"].get(k) for k in ("grade", "label", "numeric_average", "provisional")},
                    "coverage": c["coverage"]["board"],
                    "dimensions": {d: {k: c["dimensions"][d]["board"][k] for k in ("grade", "average", "assessed", "of")} for d in DIMS},
                    "indicators": {i: {k: g["indicators"][i]["board"].get(k) for k in ("score", "confidence", "rationale")} for i in IND_IDS},
                    "dimension_text": {d["dimension"]: d["assessment_text"] for d in s.data["dimensions"]},
                    "limitations": {d["dimension"]: d["limitations"] for d in s.data["dimensions"]},
                    "comparables": s.data.get("comparables", [])})
    ev = {k: f"{v['document']} ({v['date']}): {v['excerpt']}" for k, v in graded["evidence"].items() if k.startswith("E")}
    return json.dumps({"subjects": out, "company_evidence": ev}, indent=1, ensure_ascii=False)


def _route(problems, subjects):
    by = {s.name: [] for s in subjects}; rest = []
    for pr in problems:
        (by[pr[0]] if pr[0] in by else rest).append(pr)
    return by, rest


def _fix_subjects(subjects, by, extra=None, pool=None):
    jobs = []
    for s in subjects:
        text = ""
        if by.get(s.name): text += f"grade.py reported these blocking problems for {s.name}:\n{_problem_text(by[s.name])}\n"
        if extra: text += extra + "\n"
        if text:
            jobs.append((s, text + "Call submit_subject_assessment again with only the indicators, evidence items, dimensions "
                                   "and comparables that change (empty lists keep what you submitted). If nothing needs to change, "
                                   "call it with all lists empty."))
    list((pool.map if pool else map)(lambda j: j[0].revise(j[1]), jobs))


def _provided(name, documents):
    """Documents the A&M team supplied on the company: read alongside the public record, cited as 'provided: <file>'."""
    blocks = [{"type": "text", "text": f"The A&M team has also supplied {len(documents)} document(s) on {name}, below. Read them alongside the public record. "
               "Where one bears on an indicator, cite it as an evidence item like any other source, with doc_type 'provided document' and url "
               "'provided: <file name>'; the excerpt rule (under 15 words verbatim) applies. They do not replace the web research, and they are "
               "about the company only, not the peers."}]
    for d in documents:
        fname = d.get("name") or "document"
        if d.get("pdf_b64"):
            blocks += [{"type": "text", "text": f"Provided document: {fname}"},
                       {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": d["pdf_b64"]}, "title": fname}]
        elif d.get("text"):
            blocks.append({"type": "text", "text": f'<provided_document file="{fname}">\n{d["text"]}\n</provided_document>'})
    return blocks


def run_outside_in(company: str, ticker: str, peers: list[dict], period: str, mode: str, progress: Progress, documents: list[dict] | None = None) -> dict:
    prog = _Progress(progress)
    if not (company or "").strip(): raise ValueError("company is required")
    if not 2 <= len(peers) <= FW["max_peers"]: raise ValueError(f"choose two to {FW['max_peers']} peers")
    if not PERIOD_RE.match(period or ""): raise ValueError("period must be YYYY-Qn")
    if mode not in FW["run_modes"]: raise ValueError(f"mode must be one of {list(FW['run_modes'])}")
    today = _today()
    meta = {"run_date": today.isoformat(), "period": period, "stage": "outside_in", "mode": mode, "rule_version": FW["rule_version"],
            "document_window": {"behaviour_from": f"{today.year - 2}-{today.month:02d}", "trend_from": f"FY{today.year - 5}"},
            "consistency_run": 1, "simulated": False}
    subjects = [_Subject(company.strip(), ticker, "company", "E")] + [
        _Subject(p["name"].strip(), p.get("ticker", ""), "peer", PEER_PREFIXES[n]) for n, p in enumerate(peers)]
    ctx = {"today": today.isoformat(), "today_date": today, "period": period, "meta": meta, "stop": threading.Event(),
           "peerset": "; ".join(f"{s.name} ({s.ticker or 'n/a'})" for s in subjects),
           "provided": _provided(subjects[0].name, documents) if documents else None}
    prog(2, f"Planning research on {subjects[0].short} and {len(peers)} peers")

    # the company and every peer are researched at the same time: no subject's research depends on another's
    band = _Band(prog, 3, 72, len(subjects))

    def research(a):
        try: a[1].research(ctx, band, a[0])
        except BaseException as e:
            if not ctx["stop"].is_set(): ctx["stop"].set(); ctx["failed"] = e  # the first failure is the one reported
            raise
    with ThreadPoolExecutor(max_workers=min(SUBJECT_WORKERS, len(subjects))) as pool:
        for f in [pool.submit(research, a) for a in enumerate(subjects)]: f.exception()
        if ctx.get("failed"): raise ctx["failed"]

        prog(73, "Comparing the company with its peers on the peer-relative indicators")
        for rnd in range(MAX_FIX_ROUNDS + 1):
            problems, graded = _grade(_assemble_oi(ctx, subjects, {}))
            if rnd > 0 and not problems: break
            if rnd == MAX_FIX_ROUNDS:
                raise ResearchInvalid(f"The scores still break {len(problems)} rule(s) after {MAX_FIX_ROUNDS} fix rounds: "
                                      + "; ".join(f"{n} {w}: {m}" for n, w, m in problems[:5]), problems)
            if problems: prog(74 + 3 * rnd, f"Fixing {len(problems)} rule issue(s) flagged by the grade check")
            by, _ = _route(problems, subjects)
            _fix_subjects(subjects, by, _calibration(subjects) if rnd == 0 else None, pool)

    prog(85, "Writing the headline, findings and actions")
    syn, draft = {}, None

    def accept(inp):
        nonlocal syn, draft
        merged = draft = _merge(draft, inp, SYNTH_KEYS)
        p = _synth_check(merged, subjects[1:], set(graded["evidence"]), period)
        if not p: syn = merged
        return p

    prior = "There is no prior quarter for this company; what_moved explains what drove the grade across dimensions."
    sconv = _Conv("the synthesis", [SYNTH_TOOL], _prompt("synthesis.md", today=ctx["today"], period=period, mode=mode,
                  company=subjects[0].name, prior_note=prior, digest=_digest(graded, subjects)),
                  lambda b: prog(prog.pct + 1 if prog.pct < 93 else prog.pct, "Writing the headline, findings and actions"),
                  _phases(lambda m: prog(prog.pct, m), {"thinking": "Weighing the findings across the peer set", SYNTH_TOOL["name"]: "Writing the headline, findings and actions"}))
    sconv.submit(SYNTH_TOOL["name"], accept)

    prog(95, "Checking the finished assessment against the scoring rules")
    for rnd in range(MAX_FIX_ROUNDS + 1):
        problems, graded = _grade(_assemble_oi(ctx, subjects, syn))
        if not problems: break
        if rnd == MAX_FIX_ROUNDS:
            raise ResearchInvalid(f"The assessment still breaks {len(problems)} rule(s) after {MAX_FIX_ROUNDS} fix rounds.", problems)
        by, rest = _route(problems, subjects)
        _fix_subjects(subjects, by)
        if rest:
            sconv.say(f"grade.py reported these blocking problems:\n{_problem_text(rest)}\nCall submit_synthesis again with the fields that change.")
            sconv.submit(SYNTH_TOOL["name"], accept)
    prog(100, f"Outside-in assessment of {subjects[0].short} complete")
    return graded


# ---------------------------------------------------------------- inside-out

def _io_inputs(run, documents, answers, today):
    names = [d[0] for d in FW["inside_out_priority_docs"]]
    items, blocks, extra = {}, [], 14
    for d in documents:
        slot = int(d.get("slot") or 0); fname = d.get("name") or "document"
        if not (d.get("text") or d.get("pdf_b64")):
            continue
        if 1 <= slot <= len(names) and f"IO{slot:02d}" not in items:
            code, label = f"IO{slot:02d}", names[slot - 1]
        else:  # a second file for the same document type, or an unslotted one
            code, label = f"IO{extra:02d}", (f"{names[slot - 1]}: {Path(fname).stem}" if 1 <= slot <= len(names) else Path(fname).stem); extra += 1
        items[code] = {"document": f"{label} (board document)", "doc_type": "board document", "date": today.isoformat(),
                       "url": "", "excerpt": "", "evidence_class": "inside_out", "source_origin": "inside_out",
                       "simulated": False, "recent": True, "file_name": fname}
        if d.get("pdf_b64"):
            blocks += [{"type": "text", "text": f"Document {code}: {label} (file {fname})"},
                       {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": d["pdf_b64"]}, "title": f"{code} {label}"}]
        else:
            blocks.append({"type": "text", "text": f'<document code="{code}" title="{label}" file="{fname}">\n{d["text"]}\n</document>'})
    qs = FW["questionnaire"]; sa = {}
    for k, a in (answers or {}).items():
        n = int(re.sub(r"\D", "", str(k)) or 0)
        if 1 <= n <= len(qs) and (a or "").strip():
            dim, dname, q = qs[n - 1]
            sa[f"SA{n:02d}"] = {"document": f"Director self-assessment, Q{n} (Dimension {dim}: {dname})", "doc_type": "self-assessment",
                                "date": today.isoformat(), "url": "", "excerpt": a.strip(), "evidence_class": "self_assessment",
                                "source_origin": "self_assessment", "simulated": False, "recent": True, "question": q}
    return items, blocks, dict(sorted(sa.items()))


def _io_check(io, oi_cells, known, io_items, sa, prior, period):
    p = _check_cells(io.get("cells", []), known)
    for c in io.get("cells", []):
        if c.get("carried_forward") or not c.get("score"): continue
        w = f"indicator {c.get('id')}"; ev = c.get("evidence") or []
        if not any(x.startswith(("IO", "SA")) for x in ev):
            p.append(f"{w}: a post inside-out score must cite an IO or SA item, or set carried_forward true")
        if ev and all(x.startswith("SA") for x in ev):
            oi = (oi_cells.get(c.get("id")) or {}).get("score")
            if c["score"] > 3 and (oi is None or c["score"] > oi): p.append(f"{w}: self-assessment alone cannot lift a score above 3 (Rule 19)")
            if c.get("confidence") == "High": p.append(f"{w}: a self-assessment-only cell cannot be High confidence (Rule 19)")
    docs = {d.get("code"): d for d in io.get("documents", [])}
    if bad := [c for c in docs if c not in io_items]: p.append(f"documents lists unknown codes {bad}")
    if missing := [c for c in io_items if c not in docs]: p.append(f"documents needs a date and excerpt for {missing}")
    p += _check_evidence(list(docs.values()))
    p += [f"{k} is empty" for k in ("headline", "overall_summary", "what_moved") if not (io.get(k) or "").strip()]
    if len(io.get("headline_findings", [])) != 3: p.append("headline_findings must have exactly three items")
    p += _check_actions(io.get("actions", []), period)
    pids = [a["id"] for a in prior]; got = {x.get("id"): x for x in io.get("prior_actions_status", [])}
    if missing := [i for i in pids if i not in got]: p.append(f"prior_actions_status needs an entry for {missing}")
    if bad := [i for i in got if i not in pids]: p.append(f"prior_actions_status has unknown action ids {bad}")
    behind = [i for i, x in got.items() if x.get("status") in ("behind", "not_started")]
    if missing := [i for i in behind if i not in {b.get("id") for b in io.get("back_on_track", [])}]: p.append(f"back_on_track needs an entry for {missing}")
    texts = [io.get(k) or "" for k in ("headline", "overall_summary", "what_moved")] + io.get("better", []) + io.get("worse", []) \
        + io.get("headline_findings", []) + [x.get("note") or "" for x in io.get("io_change_notes", [])] \
        + [x.get("evidence_note") or "" for x in io.get("prior_actions_status", [])] + [a.get("description") or "" for a in io.get("actions", [])]
    return p + _check_text([t for t in texts if isinstance(t, str)], known)


def _assemble_io(base, io, io_items, sa, prior, ratings, period):
    run = copy.deepcopy(base)
    comp = next(s for s in run["subjects"] if s["role"] == "company")
    for c in io.get("cells", []):
        if c.get("id") not in comp["indicators"]: continue
        oi = comp["indicators"][c["id"]]["board"]
        if c.get("carried_forward"):
            cell = {k: copy.deepcopy(oi.get(k)) for k in ("score", "confidence", "evidence") if k in oi}
            if oi.get("score") is None: cell["na_cause"] = oi.get("na_cause")
            cell.update(rationale=c.get("rationale") or "Carried forward: the board documents add nothing on this indicator.", carried_forward=True)
        else:
            cell = {**_cell(c), "carried_forward": False}
        comp["indicators"][c["id"]]["board_io"] = cell
    docs = {d.get("code"): d for d in io.get("documents", [])}
    for code, item in io_items.items():
        d = docs.get(code) or {}
        run["evidence"][code] = {**item, "date": d.get("date") or item["date"], "excerpt": d.get("excerpt", "")}
    run["evidence"].update(copy.deepcopy(sa))
    heads = {a["id"]: a.get("heading", "") for a in prior}
    notes = [x for x in io.get("io_change_notes", []) if x.get("id") in IND_IDS]
    run.update(headline=io.get("headline", ""), what_moved=io.get("what_moved", ""), headline_findings=io.get("headline_findings", []),
               inside_vs_outside={"better": io.get("better", []), "worse": io.get("worse", [])},
               io_change_notes={x["id"]: x.get("note", "") for x in sorted(notes, key=lambda x: IND_IDS.index(x["id"]))},
               actions=[{"id": f"{period}-A{n}", **a} for n, a in enumerate(io.get("actions", []), 1)],
               prior_actions_status=[{"id": x.get("id"), "heading": heads.get(x.get("id"), ""), "status": x.get("status"), "evidence_note": x.get("evidence_note", ""),
                                      "metrics_note": x.get("metrics_note", "")} for x in io.get("prior_actions_status", [])],
               back_on_track=[{"id": b.get("id"), "heading": heads.get(b.get("id"), ""), **{k: v for k, v in b.items() if k != "id"}} for b in io.get("back_on_track", [])],
               additional_information_needed=io.get("additional_information_needed", []), self_ratings=ratings)
    run.setdefault("overall_summary", {})["board_io"] = io.get("overall_summary", "")
    return run


def run_inside_out(oi_run: dict, documents: list[dict], answers: dict[str, str], ratings: dict[str, int], progress: Progress) -> dict:
    prog = _Progress(progress)
    if (oi_run.get("run") or {}).get("stage") != "outside_in": raise ValueError("run_inside_out needs an outside-in run")
    today = _today(); period = oi_run["run"]["period"]
    base = copy.deepcopy(oi_run)
    for s in base["subjects"]:
        s.pop("computed", None)
        for ind in s["indicators"].values(): ind.pop("board_io", None)
    base["run"].update(stage="inside_out", run_date=today.isoformat(), simulated=False)
    io_items, blocks, sa = _io_inputs(base, documents, answers, today)
    if not io_items and not sa: raise ValueError("upload at least one board document or answer at least one question")
    ratings = {str(k): int(v) for k, v in (ratings or {}).items() if str(k) in DIMS and int(v) in (1, 3, 5)}
    comp = next(s for s in base["subjects"] if s["role"] == "company"); short = _short(comp["name"])
    hist = sorted(base.get("history", []), key=lambda h: h.get("period", ""))
    prior = hist[-1].get("actions", []) if hist else []
    prog(3, f"Reading {len(io_items)} board document(s) and {len(sa)} questionnaire answer(s)")

    _, oi_graded = _grade(oi_run)
    oc = next(s for s in oi_graded["subjects"] if s["role"] == "company")["computed"]
    oi_cells = {i: comp["indicators"][i]["board"] for i in IND_IDS}
    known = {k for k in base["evidence"] if k.startswith("E")} | set(io_items) | set(sa)
    digest = json.dumps({
        "outside_in": {"overall": oc["overall"]["board"], "dimensions": {d: oc["dimensions"][d]["board"] for d in DIMS},
                       "headline": oi_run.get("headline"), "what_moved": oi_run.get("what_moved"),
                       "headline_findings": oi_run.get("headline_findings"), "cells": oi_cells},
        "outside_in_evidence": {k: f"{v['document']} ({v.get('date', '')}): {v.get('excerpt', '')}" for k, v in base["evidence"].items() if k.startswith("E")},
        "board_documents": {k: v["document"] + f" [file {v['file_name']}]" for k, v in io_items.items()},
        "self_assessment": {k: {"question": v["question"], "answer": v["excerpt"]} for k, v in sa.items()},
        "self_ratings": ratings, "current_actions": oi_run.get("actions", []), "prior_actions": prior,
    }, indent=1, ensure_ascii=False)
    text = _prompt("inside_out.md", today=today.isoformat(), period=period, company=comp["name"], digest=digest)
    steps = iter(["Reading the board documents", "Comparing the board documents with the public record",
                  "Re-scoring the board on the inside view", "Reviewing prior actions"])
    msg = ["Reading the board documents"]

    def on_block(b):
        if getattr(b, "type", "") in ("text", "tool_use", "thinking"): msg[0] = next(steps, msg[0])
        prog(min(prog.pct + 4, 70), msg[0])

    conv = _Conv(f"inside-out review of {short}", [IO_TOOL], blocks + [{"type": "text", "text": text}], on_block,
                 _phases(lambda m: prog(prog.pct, m), {"thinking": "Weighing the board documents against the public record", IO_TOOL["name"]: "Writing up the inside-out scores"}))
    io, draft = {}, None

    def accept(inp):
        nonlocal io, draft
        merged = draft = _merge(draft, inp, IO_KEYS)
        p = _io_check(merged, oi_cells, known, io_items, sa, prior, period)
        if not p: io = merged
        else:
            pids = {a.get("id") for a in prior}
            _drop(draft, "documents", "code", {d.get("code") for d in draft.get("documents", []) if d.get("code") not in io_items})
            for f in ("prior_actions_status", "back_on_track"): _drop(draft, f, "id", {x.get("id") for x in draft.get(f, []) if x.get("id") not in pids})
        return p

    prog(8, "Reading the board documents")
    conv.submit(IO_TOOL["name"], accept)
    prog(75, "Checking the inside-out scores against the scoring rules")
    for rnd in range(MAX_FIX_ROUNDS + 1):
        problems, graded = _grade(_assemble_io(base, io, io_items, sa, prior, ratings, period))
        if not problems: break
        if rnd == MAX_FIX_ROUNDS:
            raise ResearchInvalid(f"The inside-out scores still break {len(problems)} rule(s) after {MAX_FIX_ROUNDS} fix rounds: "
                                  + "; ".join(f"{w}: {m}" for _, w, m in problems[:5]), problems)
        prog(78 + 5 * rnd, f"Fixing {len(problems)} rule issue(s) flagged by the grade check")
        conv.say(f"grade.py reported these blocking problems:\n{_problem_text(problems)}\n"
                 "Call submit_inside_out again with the cells and fields that change.")
        conv.submit(IO_TOOL["name"], accept)
    prog(100, f"Inside-out update for {short} complete")
    return graded

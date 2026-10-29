"""One Claude conversation: streamed requests, server-side pause continuation, refusal handling, and the
submit-until-accepted loop that feeds validation problems back as tool errors."""
from __future__ import annotations

import time

import structlog

from . import client as cl
from . import settings as cfg
from .client import ResearchError, ResearchInvalid, ResearchRefused
from .tools import system_blocks

log = structlog.get_logger("agents.conversation")


def echo(content):
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


def scrub(x):
    """Drops control characters from every string (python-docx and the dashboards cannot take them)."""
    if isinstance(x, str): return cfg.CTRL_RE.sub("", x)
    if isinstance(x, list): return [scrub(v) for v in x]
    if isinstance(x, dict): return {k: scrub(v) for k, v in x.items()}
    return x


class Conv:
    def __init__(self, label, tools, content, on_block=None, on_phase=None, model=None):
        self.label, self.tools, self.on_block, self.on_phase = label, tools, on_block, on_phase
        self.model = model  # None = the default model (BOARD_MODEL); Run B and the reconciliation name theirs
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
        self._check_stop()
        tools = self.tools if self.strict else [{k: v for k, v in t.items() if k != "strict"} for t in self.tools]
        kw = dict(model=self.model or cfg.MODEL, max_tokens=cfg.MAX_TOKENS, system=system_blocks(), tools=tools,
                  messages=self.messages, thinking={"type": "adaptive"}, output_config={"effort": cfg.EFFORT}, cache_control=cfg.CACHE)
        if not cfg.FOUNDRY: kw.update(betas=cfg.BETAS, fallbacks="default")
        with cl.get_client().beta.messages.stream(**kw) as stream:
            beat = time.monotonic()
            for ev in stream:
                self._check_stop()
                # on_phase(block) when Claude starts thinking or writing; on_phase(None) every HEARTBEAT seconds while it does,
                # so long silent stretches (no searches) still show progress
                if self.on_phase and ev.type == "content_block_start": self.on_phase(getattr(ev, "content_block", None)); beat = time.monotonic()
                elif self.on_phase and time.monotonic() - beat > cfg.HEARTBEAT: self.on_phase(None); beat = time.monotonic()
                if self.on_block and ev.type == "content_block_stop" and getattr(ev, "content_block", None) is not None:
                    self.on_block(ev.content_block)
            return stream.get_final_message()

    def _request(self):
        """One streamed request; waits and retries (tenacity, RETRY_WAITS) while the service is busy or unreachable."""
        anthropic = cl.anthropic
        try:
            return cl.call_with_retry(self._stream, self.label, self.stop, getattr(self.on_phase, "say", None))
        except Exception as e:
            if anthropic is None or not isinstance(e, anthropic.APIError): raise
            if isinstance(e, anthropic.BadRequestError) and self.strict and "too complex" in cl._err(e).lower():
                log.warning("strict_schema_rejected", error=cl._err(e))
                self.strict = False
                return self._request()
            raise cl.api_error(e, self.label, self.model) from e

    def turn(self):
        """One model turn, continuing server-side pauses; returns the final message of the turn."""
        for _ in range(cfg.MAX_CONTINUATIONS):
            msg = self._request()
            u = getattr(msg, "usage", None)
            log.info("turn", step=self.label, stop=msg.stop_reason, input=getattr(u, "input_tokens", None),
                     cache_read=getattr(u, "cache_read_input_tokens", None), cache_write=getattr(u, "cache_creation_input_tokens", None),
                     output=getattr(u, "output_tokens", None))
            if msg.stop_reason == "refusal":
                cat = getattr(getattr(msg, "stop_details", None), "category", None)
                raise ResearchRefused(f"Claude declined the {self.label} step{f' ({cat})' if cat else ''}, and so did the "
                                      "fallback model. Nothing was saved; try again or adjust the inputs.")
            self.messages.append({"role": "assistant", "content": echo(msg.content)})
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
                problems = accept(scrub(call.input) if isinstance(call.input, dict) else {})
                if not problems: return
            rejects += 1
            say = getattr(self.on_phase, "say", None)
            if say and rejects <= cfg.MAX_JSON_RETRIES: say(f"Checking {self.label}: {len(problems)} point(s) to correct; asking Claude to fix them")
            if rejects > cfg.MAX_JSON_RETRIES:
                raise ResearchInvalid(f"The {self.label} step returned output that breaks the rules: " + "; ".join(problems[:5]), problems)
            self.say("The submission was not accepted:\n- " + "\n- ".join(problems[:60]) + f"\nFix these and call {tool} again.", error=True)

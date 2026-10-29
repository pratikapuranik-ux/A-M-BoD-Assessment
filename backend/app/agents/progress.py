"""Progress reporting: a monotonic wrapper, a band for parallel tasks, and plain-language narration of what Claude is doing."""
from __future__ import annotations

import re
import threading
import time
from typing import Callable

Progress = Callable[[int, str], None]


class MonotonicProgress:
    def __init__(self, cb): self.cb, self.pct, self.lock = cb, 0, threading.Lock()

    def __call__(self, pct, msg):
        with self.lock:
            self.pct = max(self.pct, min(100, int(pct)))
            if self.cb: self.cb(self.pct, msg)


class Band:
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


def short_name(name):
    n = re.sub(r"\s*\(.*?\)", "", name).strip()
    for _ in range(2):
        n = re.sub(r",?\s+(Corporation|Corp\.?|Incorporated|Inc\.?|p\.l\.c\.|plc|Ltd\.?|Limited|Holdings|Company|Co\.|S\.A\.|SE|AG|N\.V\.)$", "", n, flags=re.I).strip()
    return n or name


def narrate(short, tool, inp):
    text = " ".join(str(v) for v in (inp or {}).values()).lower()
    topic = next((t for pat, t in TOPICS if re.search(pat, text)), None)
    own = short + ("'" if short.endswith("s") else "'s")
    if tool == "web_fetch":
        return f"Reading {own} {topic}" if topic else f"Reading a source document on {short}"
    return f"Searching for {own} {topic}" if topic else f"Searching public sources on {short}"


def phases(say, labels):
    """on_phase callback for Conv: names what Claude is doing (labels: 'thinking' or a tool name -> text), then repeats it
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

"""How many tokens of supplied documents one research request can carry, worked out from the model's context limit.

The limit is what a request may hold in total (BOARD_CONTEXT_TOKENS, 1,000,000 by default). From it come off what every request
already carries: the house prompt and methodology, the web pages the agent keeps in view, the answer it may write, and room for
the conversation to grow. Documents may use a share of what is left; the rest of a subject's documents are searched, not sent.
"""
from __future__ import annotations

import os

from . import settings as cfg

CONTEXT = max(100_000, int(os.environ.get("BOARD_CONTEXT_TOKENS") or 1_000_000))
SHARE = 0.5  # of the room left, how much documents may take
INLINE_CAP = max(10_000, int(os.environ.get("BOARD_DOC_INLINE_TOKENS") or 120_000))  # and never more than this: every turn pays for what is sent
CHARS_PER_TOKEN = 3.2


def fixed_cost() -> int:
    from .tools import system_blocks
    system = sum(len(b.get("text", "")) for b in system_blocks()) / CHARS_PER_TOKEN
    return int(system + cfg.KEEP_RECENT * cfg.FETCH_TOKENS + cfg.MAX_TOKENS + 60_000)


def doc_tokens() -> int:
    """Tokens of supplied documents (text, fact sheets, reviews) to send with one subject's research."""
    return max(20_000, min(INLINE_CAP, int((CONTEXT - fixed_cost()) * SHARE)))

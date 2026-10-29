"""LangGraph state for the two research graphs. The graphs run in-process without a checkpointer, so state may hold
live objects (conversations, a stop Event) next to plain data."""
from __future__ import annotations

from typing import Any, TypedDict


class SubjectTask(TypedDict):
    """Payload of one fan-out branch (research or fix) for a single subject."""
    ctx: dict
    idx: int
    subject: Any            # nodes.Subject
    text: str               # fix jobs only: the message to send into the subject's conversation


class OutsideInState(TypedDict, total=False):
    # inputs
    company: str
    ticker: str
    peers: list[dict]
    period: str
    mode: str
    documents: list[dict] | None
    progress: Any
    shared: dict            # run-wide context created by the caller (stop event, first failure)
    model: str | None       # the model this run's subjects research with (None = BOARD_MODEL)
    # working state
    ctx: dict
    subjects: list          # nodes.Subject, company first
    rnd: int                # fix rounds used in the current loop
    jobs: list              # [(subject, text)] fix jobs for the next fan-out
    rest: list              # blocking problems not attributable to a subject (go to the synthesis)
    graded: dict
    calibrated: bool        # the calibration/fix loop has finished
    done: bool              # the final rule check passed
    synth: Any              # nodes.SynthSession
    # output
    result: dict


class InsideOutState(TypedDict, total=False):
    oi_run: dict
    documents: list[dict]
    answers: dict[str, str]
    ratings: dict[str, int]
    progress: Any
    session: Any            # nodes.InsideOutSession
    rnd: int
    problems: list
    graded: dict
    done: bool
    result: dict

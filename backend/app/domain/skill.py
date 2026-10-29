"""Skill reference data (framework.json, rules v1.2) and the small helpers shared by the engine and the view builder.

Pure logic: no web or DB imports. The framework file is bundled in app/data so the backend does not depend on skill/.
"""
from __future__ import annotations

import json
import math
import os
from fractions import Fraction
from typing import Any

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def _load_fw() -> dict:
    for p in (os.path.join(DATA_DIR, "framework.json"),
              os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "skill", "assets", "framework.json")):
        if os.path.exists(p):
            with open(p, encoding="utf-8") as f:
                return json.load(f)
    raise FileNotFoundError("framework.json not found in backend/app/data or skill/assets")


FW: dict = _load_fw()
DIMS: list[str] = sorted(FW["dimensions"], key=int)
IND: list[dict] = FW["indicators"]
IND_IDS: list[str] = [i["id"] for i in IND]
DIM_OF: dict[str, str] = {i["id"]: i["dimension"] for i in IND}
LV: dict[str, int] = FW["letter_values"]
VL: dict[int, str] = {v: k for k, v in LV.items()}

# Keys of js/data/framework.js (the front end's FW).
FW_KEYS = ["rule_version", "stages", "run_modes", "evidence_classes", "strong_classes", "silence_capped", "searched_record_capped",
           "silence_full", "scoped_pairs", "na_causes", "coverage_threshold", "action_statuses", "max_peers", "grade_scale", "letter_values"]

DRAFT = "DRAFT ONLY — Requires review and approval by a qualified Alvarez and Marsal professional before use."
NAVY, BLUE, AMBER, TEAL, SLATE, GREY = "002B49", "0085CA", "CF7F00", "00677F", "5E8AB4", "646464"
GRADE_FILL = {"A": TEAL, "B": BLUE, "C": SLATE, "D": AMBER, "F": "A6192E", None: "969696"}
SCORE_FILL = {1: "A6192E", 2: AMBER, 3: SLATE, 4: BLUE, 5: TEAL}

# "How to read" and methodology text: build_docx.py's appendix wording, as edited for the app.
READ = [
    "This assessment applies Jeff Bezos's Day 1 / Day 2 lens to a listed company's board, using public information only. Day 1 boards stay obsessed with the customer, make high-velocity decisions, resist proxies and process, embrace external trends, build rather than protect, and manage to cash. Day 2 is what creeps in afterwards.",
    "Six dimensions, 22 indicators. Each indicator is scored 1 (Day 2), 3 (Mixed) or 5 (Day 1) against written anchors, once, for the board. Management's observable actions are attributed to the board's oversight, because a listed board is accountable for what the company does under its watch. Scores of 2 and 4 are used only where evidence meets parts of both adjacent anchors.",
    "Overall grades are the rounded average of the dimension letters (A=5 … F=1; midpoints round down, so 2.5 is a D); provisional where only three dimensions are reported. Where evidence falls below the minimum, an indicator is marked not assessable and excluded rather than scored as Mixed, with the cause recorded (disclosure-limited, retrieval-limited, rule-limited). Peers are assessed on public information only.",
]
RULES = [
    "Every indicator is scored once, for the board; a cell with nothing to assess is marked not applicable.",
    "Scores are 1, 3 or 5; 2 and 4 only where evidence meets parts of both adjacent anchors.",
    "A 1 or 5 requires two independent items from two documents, or one strong direct item (regulator or court record, formal board act, audited figure, or a board document); a 3 requires one.",
    "Confidence is assigned on the evidence: High = two direct sources or one strong source; Medium = one direct or two indirect; Low = a single indirect source, an inference, a silence-based score, or self-assessment alone.",
    "Below the minimum an indicator is not assessable and excluded, never defaulted to 3; silence is scorable in full on 1.4, 5.2, 5.3 and capped at 3 on 2.3, 2.4, 4.3; an empty register search supports up to 3 on 1.3.",
    "A dimension grade is reported only if at least half (outside-in) or two-thirds (post inside-out) of its indicators are assessed.",
    "Overall grade is the rounded average of dimension letters, with midpoints rounding down (for example, an average of 2.5 is a D); provisional at three dimensions; none below three.",
    "Behaviour indicators use 24 months (36 for 2.1 and 4.3); trend indicators five years of filings.",
    "3.2, 5.1, 6.1 and 6.2 are scored relative to the named peer set.",
    "Within scoped pairs an evidence item is primary for one indicator only.",
    "Approved news and trade press (for event facts) are direct evidence; formal board acts are strong direct evidence.",
    "Inside-out: board documents outrank public sources; the post inside-out score must cite at least one inside-out or self-assessment item; self-assessment alone is at most Medium confidence; peers are never re-scored.",
    "Each company is run twice on the same rule version; indicator scores within one point and unchanged dimension letters are required for the result to stand.",
]
METHOD = [f"{k:02d}  {t}" for k, t in enumerate(RULES, 1)]


def framework() -> dict:
    """The framework slice the front end reads (js/data/framework.js FW)."""
    return {k: FW[k] for k in FW_KEYS}


def stage_of(run: dict) -> str:
    return (run.get("run") or {}).get("stage", "outside_in")


def lenses_for(run: dict) -> tuple[list[str], dict]:
    st = FW["stages"][stage_of(run)]
    return st["lenses"], st["labels"]


def to_grade(avg: float) -> tuple[str, str]:
    for band in FW["grade_scale"]:
        if avg >= band["min"]:
            return band["grade"], band["label"]
    return "F", "Day 2 entrenched"


def label_of(grade: str | None) -> str:
    b = next((b for b in FW["grade_scale"] if b["grade"] == grade), None)
    return b["label"] if b else ""


def meets(assessed: int, of: int, threshold: float) -> bool:
    """assessed/of >= threshold, exactly: framework.json stores 1/2 and 2/3 as 0.5 and 0.67, read as the nearest simple
    fraction (0.67 -> 2/3), so 2 of 3 indicators meets the inside-out two-thirds rule."""
    f = Fraction(threshold).limit_denominator(12)
    return of > 0 and assessed * f.denominator >= of * f.numerator


def round_midpoint_down(x: float) -> int:
    """Round to the nearest whole number; midpoints round down (2.5 -> 2, i.e. a D)."""
    return int(math.ceil(x - 0.5 - 1e-9))


def company_of(run: dict) -> dict:
    return next(s for s in run["subjects"] if s.get("role") == "company")


def peers_of(run: dict) -> list[dict]:
    return [s for s in run["subjects"] if s.get("role") == "peer"]


def period_label(run: dict) -> str:
    r = run.get("run", {})
    return r.get("period", r.get("run_date", ""))


def prev_quarter(period: str) -> str:
    """'2026-Q4' -> '2026-Q3'"""
    y, q = period.split("-Q")
    y, q = int(y), int(q) - 1
    if q == 0:
        q, y = 4, y - 1
    return f"{y}-Q{q}"


def grade_delta(new: str | None, old: str | None) -> int | None:
    if not new or not old:
        return None
    return LV[new] - LV[old]


def defs() -> dict[str, Any]:
    """Indicator definitions, board prompt and (outside-in override) anchors, as the view's `defs`."""
    out = {}
    for i in IND:
        ov = (FW.get("outside_in_overrides") or {}).get(i["id"])
        out[i["id"]] = {"def": i["definition"] + ("  (Outside-in anchors applied.)" if ov else ""),
                        "prompt": "Board prompt: " + i.get("board_lens", ""), "anchors": (ov or i)["anchors"]}
    return out


def dim_indicators(d: str) -> list[str]:
    return [i for i in IND_IDS if DIM_OF[i] == d]

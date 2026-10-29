"""Shared helpers for the Day 1 / Day 2 board-only skill scripts."""
import json, os, math, time, uuid
from fractions import Fraction

HERE = os.path.dirname(os.path.abspath(__file__))
FW = json.load(open(os.path.join(HERE, "..", "assets", "framework.json")))
DIMS = sorted(FW["dimensions"].keys(), key=int)
IND = FW["indicators"]; IND_IDS = [i["id"] for i in IND]
DIM_OF = {i["id"]: i["dimension"] for i in IND}
LV = FW["letter_values"]; VL = {v: k for k, v in LV.items()}
NAVY, BLUE, AMBER, TEAL, SLATE, GREY = "002B49", "0085CA", "CF7F00", "00677F", "5E8AB4", "646464"
TINT, TINT2, LIGHT = "EEF7FD", "DAF2FF", "F2F2F2"
GRADE_FILL = {"A": TEAL, "B": BLUE, "C": SLATE, "D": AMBER, "F": "A6192E", None: "969696"}
SCORE_FILL = {1: "A6192E", 2: AMBER, 3: SLATE, 4: BLUE, 5: TEAL}
DRAFT = "DRAFT ONLY — Requires review and approval by a qualified Alvarez and Marsal professional before use."


def stage_of(run):
    return run.get("run", {}).get("stage", "outside_in")


def lenses_for(run):
    st = FW["stages"][stage_of(run)]
    return st["lenses"], st["labels"]


def to_grade(avg):
    for band in FW["grade_scale"]:
        if avg >= band["min"]:
            return band["grade"], band["label"]
    return "F", "Day 2 entrenched"


def meets(assessed, of, threshold):
    """assessed/of >= threshold, exactly: framework.json stores 1/2 and 2/3 as 0.5 and 0.67, read as the nearest simple
    fraction (0.67 -> 2/3), so 2 of 3 indicators meets the inside-out two-thirds rule."""
    f = Fraction(threshold).limit_denominator(12)
    return of > 0 and assessed * f.denominator >= of * f.numerator


def write_json(path, obj):
    """Write via a unique temp file and os.replace, retried while OneDrive or a reader briefly holds the file (Windows)."""
    tmp = os.path.join(os.path.dirname(os.path.abspath(path)), f"~{uuid.uuid4().hex[:10]}.tmp")  # unique, and short (Windows MAX_PATH)
    try:
        with open(tmp, "w") as f: json.dump(obj, f, indent=1)
        for i in range(10):
            try: os.replace(tmp, path); break
            except OSError:
                if i == 9: raise
                time.sleep(0.2)
    finally:
        if os.path.exists(tmp): os.remove(tmp)


def round_midpoint_down(x):
    """Round to the nearest whole number; midpoints round down (2.5 -> 2, i.e. a D)."""
    return int(math.ceil(x - 0.5 - 1e-9))


def company_of(run):
    return next(s for s in run["subjects"] if s.get("role") == "company")


def peers_of(run):
    return [s for s in run["subjects"] if s.get("role") == "peer"]


def period_label(run):
    return run.get("run", {}).get("period", run.get("run", {}).get("run_date", ""))


def prev_quarter(period):
    """'2026-Q4' -> '2026-Q3'"""
    y, q = period.split("-Q"); y, q = int(y), int(q)
    q -= 1
    if q == 0: q, y = 4, y - 1
    return f"{y}-Q{q}"


def grade_delta(new, old):
    if not new or not old: return None
    return LV[new] - LV[old]

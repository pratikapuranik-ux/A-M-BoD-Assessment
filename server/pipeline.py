"""Subprocess wrappers around skill/scripts (the skill stays the source of truth for grading and rendering)."""
from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Callable

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skill", "scripts")
Progress = Callable[[int, str], None]


class PipelineError(Exception):
    pass


def _env() -> dict:
    # The scripts use open() without an encoding; force UTF-8 so non-ASCII run text survives on Windows.
    return dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")


def run_script(*args: str, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *args], cwd=SCRIPTS, capture_output=True, text=True, encoding="utf-8", errors="replace", env=_env(), timeout=timeout)


def _ok(*args: str) -> str:
    r = run_script(*args)
    if r.returncode: raise PipelineError(f"{args[0]} failed: {(r.stderr or r.stdout).strip()[-1500:]}")
    return r.stdout


_LINE = re.compile(r"^\s+(BLOCK|WARN)\s+\[(.*?)\] (.*?): (.*)$")


def grade(path: str, check: bool = False) -> dict:
    """Run grade.py; returns {ok, problems:[str], warnings:[str], output}. Writes `computed` unless check."""
    r = run_script("grade.py", path, *(["--check"] if check else []))
    problems, warnings = [], []
    for ln in r.stdout.splitlines():
        m = _LINE.match(ln)
        if m: (problems if m.group(1) == "BLOCK" else warnings).append(f"[{m.group(2)}] {m.group(3)}: {m.group(4)}")
    if r.returncode not in (0, 1) or (r.returncode == 1 and not problems):
        problems.append("grade.py could not read the run: " + ((r.stderr or r.stdout).strip().splitlines() or ["unknown error"])[-1])
    return {"ok": not problems, "problems": problems, "warnings": warnings, "output": r.stdout}


def load_history(path: str, priors: list[str]) -> str:
    return _ok("load_history.py", path, *priors) if priors else ""


def build_docx(run_path: str, out: str) -> str:
    return _ok("build_docx.py", run_path, out)


def build_dashboard(run_path: str, out: str) -> str:
    return _ok("build_dashboard.py", run_path, out)


def build_questionnaire(company: str, out: str) -> str:
    return _ok("build_questionnaire.py", company, out)


def _period(run: dict) -> str:
    return run.get("run", {}).get("period", "")


def file_names(short: str, oi: dict, io: dict | None, prior: dict | None) -> dict:
    s = re.sub(r"[^A-Za-z0-9]+", "_", short).strip("_") or "Company"
    n = {"oi_docx": f"{s}_{_period(oi)}_Outside-in_Report.docx", "oi_html": f"{s}_{_period(oi)}_Outside-in_Dashboard.html",
         "quest": f"{s}_Self_Assessment_Questionnaire.docx"}
    if io: n.update(io_docx=f"{s}_{_period(io)}_Inside-out_Update.docx", io_html=f"{s}_{_period(io)}_Inside-out_Dashboard.html")
    if prior: n["prior_docx"] = f"{s}_{_period(prior)}_Outside-in_Report.docx"
    return n


def prepare(cid: str, progress: Progress | None = None) -> dict:
    """SKILL.md order: grade priors -> load_history into oi/io -> grade oi/io. Returns grade results by stage."""
    import store
    p = progress or (lambda *_: None)
    res: dict = {}
    with store.lock(cid):
        priors = store.prior_paths(cid)
        for k, pp in enumerate(priors):
            p(5 + k, f"Grading prior {os.path.basename(pp)}"); res[os.path.basename(pp)] = grade(pp)
        for stage in ("outside_in", "inside_out"):
            path = store.run_path(cid, stage)
            if not os.path.exists(path): continue
            if priors: p(15, f"Loading {len(priors)} prior quarter(s) into {stage}"); load_history(path, priors)
            p(20, f"Grading {stage}"); res[stage] = grade(path)
    return res


def build_all(cid: str, parts: set[str] | None = None, progress: Progress | None = None) -> dict:
    """Render deliverables into data/companies/<id>/out and record them in meta.files. parts: subset of oi, io, prior, quest."""
    import store
    p = progress or (lambda *_: None)
    with store.lock(cid):
        meta = store.load_meta(cid); oi = store.read_run(cid, "outside_in"); io = store.read_run(cid, "inside_out")
        priors = store.prior_paths(cid); prior = json.load(open(priors[-1], encoding="utf-8")) if priors else None
        names = file_names(meta.get("short") or meta.get("name", cid), oi, io, prior)
        out = store.out_dir(cid); os.makedirs(out, exist_ok=True)
        files = dict(meta.get("files") or {})
        want = parts or {"oi", "io", "prior", "quest"}
        steps = []
        if "oi" in want: steps += [("oi_docx", build_docx, store.run_path(cid, "outside_in")), ("oi_html", build_dashboard, store.run_path(cid, "outside_in"))]
        if "io" in want and io: steps += [("io_docx", build_docx, store.run_path(cid, "inside_out")), ("io_html", build_dashboard, store.run_path(cid, "inside_out"))]
        if "prior" in want and prior: steps.append(("prior_docx", build_docx, priors[-1]))
        if "quest" in want: steps.append(("quest", build_questionnaire, next(s for s in oi["subjects"] if s.get("role") == "company")["name"]))
        if not io:
            for k in ("io_docx", "io_html"): files.pop(k, None)
        for n, (key, fn, src) in enumerate(steps):
            p(40 + int(55 * n / max(1, len(steps))), f"Building {names[key]}")
            old = files.get(key)
            fn(src, os.path.join(out, names[key])); files[key] = names[key]
            if old and old != names[key]:
                try: os.remove(os.path.join(out, old))
                except OSError: pass
        meta = store.load_meta(cid); meta["files"] = files; store.save_meta(cid, meta)
    p(98, "Deliverables built")
    return files

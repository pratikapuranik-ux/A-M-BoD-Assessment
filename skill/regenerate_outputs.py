#!/usr/bin/env python3
"""Rebuild the example deliverables (run files, Word reports, dashboards, questionnaire, simulated documents)
from skill/example_runs using the skill's own scripts.

    pip install -r requirements.txt
    python regenerate_outputs.py            # writes to skill/out/

Run it from anywhere; paths are relative to this file. Follows SKILL.md: grade -> load_history -> grade -> build.
"""
import os, shutil, subprocess, sys
HERE = os.path.dirname(os.path.abspath(__file__)); SCRIPTS = os.path.join(HERE, "scripts"); OUT = os.path.join(HERE, "out")
os.makedirs(OUT, exist_ok=True)

def run(*args):
    r = subprocess.run([sys.executable, *args], cwd=SCRIPTS, capture_output=True, text=True)
    if r.returncode: sys.exit(f"FAILED: {' '.join(args)}\n{r.stdout}\n{r.stderr}")
    return r.stdout

oi, io, prior = (os.path.join(OUT, n) for n in ("outside_in_run.json", "inside_out_run.json", "prior_2026-Q3_simulated_run.json"))
shutil.copy(os.path.join(HERE, "example_runs", "outside_in_run.json"), oi)
shutil.copy(os.path.join(HERE, "example_runs", "inside_out_run.json"), io)
shutil.copy(os.path.join(HERE, "example_runs", "prior_2026-Q3_simulated_run.json"), prior)

run("grade.py", prior)                                   # grade the simulated prior quarter
for f in (oi, io): run("load_history.py", f, prior)      # ingest it as trend history (max four quarters)
for f in (oi, io): print(run("grade.py", f).splitlines()[-3:])   # rule check + computed grades
run("build_docx.py", oi, os.path.join(OUT, "Chevron_2026-Q4_Outside-in_Report.docx"))
run("build_dashboard.py", oi, os.path.join(OUT, "Chevron_2026-Q4_Outside-in_Dashboard.html"))
run("build_docx.py", io, os.path.join(OUT, "Chevron_2026-Q4_Inside-out_Update_SIMULATED.docx"))
run("build_dashboard.py", io, os.path.join(OUT, "Chevron_2026-Q4_Inside-out_Dashboard_SIMULATED.html"))
run("build_docx.py", prior, os.path.join(OUT, "Chevron_2026-Q3_Outside-in_SIMULATED.docx"))
run("build_questionnaire.py", "Chevron Corporation", os.path.join(OUT, "Chevron_Self_Assessment_Questionnaire.docx"))
run("simulate_inside_out.py", oi, OUT)                   # 13 simulated documents, tracker, filled questionnaire, manifest, zip
print("Done. Files in", OUT)

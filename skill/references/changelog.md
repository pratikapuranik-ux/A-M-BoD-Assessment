# Changelog

## v1.3 (2026-10-28)

Purpose: two runs of the same company should search for, and find, the same evidence.

- Rule 16: retrieval log per subject (Rule 14 items R1-R8, filing-feed sweep to the as-of date, sector-pack registers, fourteen fixed event-sweep queries) and a must-extract fact sheet per indicator. Created by `scripts/init_run.py`; `grade.py` blocks until complete.
- Sector pack for oil, gas and integrated energy (`assets/retrieval_spec.json`): US court dockets, state attorney-general actions, FTC, EPA ECHO, CSB, overseas retail-fuel and energy-retail regulators, EDGAR 8-K / 6-K and RNS feeds, recognised trade press. A `general` pack requires at least one named sector register.
- Rule 17: mechanical checks on source type, evidence class, approved news outlets, recognised trade press and excluded domains; indicator time windows measured from `run.as_of` with `event_date` (required for behaviour indicators; 2.4 judged over five years); `recent` recomputed.
- Rule 18 (optional): second independent run and `scripts/compare_runs.py` (tolerance: within one point, no assessable / not-assessable flip, dimension letters unchanged; peer-relative cells excluded when peer sets differ).
- Rule 19: reconciliation. `compare_runs.py --plan` writes recommendations per differing cell (rule_check, evidence, merge, judgement); the user chooses via tappable options (accept all, review judgement items, review every cell, keep base); `apply_recon.py` applies the decisions, copies adopted evidence and facts, blocks grading on pending re-research and stale text, and the reconciliation log appears in the report and dashboard.
- Not changed: anchors, scoring interpretation, grade scale, rounding (halves down), peer-set handling.
- Runs on v1.2 fail the v1.3 rule-version check; retrofit with `init_run.py <run> --add` and complete the log and fact sheet.

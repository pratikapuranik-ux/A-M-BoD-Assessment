# Spec coverage: what the prototype does against the brief

Status: **Done** = implemented and tested; **Example data** = works, but the worked example (Chevron) is fixed;
**Listed only** = accepted in the UI but not read; **Out of scope** = needs the live skill / a backend.

## Stage 1: outside-in
| Requirement | Status | Where |
|---|---|---|
| Public information plus uploaded reports | Example data; uploads **listed only** | `js/data/chevron.js`, `stage1Setup()` in `js/app.js` |
| 2 to 5 listed peers, each researched as fully as the company | Rule enforced (2 to 5); example holds 2 peers | `validateRun()` in `js/rules.js`, `FW.max_peers` |
| Listed companies only | **Done**: confirmation required before a run | `listed` checkbox, `start1` in `js/app.js` |
| Approved sources only; social media, anonymous forums, employee-review sites excluded | **Done** (notice, sources appendix) | "Approved sources and guardrails" panel, `tMethod()` |
| Trend against up to four prior quarters from earlier `run.json` | **Done**: files parsed in the browser, newest four kept, current period and wrong rule version rejected | `historyFromRun()` (port of `load_history.py`), `loadRunFiles()` |
| If none exist, simulate one prior quarter | **Done** | `S.prior==='simulate'`, `D.prior` |
| Word report and HTML dashboard per stage (light theme) | Pre-built with the skill's scripts for the example. The app offers Word and HTML only; `run.json` is not offered for download (the skill still writes it, see `skill/regenerate_outputs.py`) | `assets/downloads/`, `js/data/downloads.js` |

## Stage 2: inside-out (optional)
| Requirement | Status | Where |
|---|---|---|
| Re-score from 13 board documents | **Done** for the example's simulated findings | `ioCell()` in `js/engine.js`, `D.io.cells` |
| A post inside-out score must cite a supplied document or answer, else carry forward | **Done** | `ioCell()`, `validateCell()` (board_io branch) |
| 12-question self-assessment, built as Word and parsed when returned | **Done**: Word file provided; returned `.docx` read in the browser | `parseQuestionnaire()` (port of `parse_questionnaire.py`) |
| Self-assessment alone can lower a score, never lift above 3 | **Done** | `ioCell()` |
| Keep outside-in grades alongside | **Done** | scorecard, summaries, dashboards |
| Track prior actions; "getting back on track" for those behind | **Done** with simulated statuses; uploaded priors show *no public evidence* (a tracker or minutes are needed) | `priorActionsList()`, `tReport()` |
| Simulate everything (13 documents, tracker, filled questionnaire) | **Done**: "Fill with simulated material" and the ZIP pack | `simall`, `assets/downloads/*pack.zip` |
| Never use inside-out material for peers or other clients | **Done**: peers have no inside-out cell (rule); notice on the page | `validateRun()`, `stage2Input()` |

## Dimensions and indicators
All six dimensions and 22 indicators (including the reworked "Building over Protecting" and the new "Liquidity and Capital
Management") are in `D.ind`, the heat map, the scorecard, the evidence tables and the anchors (Appendix 6).

## Scoring rules (enforced by `js/rules.js`, a port of `grade.py`)
| Rule | Where |
|---|---|
| Scores 1, 3, 5; 2 and 4 only with a rationale naming the parts of both anchors | `validateCell()` |
| 1 or 5 needs two items from two documents, or one strong direct item | `validateCell()` |
| Thin evidence is *not assessable* with a cause (rule, disclosure or retrieval limited); never defaulted to 3 | `validateCell()`, `causeSplit()` |
| Silence / searched-record evidence capped and Low confidence | `validateCell()` |
| Scoped pairs: an evidence item is primary for one indicator only | `validateRun()` |
| Dimension letter needs half (outside-in) or two-thirds (inside-out) of indicators | `compute()` |
| Overall = rounded average of dimension letters; **midpoints round down** (2.5 = D); provisional at three dimensions | `compute()` |
| Grade scale A 4.25+, B 3.50, C 2.75, D 2.00, F below 2.00 | `D.scale` |
| Grades never hand-adjusted | grades are only ever computed |

## Guardrails
| Guardrail | Status | Where |
|---|---|---|
| Board graded as a body; no named individuals | Notice plus language check on answers | `guardrailScan()` |
| Non-accusatory language; no legal conclusions or investment advice | Language check (warnings) | `guardrailScan()`, rule-check warnings |
| Actions do not reference A&M services | **Done** (blocking rule) | `validateRun()` |
| Three run modes control labelling and circulation | **Done**: selector, labels on cover and draft box, circulation line | `FW.run_modes`, `RUN_CIRC`, `cover()` |
| Draft notice on every output | **Done** | `DRAFT` constant |
| Rule version recorded; different versions not compared | **Done** | `run.rule_version`, `historyFromRun()` |

## Known limits of the prototype
- The Word reports and dashboards are pre-built for the Chevron example in *director request* mode; changing the
  run mode relabels the in-app report but not those files. Regenerate them with `skill/regenerate_outputs.py`.
- Reports, board documents and other uploads are listed, not read. Only `run.json` files and the returned questionnaire are parsed.
- The research run is replayed; nothing is retrieved. A live run needs the skill behind an API.
- The company and two peers are fixed to the example.
- The A&M logo files are cropped from a screenshot; replace with the master artwork.

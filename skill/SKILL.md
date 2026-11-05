---
name: day1-day2-board-only-assessment
description: Runs A&M's Day 1 / Day 2 assessment of a listed company's BOARD, grading it A-F on six dimensions and 22 indicators with management's actions attributed to the board. Two stages - an outside-in run from public information and any uploaded reports, benchmarked against up to five peers with quarter-on-quarter trend from prior reports, then an optional inside-out update from board documents and a director self-assessment questionnaire - each producing a Word report and a dashboard. Use whenever a user asks to assess, grade or score a company's board, run a "Day 1 / Day 2" or "Bezos Day 1" board assessment, compare a board with competitors, track how a board's grade moved since last quarter, follow up on board actions, run an inside-out or self-assessment update, or mentions the board assessment tool or "what would Tony and Bryan say about this board". Trigger even if the user only names a company and asks "is this a Day 1 or Day 2 board".
---

# Day 1 / Day 2 Board Assessment (board-only, two-stage)

Grades a listed company's **board** A-F on six dimensions and 22 indicators. Everything the company did under the board's watch is attributed to the board, so there is one score per indicator. Stage 1 is outside-in (public information plus anything the user uploads), benchmarked against two to five peers, with trend against up to four prior quarters. Stage 2, offered after Stage 1 is delivered, re-scores the company from board documents and a self-assessment questionnaire, keeping the outside-in grades alongside. Both stages produce a Word report and a dashboard from one run file each. Everything specific lives in the reference files; read them rather than relying on memory.

## Before starting

1. Read `references/guardrails.md`. Stop if the request cannot be met inside them (a private company, a request to assess named individuals).
2. Read `references/framework.md`, `references/outside_in_overrides.md` and `references/scoring_rules.md` (24 rules; Part D, rules 20-24, governs Stage 2). Keep them open while scoring.
3. Read `references/sources.md` (approved documents, news list, Rule 14 retrieval set) and `references/data_model.md` (the run file the scripts enforce).
4. Confirm web search is on. Scripts run with `python scripts/<name>.py` from the skill folder; all read `assets/framework.json`.

## Stage 1: outside-in

### 1.1 Inputs to confirm

Ask only what is missing, in one message where possible.

- Company and ticker, and that it is listed. The period is the current calendar quarter (`YYYY-Qn`) unless the user says otherwise.
- Peers: two to five listed competitors. If the user names more than five, ask them to shortlist. If none, propose from the same sector and size band and confirm.
- Run mode: `director_request`, `internal_dry_run` or `methodology_pilot`. No written-request check; that happens outside the skill.
- **Report copies.** Ask whether the user wants to provide copies of any reports (annual reports, proxies, transcripts, investor materials) for the company or any peer. Uploaded documents are used first and tagged `source_origin: user_public`; web research fills whatever they do not cover. Peers get the same full research as the company; never partial.
- **Prior reports.** Ask whether a previous outside-in (or outside-in plus inside-out) report exists. If yes, ask for the `run.json` files that came with them (up to four quarters; a Docx alone is a degraded case: parse the scorecard and actions tables and say so). If none exists, run without a trend.
- Sector: `energy` uses the oil and gas pack; otherwise `general`, with at least one sector regulator register named. The as-of date is today unless the user says otherwise.
- Consistency: whether to run the optional second independent run (Rule 18). Default is a single run.

### 1.2 Retrieve the Rule 14 set for the company and every peer

Start the run file with the skeleton, then follow the six retrieval steps in `sources.md` ("How to run the retrieval"):

```bash
python scripts/init_run.py run.json --company "<Name>:<TICKER>" --peer "<Name>:<TICKER>" ... --sector energy --as-of YYYY-MM-DD
```


User documents first, then the Rule 14 retrieval set in `sources.md` for each subject: latest annual report plus five years of cash-flow statements; five years of proxy statements including the pay discussion and governance guidelines; four to eight earnings call transcripts with analyst Q&A; a 24-month 8-K and press sweep and a 36-month sweep for Item 5.02; any merger proxy; the sector regulator registers for 1.3; investor day and sector conference materials; ISS, Glass Lewis and rating agency reports where reachable. No source is gated on a licence; the publisher's reputation is the test. Peers get the same full research as the company, never partial. Record anything not retrievable under `coverage.documents_unavailable` and mark affected cells `retrieval-limited`. Work indicator by indicator using the source types in `framework.md`.

### 1.3 Build evidence and score

Every supporting fact is an evidence item with document, date, URL or platform reference, a short excerpt (under 15 words verbatim), an `evidence_class`, `source_origin`, `source_type` (with `outlet` for news and trade press) and, where the event predates the document, `event_date`. `recent` is recomputed by `grade.py`. Fill the fact sheet before scoring: each score should rest on the facts recorded for that indicator. Tag formal board acts `board_act`, audited figures and regulator or court records `strong_direct`, analyst and proxy-advisor material `indirect`, empty register searches `searched_record` with a `search_log`, absent expected disclosures `silence`.

Score each of the 22 indicators once, in the `board` cell, against the anchors (override anchors for 1.2 and 4.1), using the board prompt that attributes management's actions to the board. Write the rationale as two or three sentences for the reader with evidence codes inline (`[E07]`); the outputs show rationale, not raw evidence. If the minimum is not met after the retrieval set is searched, score `null`, set `na_cause`, list what was searched; never write 3 for "don't know". Score every peer at indicator level with the same care. Then write, per dimension, `assessment_text` (first sentence is the headline) and `limitations`.

### 1.4 Grade and trend

```bash
python scripts/grade.py run.json
python scripts/load_history.py run.json prior_2026-Q3.json [prior_2026-Q2.json ...]   # if prior run files exist
python scripts/grade.py run.json                                                           # re-run after history is loaded
```

`grade.py` checks stage, mode, rule version and period, the retrieval log, fact sheet, source types and time windows (Rules 16-17), computes dimension grades (half-coverage rule), the overall grade (rounded average of dimension letters, midpoints round down; provisional at three dimensions), coverage and the not-assessable split, and lists every rule violation. Fix all blocking issues; never adjust a grade by hand.

### 1.4a. Optional consistency run (Rule 18)

If the user chose the double run, research and score again, independently, from a fresh `init_run.py` file (do not copy evidence or scores from the first run), grade it, then:

```bash
python scripts/compare_runs.py run.json run_b.json --out comparison.md --record
```

On REVIEW, reconcile the two runs (step 1.4b) rather than picking one silently.

### 1.4b. Reconcile two runs (Rule 19)

Use after a consistency run, or whenever the user supplies another run of the same company and asks to reconcile, compare or align them. The base run is the one being delivered (normally the current one).

1. **Build the plan.** `python scripts/compare_runs.py base.json other.json --out comparison.md --plan recon_plan.json`. Every differing cell gets a basis and a recommendation: `rule_check` (one cell breaks a mechanical rule), `evidence` (one run assessed the cell or found facts the other did not), `merge` (each run holds facts the other lacks: re-research), `judgement` (same facts, different reading of the anchor), or `not_comparable` (peer-relative cell with different peer sets).
2. **Complete the judgement items.** For each `judgement` item, read both rationales and the evidence behind them, then write `analyst_recommendation` (`keep_a`, `adopt_b` or `re_research`) and `analyst_reason` (two sentences citing evidence from both runs, labelled as the analyst's view). Do not change anchors or rules to settle them.
3. **Offer the user the choice.** Show a short table (cell, scores in each run, basis, recommendation, reason), then ask with tappable options (`ask_user_input_v0` where available):
   - Accept all recommendations
   - Accept the rule-check and evidence items; review judgement items one by one
   - Review every cell one by one
   - Keep the base run as it is

   For cell-by-cell review, offer per cell: accept the recommendation, keep base, adopt the other run, re-research. Record each answer in the plan's `decision` field (`recommended`, `keep_a`, `adopt_b`, `re_research`) and the person deciding in `decided_by`. Never fill a decision the user has not made.
4. **Apply.** `python scripts/apply_recon.py base.json other.json recon_plan.json reconciled.json`. Adopted cells bring their evidence (ids suffixed `-B`) and fact-sheet entries; re-research cells are cleared and marked pending.
5. **Finish.** Research and score each pending cell (or mark it not assessable with its cause), rewrite every field listed in `run.reconciliation.stale_text`, then empty that list. `grade.py` blocks until both are done. Render as usual; the report and dashboard carry the reconciliation log.

If the other run exists only as a Docx, parse its scorecard and indicator tables into a scores-only run file and say so: without its evidence and fact sheet most items fall to `judgement`.

### 1.5 Synthesis fields

With grades in view, write: `headline`; `overall_summary.board`; `what_moved` (what drove the grade across dimensions, and against the prior quarter if there is one); `headline_findings`; `key_metrics` (metrics with a material bearing on performance: metric, why, current value); `peer_position` and `peer_summary_lines` (one line per peer: better, worse or at par, on what); `peer_row_summary` (per dimension, how the company compares with each peer); `change_notes` (per indicator whose score moved since the prior quarter, the evidence that moved it); up to five `actions`, each specific and directly tied to a finding ("Add a customer-harm watch list to board packs", "Schedule directors' frontline sessions without management"), with `measures` and `target_by`; a `summary` per peer. If prior actions exist, do not force a status from public information; leave `prior_actions_status` empty and say it will be asked for in Stage 2. Add `additional_information_needed` only if a specific document would change a grade or an action.

### 1.6 Render and deliver

```bash
python scripts/build_dashboard.py run.json "<Company> <period> Day1-Day2 Dashboard.html"
python scripts/build_docx.py run.json "<Company> <period> Day1-Day2 Board Assessment.docx"
```

Publish the HTML as an artifact when the Artifact tool is available; present the Docx **and the run.json** (the user needs it for next quarter's trend). Run the quality checks in `references/output_structures.md`, including rendering the Docx to PDF and checking the body fits five pages (six with trend tables). Then offer Stage 2.

## Stage 2: inside-out update (offered after Stage 1 is delivered)

### 2.1 The offer

In one message: list the inside-out documents that would move the assessment most (the first seven in `references/inside_out_documents.md`, each with the indicators it settles and, where relevant, the specific not-assessable cells from Stage 1), and ask the user to upload what they can. Offer the **self-assessment questionnaire**: build it with `build_questionnaire.py "<Company>" questionnaire.docx` and present it (12 dimension-level questions, about 30 minutes, editable answer boxes). If there were prior actions, say the documents should show their status.

### 2.2 Analyse only the new material

Copy the Stage 1 run file to a new file, set `run.stage` to `inside_out` and a new `run_date`; keep `period`. Read every supplied document and the returned questionnaire (`parse_questionnaire.py io_run.json filled.docx` turns the answers into `SA` evidence items). Add `IO` evidence items for the documents (`evidence_class: inside_out`, `source_origin: inside_out`). Do not re-research peers and do not change any outside-in cell.

For each indicator, fill the `board_io` cell: the post-inside-out score with its rationale written as "outside-in showed X; the board documents add Y", citing at least one `IO` or `SA` item, or `carried_forward: true` with the outside-in score when the documents add nothing. Self-assessment alone cannot lift a score above 3 (Rule 19). Record the status of each prior action in `prior_actions_status` with evidence, and a `back_on_track` entry for each action behind or not started (what happened, impact, root cause, mechanism to prevent, measures to track). Write `inside_vs_outside` (where the inside view is better and worse than the public record), `io_change_notes`, updated `actions`, updated `what_moved`, and `additional_information_needed` only if still warranted. Then:

```bash
python scripts/grade.py io_run.json
python scripts/build_dashboard.py io_run.json "<Company> <period> Day1-Day2 Inside-out Dashboard.html"
python scripts/build_docx.py io_run.json "<Company> <period> Day1-Day2 Inside-out Update.docx"
```

The inside-out report is a second, standalone report and dashboard: both grades side by side everywhere, trend on both, peers carried forward with a note, updated actions, back-on-track analysis, and Appendix 3 listing every source as public, inside-out or self-assessment. Present the Docx, the HTML and `io_run.json`.

## Delivery notes

Each delivery message states the overall grade (both grades in Stage 2), the three headline findings, the coverage line (assessed / 22 with the split by cause) and, in Stage 2, the prior-action statuses. Append the A&M draft notice: "DRAFT ONLY - Requires review and approval by a qualified Alvarez and Marsal professional before use." Circulation follows the run mode.

## Scripts

| Script | Purpose |
|---|---|
| `grade.py` | Validate rules (incl. retrieval log, fact sheet, sources, windows), compute grades and coverage for either stage. |
| `init_run.py` | Start a run file with the retrieval log and fact sheet for every subject (`--add` retrofits an existing run). |
| `retrieval_checks.py` | Rules 16-17 checks, called by grade.py. |
| `compare_runs.py`, `recon.py`, `apply_recon.py` | Compare two runs and reconcile them (Rules 18-19). |
| `load_history.py` | Ingest prior run files (max four quarters) into `history`. |
| `build_questionnaire.py` | Self-assessment Word file (blank answer boxes). |
| `parse_questionnaire.py` | Returned questionnaire to `SA` evidence items. |
| `build_dashboard.py`, `build_docx.py` | Render either stage. |

## Reference files

| File | When to read |
|---|---|
| `references/guardrails.md` | Always, first. |
| `references/framework.md`, `references/outside_in_overrides.md` | While scoring: indicators, anchors, merged board prompt, overrides for 1.2 and 4.1. |
| `references/scoring_rules.md` | Rules 1-19 (outside-in), Part D rules 20-24 (Stage 2), grade scale, overall method. |
| `references/sources.md` | Approved sources, news list, Rule 14 retrieval set. |
| `references/inside_out_documents.md` | The thirteen inside-out documents, what each settles, priority order for the Stage 2 offer. |
| `references/data_model.md` | Every run-file field the scripts read or enforce, for both stages. |
| `references/output_structures.md` | Report and dashboard structures for both stages, page budget, quality checks. |
| `references/changelog.md` | What changed in v1.3 and how to retrofit a v1.2 run. |
| `assets/framework.json` | Machine-readable framework; do not edit by hand. |
| `assets/retrieval_spec.json` | Retrieval items, sector packs (registers, filing feeds, trade press), event-sweep queries, fact sheet, source allowlist. |

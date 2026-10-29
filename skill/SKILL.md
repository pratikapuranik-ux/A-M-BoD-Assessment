---
name: day1-day2-board-only-assessment
description: Runs A&M's Day 1 / Day 2 assessment of a listed company's BOARD, grading it A-F on six dimensions and 22 indicators with management's actions attributed to the board. Two stages - an outside-in run from public information and any uploaded reports, benchmarked against up to five peers with quarter-on-quarter trend from prior reports, then an optional inside-out update from board documents and a director self-assessment questionnaire - each producing a Word report and a dashboard. Use whenever a user asks to assess, grade or score a company's board, run a "Day 1 / Day 2" or "Bezos Day 1" board assessment, compare a board with competitors, track how a board's grade moved since last quarter, follow up on board actions, run an inside-out or self-assessment update, or mentions the board assessment tool or "what would Tony and Bryan say about this board". Trigger even if the user only names a company and asks "is this a Day 1 or Day 2 board".
---

# Day 1 / Day 2 Board Assessment (board-only, two-stage)

Grades a listed company's **board** A-F on six dimensions and 22 indicators. Everything the company did under the board's watch is attributed to the board, so there is one score per indicator. Stage 1 is outside-in (public information plus anything the user uploads), benchmarked against two to five peers, with trend against up to four prior quarters. Stage 2, offered after Stage 1 is delivered, re-scores the company from board documents and a self-assessment questionnaire, keeping the outside-in grades alongside. Both stages produce a Word report and a dashboard from one run file each. Everything specific lives in the reference files; read them rather than relying on memory.

## Before starting

1. Read `references/guardrails.md`. Stop if the request cannot be met inside them (a private company, a request to assess named individuals).
2. Read `references/framework.md`, `references/outside_in_overrides.md` and `references/scoring_rules.md` (21 rules; Part D, rules 17-21, governs Stage 2). Keep them open while scoring.
3. Read `references/sources.md` (approved documents, news list, Rule 15 retrieval set) and `references/data_model.md` (the run file the scripts enforce).
4. Confirm web search is on. Scripts run with `python scripts/<name>.py` from the skill folder; all read `assets/framework.json`.

## Stage 1: outside-in

### 1.1 Inputs to confirm

Ask only what is missing, in one message where possible.

- Company and ticker, and that it is listed. The period is the current calendar quarter (`YYYY-Qn`) unless the user says otherwise.
- Peers: two to five listed competitors. If the user names more than five, ask them to shortlist. If none, propose from the same sector and size band and confirm.
- Run mode: `director_request`, `internal_dry_run` or `methodology_pilot`. No written-request check; that happens outside the skill.
- **Report copies.** Ask whether the user wants to provide copies of any reports (annual reports, proxies, transcripts, investor materials) for the company or any peer. Uploaded documents are used first and tagged `source_origin: user_public`; web research fills whatever they do not cover. Peers get the same full research as the company; never partial.
- **Prior reports.** Ask whether a previous outside-in (or outside-in plus inside-out) report exists. If yes, ask for the `run.json` files that came with them (up to four quarters; a Docx alone is a degraded case: parse the scorecard and actions tables and say so). If none exists, offer to **simulate one prior quarter** so the trend and action-status sections can be tested. If accepted, run `simulate_prior.py` after step 1.4 and deliver the simulated report with the real one.
- Whether this is run 1 or run 2 (the consistency test).

### 1.2 Retrieve the Rule 15 set for the company and every peer

User documents first, then the minimum retrieval set in `sources.md` for each subject: latest annual report plus five years of cash-flow statements; five years of proxy statements including the pay discussion and governance guidelines; four to eight earnings call transcripts with analyst Q&A; a 24-month 8-K and press sweep and a 36-month sweep for Item 5.02; any merger proxy; the sector regulator registers for 1.3; investor day and sector conference materials; ISS, Glass Lewis and rating agency reports where reachable. No source is gated on a licence; the publisher's reputation is the test. Record anything not retrievable under `coverage.documents_unavailable` and mark affected cells `retrieval-limited`. Work indicator by indicator using the source types in `framework.md`.

### 1.3 Build evidence and score

Every supporting fact is an evidence item with document, date, URL or platform reference, a short excerpt (under 15 words verbatim), an `evidence_class`, `source_origin` (`public` or `user_public`), `simulated: false` and a `recent` flag. Tag formal board acts `board_act`, audited figures and regulator or court records `strong_direct`, analyst and proxy-advisor material `indirect`, empty register searches `searched_record` with a `search_log`, absent expected disclosures `silence`.

Score each of the 22 indicators once, in the `board` cell, against the anchors (override anchors for 1.2 and 4.1), using the board prompt that attributes management's actions to the board. Write the rationale as two or three sentences for the reader with evidence codes inline (`[E07]`); outputs show rationale, not raw evidence. If the minimum is not met after the Rule 15 set is searched, score `null`, set `na_cause`, list what was searched; never write 3 for "don't know". Score every peer at indicator level with the same care. Then write, per dimension, `assessment_text` (first sentence is the headline), `scorecard_headline` and `limitations`; per indicator, `indicator_summary` (one line).

### 1.4 Grade, trend, simulate if asked

```bash
python scripts/grade.py run.json
python scripts/load_history.py run.json prior_2026-Q3.json [prior_2026-Q2.json ...]   # if prior run files exist
python scripts/simulate_prior.py run.json prior_sim.json && python scripts/grade.py prior_sim.json \
  && python scripts/build_docx.py prior_sim.json "<Company> <prior period> Day1-Day2 SIMULATED.docx" \
  && python scripts/load_history.py run.json prior_sim.json                               # if the user chose simulation
python scripts/grade.py run.json                                                           # re-run after history is loaded
```

`grade.py` checks stage, mode, rule version and period, computes dimension grades (half-coverage rule), the overall grade (rounded average of dimension letters, midpoints round down; provisional at three dimensions), coverage and the not-assessable split, and lists every rule violation. Fix all blocking issues; never adjust a grade by hand.

### 1.5 Synthesis fields

With grades in view, write: `headline`; `overall_summary.board`; `what_moved` (what drove the grade across dimensions, and against the prior quarter if there is one); `headline_findings`; `key_metrics` (metrics with a material bearing on performance: metric, why, current value); `peer_position` and `peer_summary_lines` (one line per peer: better, worse or at par, on what); `peer_row_summary` (per dimension, how the company compares with each peer); `change_notes` (per indicator whose score moved since the prior quarter, the evidence that moved it); up to five `actions`, each specific and directly tied to a finding ("Add a customer-harm watch list to board packs", "Schedule directors' frontline sessions without management"), with `measures` and `target_by`; a `summary` per peer. If prior actions exist, do not force a status from public information; leave `prior_actions_status` empty and say it will be asked for in Stage 2. Add `additional_information_needed` only if a specific document would change a grade or an action.

### 1.6 Render and deliver

```bash
python scripts/build_dashboard.py run.json "<Company> <period> Day1-Day2 Dashboard.html"
python scripts/build_docx.py run.json "<Company> <period> Day1-Day2 Board Assessment.docx"
```

Publish the HTML as an artifact when the Artifact tool is available; present the Docx **and the run.json** (the user needs it for next quarter's trend), plus the simulated prior report if one was made. Run the quality checks in `references/output_structures.md`, including rendering the Docx to PDF and checking the body fits five pages (six with trend tables). Then offer Stage 2.

## Stage 2: inside-out update (offered after Stage 1 is delivered)

### 2.1 The offer

In one message: list the inside-out documents that would move the assessment most (the first seven in `references/inside_out_documents.md`, each with the indicators it settles and, where relevant, the specific not-assessable cells from Stage 1), and ask the user to upload what they can. Offer the **self-assessment questionnaire**: build it with `build_questionnaire.py "<Company>" questionnaire.docx` and present it (12 dimension-level questions, about 30 minutes, editable answer boxes). For the prototype, also offer to **simulate all of it**: `simulate_inside_out.py run.json out_dir` produces thirteen board documents, an action tracker workbook, a filled questionnaire and a manifest, zipped; present the zip so the tester can see what the analysis had. If there were prior actions, say the documents should show their status.

### 2.2 Analyse only the new material

Copy the Stage 1 run file to a new file, set `run.stage` to `inside_out` and a new `run_date`; keep `period`. Read every supplied document (or the simulated set) and the returned questionnaire (`parse_questionnaire.py io_run.json filled.docx` turns the answers into `SA` evidence items). Add `IO` evidence items for the documents (`evidence_class: inside_out`, `source_origin: inside_out`, `simulated` as applicable). Do not re-research peers and do not change any outside-in cell.

For each indicator, fill the `board_io` cell: the post-inside-out score with its rationale written as "outside-in showed X; the board documents add Y", citing at least one `IO` or `SA` item, or `carried_forward: true` with the outside-in score when the documents add nothing. Self-assessment alone cannot lift a score above 3 (Rule 19). Record the status of each prior action in `prior_actions_status` with evidence, and a `back_on_track` entry for each action behind or not started (what happened, impact, root cause, mechanism to prevent, measures to track). Write `inside_vs_outside` (where the inside view is better and worse than the public record), `io_change_notes`, updated `actions`, updated `what_moved`, and `additional_information_needed` only if still warranted. Then:

```bash
python scripts/grade.py io_run.json
python scripts/build_dashboard.py io_run.json "<Company> <period> Day1-Day2 Inside-out Dashboard.html"
python scripts/build_docx.py io_run.json "<Company> <period> Day1-Day2 Inside-out Update.docx"
```

The inside-out report is a second, standalone report and dashboard: both grades side by side everywhere, trend on both, peers carried forward with a note, updated actions, back-on-track analysis, and Appendix 3 listing every source as public, inside-out or self-assessment and whether it was simulated. Present the Docx, the HTML and `io_run.json`.

## Delivery notes

Each delivery message states the overall grade (both grades in Stage 2), the three headline findings, the coverage line (assessed / 22 with the split by cause) and, in Stage 2, the prior-action statuses. Append the A&M draft notice: "DRAFT ONLY - Requires review and approval by a qualified Alvarez and Marsal professional before use." Circulation follows the run mode. Anything simulated is labelled SIMULATED in the file name and in the outputs.

## Scripts

| Script | Purpose |
|---|---|
| `grade.py` | Validate rules, compute grades and coverage for either stage. |
| `load_history.py` | Ingest prior run files (max four quarters) into `history`. |
| `simulate_prior.py` | Simulated prior quarter with minor movements and prior actions. |
| `build_questionnaire.py` | Self-assessment Word file; `--simulate-answers` fills it. |
| `parse_questionnaire.py` | Returned questionnaire to `SA` evidence items. |
| `simulate_inside_out.py` | Thirteen simulated board documents, tracker, filled questionnaire, manifest, zip. |
| `build_dashboard.py`, `build_docx.py` | Render either stage. |

## Reference files

| File | When to read |
|---|---|
| `references/guardrails.md` | Always, first. |
| `references/framework.md`, `references/outside_in_overrides.md` | While scoring: indicators, anchors, merged board prompt, overrides for 1.2 and 4.1. |
| `references/scoring_rules.md` | Rules 1-16 (both stages), Part D rules 17-21 (Stage 2), grade scale, overall method. |
| `references/sources.md` | Approved sources, news list, Rule 15 retrieval set. |
| `references/inside_out_documents.md` | The thirteen inside-out documents, what each settles, priority order for the Stage 2 offer. |
| `references/data_model.md` | Every run-file field the scripts read or enforce, for both stages. |
| `references/output_structures.md` | Report and dashboard structures for both stages, page budget, quality checks. |
| `assets/framework.json` | Machine-readable framework; do not edit by hand. |
| `assets/example_run.json`, `assets/example_run_inside_out.json` | Fictional, complete examples of each stage's run file. |

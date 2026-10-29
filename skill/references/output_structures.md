# Output structures (v1.2, board-only, two stages)

Both outputs come from the same run file via the scripts, in A&M visual style (navy 002B49, blue 0085CA, amber CF7F00, teal 00677F, Arial). Change the scripts, not the outputs.

## Word report (`build_docx.py`)

Page breaks only after the cover, after the executive summary and before the appendices (peer one-pagers in the appendix each start on a new page). The body (sections 2-7) is written to fit five pages; six is acceptable when trend tables are present.

1. **Cover.** Navy title block (title, "Inside-out update" in Stage 2, company, period, basis, peers, date); purpose / basis / trend / evidence-window table; draft notice with run mode.
2. **Executive summary.** Grade tile(s) with prior-quarter change; what moved the rating (summary across dimensions); Stage 2 only: inside view against the public record (better / worse); key actions; metrics worth tracking; position relative to peers with one line per peer.
3. **Scorecard and trend.** Dimension grades with up to four prior quarters, the current grade(s), change arrow, and one line of evidence per dimension; coverage line with the outside-in caveat. "What changed since <prior quarter>" table (indicator, prior, now, delta, evidence). Stage 2 adds "Outside-in to post inside-out: indicators that moved" (outside-in evidence, then what the documents added).
4. **Evidence behind each indicator.** One row per indicator: score(s) and a one-line evidence summary with codes linked to the sources appendix.
5. **Peer comparison.** Dimension grades for the company (outside-in) and up to five peers, with a per-row summary of how the company compares; overall row; peer trend (last quarter and this quarter, overall) when history exists. Stage 2 carries the note that peers are compared on outside-in grades only.
6. **Actions.** Up to five, numbered, each with description, measures and target quarter. Status of prior actions (six statuses, with evidence and metrics) when known; in Stage 1 a note that status is asked for in Stage 2.
7. **Getting back on track.** Only when an action is behind or not started: what happened, impact, root cause, mechanism to prevent, measures to track.
8. **Additional information that would sharpen the assessment.** Only when a specific document would change a grade or action.
9. **Appendices.** Appendix 1: detailed indicator view (per dimension, assessment text, full rationale with linked codes, confidence). Appendix 2: one page per peer (grade strip, summary, 22-row indicator table). Stage 2 only, Appendix 3: data sources (one line each; origin public / inside-out / self-assessment; simulated yes/no; used for). Then: how to read; methodology and rules; sources consulted (bookmarked entries with excerpt, question for SA items, search log, link, SIMULATED flag); indicator definitions and anchors.

## Dashboard (`build_dashboard.py`)

Same order: header band with run-mode label; executive summary (tiles with prior-quarter change, what moved, inside-vs-outside in Stage 2, key actions, metrics, peer position); scorecard and trend with the what-changed tables; evidence by indicator (one-line summaries; a dimension expands to the detailed rationale with evidence behind info icons; "?" opens definition and anchors); peer comparison with row summaries, peer trend and a collapsible indicator view per peer; actions with prior-action statuses; getting back on track; additional information; coverage and limitations (assessed / 22, split by cause, confidence, simulated items); evidence accordion (collapsed; filters by dimension, origin, indicator; free text); methodology footer.

## Quality checks before delivering

- Docx rendered to PDF: body within the page budget; only the three body page breaks; grade cells coloured; Appendix links resolve.
- Dashboard: every dimension expands, both icons work, peer indicator views open, evidence accordion opens, nothing shows as missing.
- Scores shown equal what grade.py reported as assessed, for each lens.
- No named individual characterised; no quote over 15 words; run-mode label correct; everything simulated labelled SIMULATED.
- run.json delivered with the report.

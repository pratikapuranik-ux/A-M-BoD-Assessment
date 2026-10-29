# Run data model (run.json), rules v1.2, board-only, two stages

One JSON file per stage per quarter. `grade.py` validates it and writes `computed`; the renderers read it. Always deliver the file with the report: the next quarter's trend and action tracking depend on it.

```json
{
  "run": {"run_date": "2026-10-28", "period": "2026-Q4", "stage": "outside_in | inside_out",
          "mode": "director_request | internal_dry_run | methodology_pilot", "rule_version": "1.2",
          "document_window": {"behaviour_from": "2024-10", "trend_from": "FY2021"}, "consistency_run": 1, "simulated": false},
  "headline": "One line for the executive summary.",
  "subjects": [
    {"name": "Example Corp", "ticker": "EXMP", "role": "company",
     "indicators": {"1.1": {
        "board":    {"score": 3, "confidence": "Medium", "evidence": ["E01"], "rationale": "What the board did, with codes inline [E01]."},
        "board_io": {"score": 5, "confidence": "High", "evidence": ["IO03", "SA01"], "rationale": "Outside-in showed X; the board documents add Y [IO03] [SA01].", "carried_forward": false}},
       "1.2": {"board": {"score": null, "confidence": null, "evidence": [], "na_cause": "disclosure-limited", "rationale": "Not assessable. Searched: ..."}}},
     "assessment_text": {"1": "First sentence is the headline. Then about 80 words."}, "limitations": {"1": "One line."}},
    {"name": "Peer One", "role": "peer", "indicators": {"...": "board cells only, scored fully"}, "summary": "Two sentences for the peer page."}
  ],
  "evidence": {
    "E01":  {"document": "...", "doc_type": "10-K", "date": "2026-02-20", "url": "https://...", "excerpt": "<15 words", "evidence_class": "strong_direct", "source_origin": "public", "simulated": false, "recent": false},
    "E09":  {"document": "FDA recall database search", "evidence_class": "searched_record", "search_log": "register; terms; date; result", "source_origin": "public"},
    "IO03": {"document": "Board pack extracts (board document)", "evidence_class": "inside_out", "source_origin": "inside_out", "simulated": true, "date": "2026-11-01"},
    "SA01": {"document": "Director self-assessment, Q1 (Dimension 1)", "evidence_class": "self_assessment", "source_origin": "self_assessment", "question": "...", "excerpt": "answer"}
  },
  "history": ["written by load_history.py: period, stage, simulated, dimension grades per lens, overall, indicator scores, peers, actions"],
  "overall_summary": {"board": "One sentence per lens.", "board_io": "..."},
  "what_moved": "Summary across dimensions of what drove the grade (and vs the prior quarter).",
  "inside_vs_outside": {"better": ["...[IO01]"], "worse": ["...[IO03]"]},
  "headline_findings": ["...", "...", "..."],
  "key_metrics": [{"metric": "...", "why": "...", "current": "..."}],
  "peer_position": "One sentence.", "peer_summary_lines": ["Peer One: better on ..., worse on ..."],
  "scorecard_headline": {"1": "one line"}, "indicator_summary": {"1.1": "one line [E01]"},
  "peer_row_summary": {"1": "how the company compares with each peer on this dimension"},
  "change_notes": {"5.2": "why the score moved since the prior quarter"}, "io_change_notes": {"1.1": "outside-in evidence, then what the documents added"},
  "actions": [{"id": "2026-Q4-A1", "heading": "Add a customer-harm watch list to board packs", "description": "...", "measures": ["..."], "target_by": "2027-Q1"}],
  "prior_actions_status": [{"id": "2026-Q3-A1", "heading": "...", "status": "completed | cancelled | on_track | behind | not_started | no_public_evidence", "evidence_note": "...[IO01]", "metrics_note": "..."}],
  "back_on_track": [{"id": "2026-Q3-A2", "heading": "...", "what_happened": "...", "impact": "...", "root_cause": "...", "prevention": "...", "measures": ["..."]}],
  "additional_information_needed": ["only if a specific document would change a grade or action"],
  "self_ratings": {"1": 3},
  "coverage": {"documents_unavailable": [], "consistency_result": "", "notes": ""}
}
```

## Field rules the scripts enforce

| Field | Rule |
|---|---|
| `run.stage` | `outside_in` scores `board` cells; `inside_out` adds `board_io` for the company only and leaves `board` untouched. |
| `run.period` | `YYYY-Qn`; history may not contain the current period. |
| `run.mode`, `run.rule_version` | Known mode; rule version must equal the framework's (1.2). |
| `subjects` | One `company`; two to five `peer`, all 22 indicators each. |
| `score` | Integer 1-5 or `null` with `na_cause` and a rationale listing what was searched. |
| `evidence` per score | 1 or 5: two items from two documents, or one `strong_direct`, `board_act` or `inside_out` item. 2-4: at least one. Scoped pairs: an item is primary for one indicator only. |
| `board_io` | Must cite an `IO` or `SA` item or set `carried_forward: true` with the outside-in score; self-assessment-only cells cannot be High confidence. Outside-in cells may not cite `IO` or `SA` items. |
| `confidence` | High / Medium / Low; silence or searched-record-only cells are Low. |
| `actions` | At most five, each with heading and description; `target_by` recommended so status can be tracked. |
| `prior_actions_status[].status` | One of the six statuses. |
| `evidence[].simulated` | True for anything generated by the simulators; shown as SIMULATED everywhere. |

`computed` (written by grade.py): per lens, `dimensions` (assessed, of, average, grade, label, reported), `overall` (grade, numeric_average, dimensions_reported, provisional, label), `coverage` (assessed / 22 with the not-assessable split).

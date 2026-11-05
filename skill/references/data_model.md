# Run data model (run.json), rules v1.3, board-only, two stages

One JSON file per stage per quarter. `grade.py` validates it and writes `computed`; the renderers read it. Always deliver the file with the report: the next quarter's trend and action tracking depend on it.

```json
{
  "run": {"run_date": "2026-10-28", "period": "2026-Q4", "stage": "outside_in | inside_out",
          "mode": "director_request | internal_dry_run | methodology_pilot", "rule_version": "1.3", "as_of": "2026-10-28", "sector": "energy",
          "extra_registers": [], "extra_trade_press": [],
          "document_window": {"behaviour_from": "2024-10", "trend_from": "FY2021"}, "consistency_run": 1},
  "headline": "One line for the executive summary.",
  "subjects": [
    {"name": "<Company name>", "ticker": "<TICKER>", "role": "company",
     "indicators": {"1.1": {
        "board":    {"score": 3, "confidence": "Medium", "evidence": ["E01"], "rationale": "What the board did, with codes inline [E01]."},
        "board_io": {"score": 5, "confidence": "High", "evidence": ["IO03", "SA01"], "rationale": "Outside-in showed X; the board documents add Y [IO03] [SA01].", "carried_forward": false}},
       "1.2": {"board": {"score": null, "confidence": null, "evidence": [], "na_cause": "disclosure-limited", "rationale": "Not assessable. Searched: ..."}}},
     "assessment_text": {"1": "First sentence is the headline. Then about 80 words."}, "limitations": {"1": "One line."}},
    {"name": "Peer One", "role": "peer", "indicators": {"...": "board cells only, scored fully"}, "summary": "Two sentences for the peer page."}
  ],
  "evidence": {
    "E01":  {"document": "...", "doc_type": "10-K", "date": "2026-02-20", "url": "https://...", "excerpt": "<15 words", "evidence_class": "strong_direct", "source_origin": "public", "recent": false,
            "source_type": "company", "outlet": null, "event_date": "2026-02-20"},
    "E09":  {"document": "FDA recall database search", "evidence_class": "searched_record", "search_log": "register; terms; date; result", "source_origin": "public"},
    "IO03": {"document": "Board pack extracts (board document)", "evidence_class": "inside_out", "source_origin": "inside_out", "date": "2026-11-01"},
    "SA01": {"document": "Director self-assessment, Q1 (Dimension 1)", "evidence_class": "self_assessment", "source_origin": "self_assessment", "question": "...", "excerpt": "answer"}
  },
  "history": ["written by load_history.py: period, stage, dimension grades per lens, overall, indicator scores, peers, actions"],
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

## v1.3 additions (Rules 16-19)

Each subject also carries two blocks created by `scripts/init_run.py`; every entry starts as `todo` and grading is blocked until it is final.

```json
"retrieval_log": {
  "items": {"R1": {"status": "found", "documents": ["10-K FY2025", "10-K FY2024"], "years": [2021, 2022, 2023, 2024, 2025], "queries": []},
            "R4": {"status": "found", "documents": ["EDGAR 8-K list"], "from": "2023-10-28", "to": "2026-10-28", "filings_reviewed": 41, "feed": "SEC EDGAR 8-K"},
            "R5": {"status": "not_applicable", "reason": "No pending transaction requiring a merger proxy"}},
  "registers": {"REG-E1": {"status": "searched", "query": "Chevron consumer class action", "date": "2026-10-28", "hits": ["E05"]},
                "REG-E6": {"status": "not_applicable", "reason": "No retail fuel sales outside the US"}},
  "event_sweep": {"ES01": {"query": "Chevron chair", "from": "2024-10-28", "to": "2026-10-28", "results_reviewed": 10, "hits": []}}
},
"facts": {"1.4": {"discretion_or_reduction_applied": {"status": "found", "value": "CEO individual component cut 9% for fatalities", "evidence": ["E04"]},
                  "cascade_below_csuite": {"status": "not_disclosed", "where_searched": "2026 proxy CD&A; 2025 10-K"}}}
```

| Field | Rule |
|---|---|
| `run.as_of` | Required. Every sweep must reach it (7-day tolerance); windows and `recent` are measured from it. |
| `run.sector` | Required: a key of `sector_packs` in `assets/retrieval_spec.json`. `general` needs `run.extra_registers` (each `{id, name, query}`), logged like pack registers. |
| `retrieval_log.items` | All of R1-R8 per subject. `found` needs `documents`; `searched_none` / `unavailable` need `queries`; `not_applicable` only for R5 with `reason`. R4 needs `from`, `to`, `filings_reviewed`. |
| `retrieval_log.registers` | Every sector-pack register: `searched` (query, date, hits) or `not_applicable` (reason). |
| `retrieval_log.event_sweep` | All fourteen ES queries: filled query text, `from` at least 24 months before `as_of`, `to` at `as_of`, `results_reviewed`, `hits` (evidence ids). |
| `facts[iid][field]` | Every field in the fact sheet: `found` (value, evidence) or `not_disclosed` (where_searched). |
| `evidence[].source_type` | One of company, regulator_exchange, court, approved_news, trade_press, rating_agency, proxy_advisor, sell_side, data_platform, other; `outlet` for news and trade press; `underlying_source_type` for data platforms. |
| `evidence[].event_date` | Date of the event when it predates the document. Required on every item cited by 2.1, 3.2, 4.1, 4.2, 4.3, 5.4, 6.3. |
| `run.reconciliation` | Written by `apply_recon.py`: `base`, `other`, `date`, `decided_by`, `decisions` (item, subject, indicator, decision, applied, basis, recommendation, reason, score_a, score_b, evidence_copied) and `stale_text` (fields to rewrite; must be emptied before grading). |
| `indicators[iid].board.pending_recon` | Set on cells the user sent for re-research; grading blocks until removed and the cell is scored or marked not assessable. |
| `recon_plan.json` | Written by `compare_runs.py --plan`: `items` with id, subject, indicator, scores, rationales, issues, facts_only_a/b, basis, recommendation, reason; the analyst adds `analyst_recommendation` and `analyst_reason` to judgement items; the user's answer goes in `decision`, and the plan's `decided_by` names who decided. |
| `run.consistency` | Optional. `mode`: `single` or `double`; `compare_runs.py --record` adds `verdict`, `flags`, `compared_with`. |

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

`computed` (written by grade.py): per lens, `dimensions` (assessed, of, average, grade, label, reported), `overall` (grade, numeric_average, dimensions_reported, provisional, label), `coverage` (assessed / 22 with the not-assessable split).

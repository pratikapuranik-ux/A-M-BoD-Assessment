Today is $today. Assessment period: $period. Stage: inside-out update for $company (rules 17-21 apply; the outside-in overrides for 1.2 and 4.1 do not).

The board documents supplied by the director are attached above, each labelled with its evidence code. The self-assessment answers, the outside-in result and the prior actions are below. Re-score the company only; peers are never re-scored and the outside-in board cells stay unchanged.

For each of the 22 indicators submit a cell for the post inside-out score:
- If the documents or answers bear on the indicator: score it against the level-neutral anchors with the rationale written as "Outside-in showed X; the board documents add Y", citing at least one IO or SA code (outside-in E codes may be cited alongside). carried_forward false. The score may move either way.
- If they add nothing: carried_forward true, with a one-line rationale saying so; the outside-in score is kept as it is (repeat it in score, or 0 if it was not assessable).
- Self-assessment alone (SA codes without any IO or E code) can lower a score but cannot lift it above 3, and is never High confidence. One IO item is strong direct evidence and can support a 1 or 5.
- Score 0 means still not assessable: give na_cause and say what is missing.

Also submit:
- documents: for each IO code, the document's date (YYYY-MM-DD, YYYY-MM or YYYY as stated in it, else $today) and a verbatim excerpt under 15 words that best shows what it adds.
- headline, overall_summary (one sentence on the post inside-out grade against the outside-in grade), what_moved (what the documents changed across dimensions).
- better / worse: where the inside view is better and worse than the public record, one line each with codes.
- headline_findings: exactly three, with codes.
- io_change_notes: for each indicator whose score moved, the outside-in evidence and then what the documents added.
- actions: up to five updated actions with measures and target_by (YYYY-Qn after $period), tied to findings.
- prior_actions_status: one entry per prior action listed below (same id), status from the documents (completed, cancelled, on_track, behind, not_started, no_public_evidence), evidence_note with codes, metrics_note. Empty if there are no prior actions.
- back_on_track: one entry per prior action that is behind or not_started (what happened, impact, root cause, mechanism to prevent, measures to track).
- additional_information_needed: only where a specific document would still change a grade or action.

Input data:
$digest

Call submit_inside_out once with every field.

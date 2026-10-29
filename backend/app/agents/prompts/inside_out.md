Today is $today. Assessment period: $period. Stage: inside-out update for $company (rules 17-21 apply; the outside-in overrides for 1.2 and 4.1 do not).

The board documents supplied by the director are attached above, each labelled with its evidence code. The self-assessment answers, the outside-in result and the prior actions are below. Re-score the company only; peers are never re-scored and the outside-in board cells stay unchanged.

For each of the 22 indicators submit a cell for the post inside-out score:
- If the documents or answers bear on the indicator: score it against the level-neutral anchors with the rationale written as "Outside-in showed X; the board documents add Y", citing at least one IO or SA code (outside-in E codes may be cited alongside). carried_forward false. The score may move either way.
- If they add nothing: carried_forward true, with a one-line rationale saying so; the outside-in score is kept as it is (repeat it in score, or 0 if it was not assessable).
- Self-assessment alone (SA codes without any IO or E code) can lower a score but cannot lift it above 3, and is never High confidence. One IO item is strong direct evidence and can support a 1 or 5.
- Score 0 means still not assessable: give na_cause and say what is missing.

Also submit:
- documents: for each IO code, the document's date (YYYY-MM-DD, YYYY-MM or YYYY as stated in it, else $today) and a verbatim excerpt under 15 words that best shows what it adds.
- self_assessment_themes: the director self-assessment synthesised for the appendix, which prints these entries and nothing else from the answers. One entry per theme: dimension ("1" to "6"), a short theme label, and a summary of two or three sentences covering what several directors raised, where views diverged, and how that reads against the public record. Three to eight entries across the answered dimensions. Themes only: never quote an answer, reproduce its distinctive phrasing or a recounted incident, and never write "one director said" or "Response 2". Attribute to the group ("most answers", "two of the responses", "views divided on"). Empty if there are no answers.
- headline, overall_summary (one sentence on the post inside-out grade against the outside-in grade), what_moved (what the documents changed across dimensions).
- better / worse: where the inside view is better and worse than the public record, one line each with codes.
- headline_findings: exactly three, with codes.
- io_change_notes: for each indicator whose score moved, the outside-in evidence and then what the documents added.
- actions: up to five updated actions with measures and target_by (YYYY-Qn after $period), tied to findings.
- prior_actions_status: one entry per prior action listed below (same id), status from the documents (completed, cancelled, on_track, behind, not_started, no_public_evidence), evidence_note with codes, metrics_note. Empty if there are no prior actions.
- back_on_track: one entry per prior action that is behind or not_started (what happened, impact, root cause, mechanism to prevent, measures to track).
- additional_information_needed: only where a specific document would still change a grade or action.

Writing and anonymity
- Register as set out under Writing in the system prompt: declarative and literal, figures and dates, no metaphor, idiom or personification, no journalistic opener. Name the dimension ("Building over Protecting"), never "Dimension 5".
- The self-assessment is anonymous, and the answers below are shuffled question by question, so "Response 2" is a different director from one question to the next. Wherever self-assessment material is used - rationales, better / worse, findings, io_change_notes, actions and the themes - write it as the view of the group, not of a person, and leave out the phrasing, the recounted incident, the date or the role detail that would let a reader work out who wrote it. Cite the SA code for traceability: it stands for the question, not for the respondent.

Input data:
$digest

Call submit_inside_out once with every field.

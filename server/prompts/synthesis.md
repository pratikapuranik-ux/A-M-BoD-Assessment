Today is $today. Assessment period: $period. Run mode: $mode.

The outside-in research is complete and grade.py has computed the grades below. Write the synthesis fields for the report and dashboard, for $company's board, using only the scores, rationales and evidence codes given here. Cite company evidence codes inline as [E07]; peer codes may be cited where a comparison needs them.

$prior_note

Fields for submit_synthesis:
- headline: one line for the executive summary that captures what the board does well and what holds it back.
- overall_summary: one sentence with the overall grade and its classification, what lifts it and what holds it back.
- what_moved: a short paragraph on what drove the grade across dimensions, naming the dimension grades.
- headline_findings: exactly three one-line findings, each with codes.
- key_metrics: three to six metrics with a material bearing on the assessment (metric, why it matters, current value with period).
- peer_position: one sentence on where the company stands against the peers, using overall grades.
- peer_summary_lines: one line per peer, in peer order: "<Peer>: better on ..., worse on ...; <ahead / behind / at par> overall (<grade>)".
- scorecard_headline: one line of evidence per dimension "1" to "6" with codes, plus key "7" for the overall row (how the overall grade is formed).
- peer_row_summary: per dimension "1" to "6", how the company compares with each peer, with their grades.
- peer_summaries: per peer ticker, two sentences for the peer page: overall grade, strongest and weakest dimensions and why.
- actions: up to five, specific and directly tied to a finding (for example "Add a customer-harm watch list to board packs", "Schedule directors' frontline sessions without management"), each with a description naming who acts, measures to track, and target_by as a quarter (YYYY-Qn) after $period.
- additional_information_needed: only where a specific document would change a grade or an action; otherwise empty.

Run data:
$digest

Call submit_synthesis once with every field.

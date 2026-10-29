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
- actions: up to five, specific and directly tied to a finding (for example "Add a customer-harm watch list to board packs", "Schedule directors' frontline sessions without management"), each with a description naming who acts, `improves` (one sentence: which dimension and indicator numbers it should raise and how, e.g. "Raises Customer Obsession (1.4, 1.1) by making customer outcomes a paid-for priority."), measures to track, and target_by as a quarter (YYYY-Qn) after $period.
- additional_information_needed: only where a specific document would change a grade or an action; otherwise empty.

Length and style (the report must read like the reference report, so keep to these limits):
- Register as set out under Writing in the system prompt: declarative and literal, no metaphor, idiom or personification, no journalistic opener. A headline or finding is a fact with its figures, never a turn of phrase. Name the dimension ("Customer Obsession"), never "Dimension 1", in what_moved, scorecard_headline, peer_row_summary, peer_summaries and every `improves` line.
- headline at most 25 words; overall_summary one sentence of about 35 words; what_moved about 90 words in total; each headline_finding one line.
- References throughout: cite the evidence code inline ([E07], or a peer's code) wherever a figure or finding rests on a source: in overall_summary, what_moved, every headline_finding, the "current" value of each key_metric, peer_position, each peer line, peer_row_summary, peer_summaries, scorecard_headline and in the finding behind each action. Keep it to one or two codes per sentence, only codes shown in the run data. The headline itself carries no code.
- Name grades as letters ("Chevron (C)"); do not quote numeric averages such as 2.75.
- key_metrics: exactly five, each "why" under 12 words and each "current" value under 8 words.
- peer_summary_lines: one line of about 25 words per peer. peer_row_summary: at most two sentences (about 35 words) per dimension.
- scorecard_headline: one line of at most 22 words per dimension. actions: heading plus a description of about 45 words naming who acts, and two measures.

Run data:
$digest

Call submit_synthesis once with every field.

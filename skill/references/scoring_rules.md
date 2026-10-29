# Scoring Rules v1.2 (outside-in)

Apply every rule on every run. `scripts/grade.py` enforces rules 2, 3, 4, 5, 6, 7, 10 and 16 mechanically from the run JSON and checks run mode and rule version; the others are applied while researching and scoring.

## Rule 1: One lens: the board

Every indicator is scored once, for the board, against the anchors. Evidence of what management did (capital deployed, timing on shocks, cash discipline, pilots scaled or stopped) is attributed to the board's oversight and scored as board behaviour; there is no separate management score.

## Rule 2: Indicator scores

1, 3 or 5 against the anchors. 2 and 4 only when evidence meets parts of both adjacent anchors, with a rationale naming those parts. No decimals.

## Rule 3: Evidence minimums

A score of 3 requires one evidence item. A score of 1 or 5 requires either two independent evidence items from two different documents, or one item of strong direct evidence: a regulator or court record, a formal board act (Rule 14), or an audited figure in a 10-K / annual report; the rationale must state which strong-evidence type applies. Each item cites the document, its date and the specific passage or data point.

## Rule 4: Confidence per score

Assigned on the evidence, not the document tier. High: two or more direct sources agree, or one strong direct source under Rule 3. Medium: one direct source, or two indirect ones. Low: a single indirect source, an inference, or a silence-based score under Rule 5.

## Rule 5: Not assessable, and when silence counts

Below the evidence minimum, the indicator is marked not assessable with its cause (rule-limited, disclosure-limited, retrieval-limited) and excluded from the average. It is never defaulted to 3. Silence in a filing may be scored where disclosure is legally or regulatorily expected: 1.4 (incentive metrics), 5.2 (tenure, age, appointments) and 5.3 (evaluation process) up to 1-5 per anchor; 2.3 (governance guidelines on access to management and advisors), 2.4 (committee charters across five proxies) and 4.3 (director resignations over disagreement, 8-K Item 5.02, over the lookback) capped at 3, Low confidence. Searched-record evidence: a documented search of a public register that returns nothing is an evidence item (record the register, the search terms and the date) and may support a score of up to 3 on 1.3 at Low confidence. The cap at 3 is what separates this from defaulting to 3.

## Rule 6: Dimension grades

Average of assessed indicator scores, mapped to A-F using the grade scale. A letter is reported only if at least half the dimension's indicators are assessed.

## Rule 7: Overall grades

Map reported dimension letters A=5, B=4, C=3, D=2, F=1; average; round midpoints down (2.50 is a D); map back. Four or more dimensions reported: overall grade shown. Exactly three: shown as Provisional and excluded from cross-company comparisons. Fewer than three: no overall grade.

## Rule 8: Time windows

Behaviour indicators (3.2, 4.1, 4.2, 5.4, 6.3): 24-month lookback. 2.1, 4.3: 36-month lookback, because assumption revisions and dissent signals are infrequent. Trend indicators (3.4, 5.1, 5.2, 6.1, 6.2): five years of filings. All others: the most recent filing cycle plus events in the 24-month window.

## Rule 9: Peer-relative scoring

3.2, 5.1, 6.1, 6.2 are scored against a named set of two to four listed peers, run with the same rubric in the same session. 'In line with peers' is the 3 anchor. Where a peer cannot be scored on a peer-relative indicator, a reputable sector median (rating-agency peer tables, CapIQ comparables) may substitute for that peer; cite the source.

## Rule 10: No double counting

Within each scoped pair (3.4/5.1, 5.4/6.3, 1.4/6.1, 2.3/3.3), an evidence item is primary for one indicator only. Different passages of the same document are separate evidence items and may serve different indicators in the pair.

## Rule 11: News as evidence

Direct evidence, no corroboration required, from the approved list: Bloomberg, Reuters, The Wall Street Journal, Financial Times, Forbes, AP, The New York Times, Barron's, The Economist, CNBC, Nikkei, Handelsblatt, Les Echos, The Economic Times, Mint (The Economic Times and Mint for Indian companies). Recognised sector trade press (e.g. Food Business News, FoodNavigator, Supermarket News) is direct evidence for event facts (what was announced, when, at what value) and context for interpretation or opinion. Content through S&P Capital IQ, AlphaSense or PitchBook is treated according to its underlying source. Events in the last 90 days are marked RECENT.

## Rule 12: Consistency test

Each company is run at least twice on the same rule version. Tolerance: indicator scores within one point and dimension letters unchanged.

## Rule 13: Output order

Per dimension: the board grade, two or three evidence points with citations, confidence, and where public evidence limits the grade. Overall grades follow. Actions come last.

## Rule 14: Formal board acts as Board-lens evidence

Acts the board formally approves are Board evidence for the indicator they bear on and count as strong direct evidence under Rule 3: Dividend declarations, increases, cuts (5.1, 5.4, 6.3); Buyback authorisations (5.1, 6.2); M&A and divestiture approvals (incl. 'unanimously approved') (3.4, 4.2); Guidance-framework or long-term algorithm changes (2.1); CEO appointments, separations and succession announcements (5.2, 4.2); Committee creation, renaming or dissolution (2.4).

## Rule 15: Minimum retrieval before 'not assessable'

An indicator may be marked not assessable only after the standard retrieval set for that indicator has been searched, and the rationale lists what was searched. The minimum set per subject: (1) Latest 10-K / annual report, plus five years of cash-flow statements. (2) Five years of proxy statements, read in full, including the pay discussion and governance guidelines. (3) Four to eight earnings call transcripts with analyst Q&A (CapIQ or AlphaSense preferred), including any call held on the day of a major transaction announcement. (4) A 24-month sweep of 8-Ks / exchange announcements, and a 36-month sweep for Item 5.02. (5) A merger proxy or registration statement for any pending transaction. (6) Sector regulator registers relevant to indicator 1.3 (e.g. FDA recalls for food, CFPB complaints for consumer finance). (7) Investor day materials and sector conference presentations (e.g. CAGNY for consumer staples). (8) Where accessible: ISS / Glass Lewis reports and Moody's / S&P / Fitch reports.

## Rule 16: Coverage reporting

Each run reports the coverage ratio (assessed / 22) per subject and splits the not-assessable cells into three causes: rule-limited, disclosure-limited and retrieval-limited, so a gap can be attributed to the company or to the run.

## Rule 17: Inside-out stage is a re-score, not a new framework

The inside-out stage keeps every outside-in score unchanged in the `board` cell and adds a `board_io` cell (post inside-out) for the company only. The same 22 indicators and the level-neutral anchors apply (the outside-in overrides for 1.2 and 4.1 do not). Peers are never re-scored; peer comparisons use the company's outside-in grade.

## Rule 18: Inside-out evidence weight

Board documents (minutes, agendas, packs, governance framework, strategy and capital papers, treasury reports, evaluation and succession documents, CEO reports, customer and risk reports, executive-session notes) are `inside_out` evidence and count as strong direct evidence: one item can support a 1 or 5. A post-inside-out score must cite at least one `inside_out` or `self_assessment` item; a cell may instead be carried forward unchanged with `carried_forward: true` when the documents add nothing on that indicator. A post-inside-out score may move in either direction.

## Rule 19: Self-assessment evidence

Questionnaire answers are `self_assessment` evidence, self-reported. Alone they support at most Medium confidence and cannot lift a score above 3 unless corroborated by an inside-out or public item; they can lower a score on their own. Each cited answer is quoted with its question in the sources appendix. Self-ratings (1 / 3 / 5 per dimension) are shown as context in the sources appendix and are not scored.

## Rule 20: Coverage threshold and gaps in the inside-out stage

A dimension's post-inside-out grade is reported only if at least two-thirds of its indicators are assessed. A cell still not assessable after the documents are read is recorded with its cause, and the indicator is listed in the additional-information section only if a specific document would settle it.

## Rule 21: Trend, actions and status

Prior quarters come only from prior run files produced by this skill (an inside-out run file supersedes an outside-in file for the same period); at most four quarters are shown. Indicator-level change is shown only where a score moved. Status of prior actions is recorded from inside-out evidence with one of: completed, cancelled, on track, behind, not started, no public evidence; in an outside-in run the status is not forced and is asked for in the inside-out stage. Actions behind or not started get a back-on-track entry (what happened, impact, root cause, mechanism to prevent, measures to track). New actions: at most five, each with measures and a target quarter.

## Grade scale (dimension level)

| Average indicator score | Grade | Classification |
|---|---|---|
| 4.25 - 5.00 | A | Day 1 |
| 3.50 - 4.24 | B | Day 1 early drift |
| 2.75 - 3.49 | C | Day 2 creeping in |
| 2.00 - 2.74 | D | Day 2 established |
| below 2.00 | F | Day 2 entrenched |

## Overall grade

1. Map each reported dimension letter: A=5, B=4, C=3, D=2, F=1.
2. Average across reported dimensions.
3. Round to the nearest whole number; midpoints round down (3.50 -> 3, 2.50 -> 2).
4. Map back: 5=A, 4=B, 3=C, 2=D, 1=F.
5. Four or more dimensions: full overall grade. Exactly three: provisional. Fewer: none.

| Dimension grades | Average | Overall |
|---|---|---|
| B B B B C C | 3.67 | B |
| B B B C C C | 3.50 | B |
| B B B B C D | 3.50 | B |
| B B C C C D | 3.17 | C |
| A B B C C F | 3.33 | C |
| B C C (3 reported) | 3.33 | C, provisional |

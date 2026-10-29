# Inside-out documents

The thirteen document types, in priority order for the Stage 2 offer (the first seven move the assessment most). Each line gives the indicators it settles. Ask for the whole Tier 1 set for the same 12-month window rather than minutes alone: US minutes are deliberately thin and the agenda and pack carry much of the signal. For the prototype, `scripts/simulate_inside_out.py` generates all thirteen plus an action tracker and a filled questionnaire.

| # | Document | Indicators settled |
|---|---|---|
| 1 | Board and committee minutes (12 months) | 1.1 1.3 2.1 2.3 3.2 4.1 4.2 4.3 5.4 6.3 |
| 2 | Board agendas and annual calendar | 1.1 1.2 2.3 3.1 3.3 |
| 3 | Board and committee packs (routine pre-reads) | 1.1 2.2 2.4 3.1 6.1 |
| 4 | Governance framework: delegation of authority, committee terms, capital and treasury policies, incentive scorecards | 1.4 2.4 4.1 5.1 5.3 6.1 6.2 |
| 5 | Strategy papers and plan versions | 2.1 3.1 |
| 6 | Capital and investment papers with post-investment reviews | 3.4 4.2 5.1 |
| 7 | Treasury and liquidity reports (stress tests, covenant headroom) | 6.1 6.2 6.3 |
| 8 | Board evaluation report and action log | 5.3 |
| 9 | Skills matrix and board/CEO succession plans | 3.3 5.2 |
| 10 | CEO reports to the board | 1.1 3.1 6.1 |
| 11 | Customer insight and key-account reports | 1.1 1.3 |
| 12 | Internal audit and risk reports | 1.3 2.2 6.3 |
| 13 | Chair / lead independent director notes from executive sessions | 2.3 4.3 |

## How each is read

- **Minutes**: decision cycle times, deferrals, recorded dissent and revisited views, external presenters, responses to escalations, status of prior actions. Read across 12-24 months.
- **Agendas and calendar**: time allocation by topic, standing items, site visits and unmediated contact, outside speakers.
- **Packs**: curated vs unfiltered evidence, backward vs forward looking, earnings vs cash, pack evolution.
- **Governance framework**: decision rights by reversibility, committee remits and history, incentive metrics and weights, leverage and liquidity limits, capital allocation priorities.
- **Strategy papers and plan versions**: when and why core assumptions changed; positions on named shifts.
- **Capital and investment papers with post-investment reviews**: alternatives considered, pre-mortems, outcomes vs case; absence of reviews is itself a finding.
- **Treasury reports**: headroom against floor, stress tests, covenant compliance, early-warning triggers.
- **Evaluation report and action log**: facilitation, findings, actions closed.
- **Skills matrix and succession plans**: gaps and appointment rationale, pipeline depth, limits and waivers.
- **CEO reports**: share of attention to customers, shifts and cash over four to eight meetings.
- **Customer insight and key-account reports**: whether they exist and reach the board at all; watch lists.
- **Internal audit and risk reports**: early-warning dashboards, KPI definition changes flagged.
- **Chair notes from executive sessions**: candid challenge, dissent, board-CEO dynamics; rarely exist.

## Self-assessment questionnaire

Twelve dimension-level questions (two per dimension), with an optional 1 / 3 / 5 self-rating per dimension, built by `scripts/build_questionnaire.py` as a Word file with shaded answer boxes. Answers are themes to be drawn, not indicator scores. `scripts/parse_questionnaire.py` turns a returned file into `SA01`-`SA12` evidence items (self-reported; Rule 19).

1. (Dimension 1, Customer Obsession) In the last 12 months, when did something a customer said or did change a decision in the boardroom? How did it reach you: through management's summary, or directly (complaints, churn data, a conversation without management present)?
2. (Dimension 1, Customer Obsession) Which customer or quality measure sits in executive pay, at what weight, and has it ever reduced a payout?
3. (Dimension 2, Resisting Proxies) When did the board last change a core strategic assumption, and what prompted it: internal evidence the board asked for, or outside pressure (a miss, an activist, an analyst)?
4. (Dimension 2, Resisting Proxies) Which number in the board pack do you trust least, and what has the board retired or redefined in the last two years (a metric, a report, a committee) because it no longer earned its place?
5. (Dimension 3, Embracing External Trends) Name the two or three structural shifts that matter most to the company. For each, does the board hold an explicit position with targets, and who outside the company has addressed the board on it in the past year?
6. (Dimension 3, Embracing External Trends) On the last two or three sector shocks, did the company move ahead of peers, with them, or after them, and did the board or management initiate the move?
7. (Dimension 4, High-Velocity Decision-Making) Does the board distinguish reversible from irreversible decisions in practice? Give one example of each from the last year, how many meetings each took, and whether anything was reversed, deferred or declined.
8. (Dimension 4, High-Velocity Decision-Making) When did a director last change their mind because of an argument made in the room, how are minority views recorded, and does a contested decision stay settled afterwards?
9. (Dimension 5, Building over Protecting) When earnings last came under pressure, which lever did the board reach for first (cost, buybacks, guidance, reinvestment), and how was the alternative debated?
10. (Dimension 5, Building over Protecting) What did the last board evaluation and the last board appointment change, and what would owners say about the board that the board would not say about itself?
11. (Dimension 6, Liquidity and Capital Management) Does the board spend more time on earnings or on cash? What liquidity trigger would make the board act, and has it ever acted while the numbers still looked fine?
12. (Dimension 6, Liquidity and Capital Management) What is the stated leverage and liquidity policy, how often is it stress-tested in front of the board, and who on the board owns working capital?

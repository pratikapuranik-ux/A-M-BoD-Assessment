Today is $today. Assessment period: $period. Stage: outside-in, from public information only.

Subject: $name ($ticker), role in this assessment: $role.
Full peer set (company first): $peerset.
Evidence code prefix: $prefix. Number your evidence items ${prefix}01, ${prefix}02, ... and use no other codes.
Time windows: behaviour indicators from $behaviour_from (24 months; 36 months for 2.1 and 4.3), trend indicators over five fiscal years from $trend_from.

Task: research and score this subject's board on all 22 indicators, exactly as the methodology requires. Peers are researched as fully as the company.

1. Retrieve the Rule 15 minimum set for this subject: latest 10-K or annual report plus five years of cash-flow figures; the proxy statements (latest in full, earlier years for renewal, committee and evaluation changes) with the pay discussion and governance guidelines; four to eight recent earnings call transcripts or their reputable summaries with analyst Q&A; a 24-month sweep of 8-Ks or exchange announcements and a 36-month sweep for Item 5.02; any merger proxy for a pending deal; the sector regulator registers relevant to 1.3; investor day or sector conference materials; ISS, Glass Lewis and Moody's, S&P or Fitch commentary where reachable. Use web_search to locate documents and web_fetch to read primary pages (SEC EDGAR or the local regulator, the investor-relations site, approved news). The Rule 15 set must be searched before any indicator is marked not assessable. The limits of $search_budget searches and $fetch_budget fetches are ceilings, not targets: use as many as the set needs, and prefer one well-chosen primary document over several summaries.
1b. Read the primary documents themselves, not only summaries: the latest proxy statement's pay discussion, governance guidelines, director and committee sections and board evaluation; the annual report or 10-K cash-flow statements. If a PDF or page cannot be fetched, try another route before giving up: the investor-relations HTML version, the SEC EDGAR filing index, a regulator or exchange page, or a reputable mirror of the same filing. Record a document in documents_unavailable only after those routes have failed.
1c. Look for adverse and Day 2 evidence on purpose, so that no score rests on favourable material alone: waivers of age or term limits, director or executive departures and their stated reasons, litigation and regulator actions, impairments and reversed decisions, protective governance provisions, votes against management.
2. Score each indicator once, in the board cell, against its anchors. Peer-relative indicators (3.2, 5.1, 6.1, 6.2) are scored against the peer set above; use figures you retrieved and reputable sector comparables where needed (Rule 9).
3. Record comparables for the peer-relative calibration: capex to depreciation (latest year and five-year view), free cash flow to net income, leverage (net debt ratio or net debt to EBITDA), credit rating, cash returned to shareholders, and timing on the last two or three sector shocks, each with its evidence code.
4. Per dimension 1-6 write assessment_text (first sentence is the headline, then about 60 to 80 words in total, codes inline) and limitations (one line on where public information limits the grade).
5. Per indicator write summary: one line of at most 20 words with codes, for the evidence table. Each rationale is two or three sentences (about 50 words), naming the anchor parts met; do not narrate the research.

Submission encoding for submit_subject_assessment:
- score 1-5 with confidence High, Medium or Low and na_cause "none"; or score 0 for not assessable, with confidence "None", na_cause rule-limited, disclosure-limited or retrieval-limited, and a rationale listing what was searched (Rule 15). Never use 3 for "don't know".
- evidence lists the codes the score rests on. In each scoped pair (3.4/5.1, 5.4/6.3, 1.4/6.1, 2.3/3.3) an item is primary for one indicator only.
- search_log is empty except for searched_record items; url is empty only for searched_record items.
- documents_unavailable lists Rule 15 documents you could not retrieve.

When the research is done, call submit_subject_assessment once with the complete assessment.

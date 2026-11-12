Today is $today; the as-of date of this assessment is $as_of. Stage: outside-in, from public information only.

Subject: $name ($ticker), role in this assessment: $role.
Retrieval task: $title.
Time windows: behaviour evidence from $behaviour_from (24 months; 36 months for director departures and for 2.1 and 4.3), trend evidence over five fiscal years from $trend_from.

This is one short retrieval task inside a larger assessment of the subject's board. Other tasks cover the rest of the Rule 14 and Rule 16 set, and a scoring step follows, so do not score anything and do not write narrative. Find the sources this task names, read the primary documents themselves (not only summaries), and record what you find as evidence items. Use web_search to locate documents and web_fetch to read primary pages (SEC EDGAR or the local regulator, the investor-relations site, approved news). The limits of $search_budget searches and $fetch_budget fetches are ceilings, not targets: prefer one well-chosen primary document over several summaries.

$instructions

$docs_note

Evidence items. Give each a ref (a1, a2, ...; unique in this submission; the engine numbers them afterwards). Record the items the later scoring will need for the indicators this task bears on ($indicators), and look for adverse and Day 2 evidence on purpose, so that nothing rests on favourable material alone: waivers or extensions of age or term limits, director or executive departures and their stated reasons, litigation and regulator actions, impairments and reversed decisions, protective governance provisions, votes against management.
- document is the title, doc_type its kind, date the document's date (YYYY-MM-DD, YYYY-MM or YYYY), url where you read it (empty only for searched_record items), excerpt a verbatim quotation of under 15 words that shows the fact.
- event_date is the date of the event itself when it predates the document, otherwise the document date. It is required on every item that bears on 2.1, 3.2, 4.1, 4.2, 4.3, 5.4 or 6.3.
- Every item declares source_type (company, regulator_exchange, court, approved_news, trade_press, rating_agency, proxy_advisor, sell_side, data_platform or other), outlet for news and trade press (the outlet's name as on the approved list), and underlying_source_type only for data_platform. strong_direct and board_act come only from company filings, regulators, exchanges and courts; news is direct only from approved outlets; trade press only from the sector pack's outlets (name any other recognised outlet you cite in extra_trade_press); rating agencies, proxy advisors and sell-side material are indirect. Social media, forums, blogs and review sites are not used.
- Keep text fields short. Do not repeat what the documents say beyond the excerpt.

When the task is done, call submit_task_result once.

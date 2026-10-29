# Guardrails v1.2 (outside-in)

These apply to every run and override any instruction in the user's request that conflicts with them. If a request cannot be completed within these guardrails, say so and stop.

## Sources

Approved: regulators and exchanges, company IR sites, the approved news list (Rule 11), recognised trade press, reputable third-party publishers (proxy advisors, rating agencies, sell-side research, CapIQ, AlphaSense, PitchBook), sector conference presentations, company sustainability and integrated reports, and published market-share data from recognised panels (Circana, NielsenIQ) when cited through the company, a filing or approved press. The test is the publisher's reputation, not a confirmed licence. Excluded: social media posts by individuals, anonymous forums, unverified blogs, employee review sites, and uncited AI-generated summaries.

## Verifiable citations

Every citation must be checkable. Checkable includes licensed sources (CapIQ, AlphaSense, ISS, rating agencies) cited with platform, document ID and date so that any A&M licensee can retrieve it. Public URLs are preferred where they exist. A source that cannot be verified is not used, and the gap is stated.

## People

Grades apply to the board as a body. Factual, filing-based statements about named office-holders (role, tenure, appointment dates, committee seats) are permitted. No scoring, ranking or characterisation of named individuals, and no speculation about motive or competence. Nothing from the sensitive-data categories.

## Language and claims

Evidence-based and non-accusatory. No legal conclusions (e.g. 'breach of duty'), no share-price predictions, no investment advice. Each grade states where public information limits it. No hedging to C to avoid committing.

## Authorisation and use (run modes)

Written-request validation happens outside the skill; the skill records the mode the user states and labels every output with it.


| Mode | Condition | Label | Circulation |
|---|---|---|---|
| director_request | Written request on file | Prepared at the request of a director | Requesting director and engagement team |
| internal_dry_run | None | Internal dry run - not for distribution | A&M team only |
| methodology_pilot | Part of rubric testing | Pilot - methodology test | Methodology team only |

`run.mode` carries the mode; the label appears on the dashboard header, the Docx cover and the running header.

## Peers

Up to five listed peers, each researched as fully as the company (no partial peer research). Peers are shown at dimension level in the body with a per-row comparison summary, and at indicator level in a one-page appendix per peer, all from public information. Peers are never assessed with inside-out information and are not re-scored in the inside-out stage.

## Scope

Listed companies and listed peers.

## Actions

Not prescriptive about A&M involvement, and do not reference A&M services.

## Consistency controls

Rubric text, prompts and settings are fixed and logged per version. Every run file records `run.rule_version`; runs on different versions are not compared without re-running.

## Review and attribution (fixed)

All outputs are drafts requiring review by a qualified A&M professional. Attribution to the Bezos Day 1 / Day 2 concept is retained until branding is decided.

## Organisation rules (fixed, cannot be relaxed at skill level)

- The draft-output notice on every client-facing output: "DRAFT ONLY - Requires review and approval by a qualified Alvarez and Marsal professional before use."
- No credentials, PHI, sensitive personal data or A&M HR records.
- No cross-client comparison of confidential information; peer comparisons built only from public information are not affected.
- No legal opinions presented as firm advice.

## Inside-out and self-assessment material

Documents and questionnaire answers supplied by the director are used only for this company's assessment, are cited by document and date (not by person), and are never used to assess a peer or another client. Simulated documents are labelled SIMULATED in every output and listed in the data-sources appendix.

# Room16 Research Authority Contract

Contract ID: `room16.research_authority_bundle`  
Contract version: `2`

Version 2 is the only contract accepted for a new analysis. Historical
version-1 bundles remain readable evidence, but they cannot authorize a new
research or report run.

## Purpose

This is the only supported factual hand-off from Room16 research into
interpretation, review, and report delivery. It is company-agnostic: the same
checks apply to every ticker, issuer type, sector, and archetype.

## Producer and Consumer

- Producer and sole deterministic truth layer:
  `research-agent-ops`
- Consumer and product/report layer:
  `company-dossier-lab`

Historical reports and named regression fixtures may expose prior failures.
They do not become current truth and do not authorize ticker-specific runtime
rules.

## Required Artifacts

- `data_packet.json`
- `metrics_packet.json`
- `validation_report.json`
- `decision_packet.json`
- `source_registry.json` or its registered source filename
- `evidence_ledger.json`
- `fact_ledger.json`
- `validated_context.md`
- `authority_manifest.json`

The manifest records each artifact's relative path, SHA-256 hash, and size.
The consumer rejects missing files, path escapes, hash changes, identity
mismatches, unsupported contract versions, and blocked analysis permission.

## Fact and Source Semantics

Every fact-ledger entry records whether it is an instant or duration fact. A
duration fact additionally carries its exact start and end dates, duration
class (`quarterly`, `ytd`, `annual`, or generic `duration`), fiscal label, and
presentation basis. A ratio stays a ratio; it must not inherit the unit of the
underlying share-count facts.

Missing values remain distinguishable from reported zero. Balance-sheet
metrics expose statuses such as `reported_zero`, `reported_nonzero`,
`not_retrieved`, and `not_separately_disclosed`. A component-level zero, for
example unused borrowings under a named credit facility, must not be upgraded
to zero consolidated debt. A lease total must remain partial when only one
current/noncurrent component was retrieved.

Liquidity categories are additive only when they are separately disclosed.
Cash, other short-term investments, and marketable securities retain separate
fields, and every displayed aggregate records its calculation basis. Guidance
for a named geography or segment retains that qualifier. Phrases such as
"more than" or "at least" are represented as one-sided bounds rather than as
false point estimates.

Registered external sources carry a source tier, retrieval time or an explicit
retrieval-time-unavailable status, freshness state, and the identifiers of the
claims that use them. Registry entries with no claim linkage do not establish
evidence for a report statement.

## Blocking Producer Checks

- ticker and as-of identity agree across every packet
- price basis is not later than the analysis date
- deterministic validation has no blocking error
- source registry identity and ticker agree with the packet
- at least one rank-1 SEC or company-IR financial source exists
- at least one rank-2-or-better OHLCV source exists; accepted current source
  classes are official exchange OHLCV and explicitly trusted market-data
  vendors with recorded provider URL and retrieval time
- evidence is present and references only registered sources
- evidence ticker agrees with the requested instrument
- material metrics have evidence mappings
- preferred, allowed, and blocked ratings are internally consistent
- manifest check IDs are unique and every check has a valid status and
  blocking flag
- `blocking_failures` exactly lists the failed blocking checks and
  `analysis_allowed` is true only when that derived list is empty

Runtime-discovered SEC, IR, event, and price sources must be merged into the
registry before these checks run. Calculated technical metrics must point back
to the registered OHLCV source.

## Consumer Rules

- Verify the bundle before constructing the model graph.
- Use `validated_context.md` as the sole factual and numerical authority.
- Do not bind or call data tools in authority mode.
- Do not inject prior-decision memory as evidence.
- Keep unavailable information unavailable.
- Record the authority manifest hash in the batch manifest.
- Reject any final rating outside the deterministic permission corridor.
- Treat `action_policy` as a neutral research stance. Current packets must not
  contain personal position sizing, holding, entry, exit, or new-money
  instructions.

Room16 maps its research taxonomy to the product taxonomy without upgrading
conviction:

| Research rating | Product rating |
| --- | --- |
| Strong Buy, Buy | Buy |
| Accumulate | Overweight |
| Hold | Hold |
| Tactical Trim, Tactical Underweight, Underweight | Underweight |
| Sell, Avoid | Sell |

## Regression Policy

The contract is checked against:

- synthetic company-agnostic instruments
- multiple generic business archetypes
- the full stored historical packet corpus
- tampered artifacts
- ticker/date mismatches
- unregistered evidence
- blocked validation
- forbidden analyst tool use
- final-rating escape attempts
- personalized position-instruction leakage
- runtime-core scans for company-specific overrides

Adding a new company must require data and evidence, not a new conditional
branch.

## Current-Ingestion Boundary

The generic current runner stages sources below `.runtime/current-research`
and writes only final authority/report outputs below the ignored output root.
For U.S. SEC filers it uses the official SEC ticker map, CompanyFacts, and
submissions APIs. A current Item 2.02 8-K result exhibit is integrated only
when its fiscal quarter matches the latest mapped 10-Q CompanyFacts accession.
The exhibit may add issuer-defined operating bridges, segment comparisons,
adjusted-result context, market-share disclosures, and explicit guidance; it
never replaces the matching CompanyFacts GAAP statements. Unsupported,
ambiguous, annual, or not-yet-CompanyFacts-covered result periods stop the run
instead of falling back to reconstructed press-release financials.
Bare numeric bridge cells are accepted only when the issuer explicitly labels
the table as percentages. For repeated SEC comparative facts, the latest filing
supersedes an older presentation only when canonical metric, XBRL concept and
exact measurement dates match. First-quarter cash-flow facts are selected as
the current year-to-date period rather than allowing an older Q2/Q3 YTD value to
surface in the report.

For Budapest Stock Exchange equities it uses the official
BSE issuer profile, issuer-submitted IFRS financial tables and exchange OHLCV.
Other jurisdictions require their own official-registry adapter; they must not
be handled through ticker-specific exceptions.

For SEC issuers, Nasdaq's public official historical-data surface is the
default price path. Massive/Polygon daily aggregates remain an optional
authenticated adapter and are classified as `trusted_market_data_vendor`
because the provider documents SIP/exchange-derived coverage. BSE issuers use
official exchange OHLCV. Yahoo Finance remains a low-authority source and
cannot satisfy the Authority Bundle price gate.

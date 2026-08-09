# Research Agent Deterministic Core

Canonical local path:

```text
/Users/BjornRosinger/Documents/DreamFactory/Room16/research-agent-ops
```

Retired legacy path:

```text
/Users/BjornRosinger/Documents/New project 2
```

`New project 2` must not exist as a root folder or root symlink in
`/Users/BjornRosinger/Documents`. The old compatibility link was archived under
`/Users/BjornRosinger/Documents/Codex/path-hygiene-compatibility-links/`.
New work must use the canonical Room16 path above.

## Current Room 16 authority contract

The deterministic layer is the truth boundary. For BSE issuers it ingests the
official full report in addition to exchange summary tables, carries explicit
corporate-action adjustment metadata, and blocks when the official financial
core is incomplete. Technical output distinguishes moving-average alignment
from an actual cross event. Missing measurements have explicit coverage
states and are never described as low risk.

Instrument discovery belongs to the product intake layer. Jurisdiction
adapters belong here and are added only when an actual requested market needs
one; unsupported markets remain fail-closed instead of receiving vendor
fundamental substitutes.

This project keeps LLM agents out of the accounting and calculation layer.

Core rule:

- Python calculates metrics.
- Python validates metrics and logic.
- LLM agents may only interpret validated packets.
- Final reports may use numbers only from `data_packet.json`, `metrics_packet.json`, `validation_report.json`, or explicitly registered sources in `source_registry.json`.
- Every report-capable run must export and pass a
  `room16.research_authority_bundle@2`; there is no configuration switch that
  bypasses this hand-off.
- Runtime-discovered sources are merged into the registry before validation,
  and calculated technical values retain their OHLCV provenance.
- The deterministic decision packet expresses a research stance and
  confirmation/risk markers. It does not prescribe personal position sizes,
  holdings, entries, exits, or new-money actions.

Valuation sensitivity, the financial-risk screen, the separation of company
rating from technical timing, and their limitations are specified in
[`docs/ANALYTICAL_CORE_V02.md`](docs/ANALYTICAL_CORE_V02.md).

The separate shadow-only valuation calibration contract and readiness runner
are documented in
[`docs/VALUATION_CALIBRATION_V1.md`](docs/VALUATION_CALIBRATION_V1.md). They
require hash-bound, corporate-action-adjusted 252-trading-day outcomes and
never activate a valuation score automatically. The provider-neutral outcome
workbench creates either an explicitly unverified draft or a self-contained
`room16.valuation_calibration_source_bundle@2`; verified mode additionally
requires evidence-bound usage rights and an independent human review.

The initial build includes Pydantic packet schemas, technical/fundamental/valuation calculations, source-authority checks, trade/rating/news validation rules, regression tests for known failures, and a pipeline skeleton that stops report generation on blocking validation errors.

## Mandatory Room16 Handoff

For each ticker and analysis date the pipeline writes:

```text
<output_dir>/<TICKER>/<YYYY-MM-DD>/authority_bundle/
```

The bundle contains copied input packets, the source registry, evidence
ledger, a compact validated context, and a manifest with hashes and blocking
checks. `company-dossier-lab` verifies the complete bundle before any model
call.

The binding contract is documented in
[`docs/RESEARCH_AUTHORITY_CONTRACT.md`](docs/RESEARCH_AUTHORITY_CONTRACT.md).

## Current Research Ingestion

The generic current-data entry point is:

```bash
ROOM16_SEC_USER_AGENT="Room16 Name contact@example.com" \
python -m research_agent.current \
  --ticker <TICKER> \
  --date <YYYY-MM-DD>
```

It resolves the issuer through the official SEC ticker map, fetches SEC
CompanyFacts and submissions, and integrates a structurally supported current
Item 2.02 result exhibit only when the same fiscal quarter is already covered
by the mapped 10-Q CompanyFacts accession. Result exhibits add operating and
guidance context; explicitly percent-labelled bridge tables may carry bare
numeric cells, but unlabelled tables may not. They do not replace GAAP
statements. Later SEC comparative presentations supersede older values only for
the same concept and exact measurement dates, and a first-quarter cash-flow
period is treated as the current year-to-date period. The runner obtains daily
OHLCV through Nasdaq's public official historical-data surface by default,
stages temporary inputs below `.runtime/current-research/`, and invokes the
same deterministic pipeline.
Outputs appear below `research_agent/data/outputs/`, which is intentionally
Git-ignored except for `.gitkeep`.

Massive/Polygon remains an optional authenticated provider. Set
`ROOM16_PRICE_PROVIDER=massive` together with `MASSIVE_API_KEY` or
`POLYGON_API_KEY` to select it explicitly. In `auto` mode, Room16 prefers the
authenticated provider when a key exists and otherwise uses Nasdaq.

For equities listed on the Budapest Stock Exchange, the same command uses the
public official BSE issuer profile, issuer-submitted IFRS Excel tables and BSE
historical OHLCV. This path requires neither SEC identity nor a Massive key.
Aliases, WKNs and ISINs are resolved by the product before the canonical BSE
ticker enters this core.

There are no ticker-specific provider exceptions. A security absent from all
enabled official jurisdiction adapters stops with an explicit adapter gap.
Vendor fundamentals and weak price feeds do not silently replace missing
authority sources. Metrics not present in the official tables remain
unavailable rather than becoming zero.

Primary references:

- SEC EDGAR APIs:
  https://www.sec.gov/search-filings/edgar-application-programming-interfaces
- SEC ticker map:
  https://www.sec.gov/files/company_tickers.json
- Massive daily aggregates:
  https://massive.com/docs/rest/stocks/aggregates/custom-bars
- Nasdaq historical market data:
  https://www.nasdaq.com/market-activity/stocks
- Budapest Stock Exchange company profiles and issuer-submitted financials:
  https://www.bse.hu/pages/company_profile/

## Markdown Report Auditor

The post-generation auditor checks finished Markdown reports against validated packets:

```bash
python -m research_agent.audit.report_linter \
  --report path/to/report.md \
  --metrics path/to/metrics_packet.json \
  --validation path/to/validation_report.json \
  --sources path/to/source_registry.json \
  --evidence path/to/evidence_ledger.json
```

The evidence ledger is required for a full generated-report audit because one
sentence can contain several distinct financial metrics. The linter emits
`audit_report.json`-style output and exits with status `2` when blocking audit
errors are found.

## Decision Engine

The final Investment Committee layer receives a deterministic `DecisionPacket` with:

- `allowed_ratings`
- `blocked_ratings`
- `preferred_rating`
- signal scores for fundamentals, technicals, valuation, and risk
- a neutral research-stance policy derived from the preferred rating

The final writer may not output a blocked rating. This keeps cautious research
views from becoming accidental `Sell` calls and constructive views from
becoming unconstrained `Buy` calls. Personal portfolio instructions are not
part of the deterministic packet.

## Auto-Repair And Quality Gate

When a Markdown draft fails audit, the repair loop can attempt up to three controlled repairs and then re-run the auditor. Successful repairs can write:

- `repaired_report.md`
- `final_report.md`
- `quality_score.json`

If repair cannot clear blocking issues, the system writes `manual_review_required.md`, `draft_failed_audit.md`, and `audit_report.json` instead.

The quality gate requires a score of at least `85`, no blocking validation errors, no blocking audit errors, and a final rating allowed by `DecisionPacket`.

## Agent OS Readiness Pack

Hermes/OpenClaw-inspired operating improvements live behind a local, safe readiness pack:

```bash
python3 scripts/ops/agent_os_readiness.py
```

The runner writes `outputs/agent_os_readiness/` with:

- OpenClaw migration dry-run and capability matrix
- local skill registry with risk decisions
- Obsidian-compatible memory inbox candidates and SQLite search index
- proposed automation job cards
- local operator inbox contract
- local/Docker terminal backend contracts
- static guardrails-as-code scan

It does not install external skills, read secret values, mutate runtime config, write canonical Obsidian notes, create automations, or call the network.

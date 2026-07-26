# Room16 Research Authority Contract

Contract ID: `room16.research_authority_bundle`  
Contract version: `1`

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
- `validated_context.md`
- `authority_manifest.json`

The manifest records each artifact's relative path, SHA-256 hash, and size.
The consumer rejects missing files, path escapes, hash changes, identity
mismatches, unsupported contract versions, and blocked analysis permission.

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
submissions APIs. Other jurisdictions require their own official-registry
adapter; they must not be handled through ticker-specific exceptions.

The first enabled market adapter is Massive/Polygon daily aggregates. It is
classified as `trusted_market_data_vendor` because the provider documents
SIP/exchange-derived coverage. Yahoo Finance remains a low-authority source and
cannot satisfy the Authority Bundle price gate.

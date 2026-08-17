# Renderer Contract

## Scope

The same hard boundary applies to PDF, DOCX, Markdown, JSON, API and UI
renderers. A renderer is a deterministic consumer of one verified compiler
bundle and a declared renderer profile.

## Input

- verified `room16.compiler_artifact_bundle@1`;
- supported `room16.compiler.render_input_ir@1` or an explicitly marked
  legacy canonical report payload during migration;
- renderer ID/version and profile hash;
- locale, theme, page/layout and accessibility settings;
- permitted visibility/redaction policy IDs from Research;
- capability decision and compiler eligibility state.

No renderer may fetch sources or receive unbound factual prose.

## Allowed operations

- select only compiler-authorized visible sections;
- order sections according to a declared profile;
- format dates, decimals and units using compiler-supplied display values or a
  compiler-owned display policy;
- localize approved text fragments without changing their semantic IDs;
- paginate, wrap, style, add fonts, headers, footers and navigation;
- hide optional content according to an explicit visibility rule;
- create links to bundle-bound source/locator references;
- add non-factual document metadata such as page numbers and renderer version.

## Forbidden operations

- create or infer facts, metrics, periods, units or formula results;
- recalculate, round or scale a financial value outside the supplied display
  policy;
- create, merge, split or rewrite claims in a way that changes meaning;
- invent evidence, citations, source hierarchy or locator details;
- create or change decisions, ratings, score, risk state, counterevidence,
  timing, permissions or non-advice state;
- suppress a diagnostic with release effect or render a blocked compile as
  eligible;
- fetch fresh data, call a model for factual prose or fall back to legacy data;
- convert a non-authoritative TradingAgents annotation into canonical text;
- declare PDF/DOCX/Markdown as semantic truth.

## No-new-truth invariant

Machine checks must establish:

```text
RendererOutput.fact_ids     ⊆ CompilerBundle.fact_ids
RendererOutput.claim_ids    ⊆ CompilerBundle.claim_ids
RendererOutput.decision_ids ⊆ CompilerBundle.decision_ids
RendererOutput.source_ids   ⊆ CompilerBundle.source_ids
RendererOutput.visible_numbers ⊆ CompilerBundle.display_tokens
```

Each visible factual token carries or can be deterministically mapped to:

- source artifact ID;
- semantic object ID;
- optional field/path;
- display-token ID;
- renderer location (page, block, cell or UI node).

Unmatched number-like tokens block unless they belong to a small enumerated
non-factual class such as page number, document generation timestamp or schema
version. The exception class itself is contract-versioned.

Text parity uses canonical semantic spans, not only whole-document text. Each
rendered claim/rationale/source caption maps to an approved compiler span ID.
Arbitrary renderer prose is forbidden.

## Renderer output

`room16.rendered_artifact_set@1` contains:

- source bundle ID and verified bundle hash;
- renderer ID/version/profile and environment attestation;
- output format, file hash and byte length;
- fact/claim/decision/source/display-token inventories;
- no-new-truth, numeric/table, citation and text-parity results;
- extraction method/version for PDF and DOCX checks;
- rendering diagnostics and render verdict;
- an explicit statement that the output has no independent release authority.

## Format-specific rules

| Renderer | Additional rule |
|---|---|
| Markdown | Stable semantic anchors and visible source IDs; no hidden HTML factual content |
| JSON | Projection schema only; no consumer-derived fields presented as compiler fields |
| API | Returns bundle/projection IDs and capability errors; no recalculation endpoints |
| UI | Components bind to semantic IDs; labels/filters cannot change verdict meaning |
| DOCX | Tables and footnotes preserve semantic anchors in custom properties or audit sidecar |
| PDF | Extracted text/table inventory must match the sidecar; visual clipping is a blocking render defect |

## LLM use

An LLM may only operate on pre-approved, ID-bound text fragments in a mode that
cannot introduce arbitrary prose. Present authority-bound TradingAgents debate
therefore remains a separate annotation input and is not eligible for the
canonical renderer path in initial BA10.


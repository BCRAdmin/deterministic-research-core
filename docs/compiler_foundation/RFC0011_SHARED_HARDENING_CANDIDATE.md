# RFC-0011 Candidate — Shared Alpha H1–H4 Hardening

Status: candidate for independent rereview. It is not accepted or frozen.

## Boundary

RFC-0011 is an additive successor beside the frozen BA3 SourceAcquisitionIR /
SourceSnapshotIR and RFC-0010 live-capture bridge. It does not reinterpret,
migrate, or rewrite any v1 artifact. Existing CompanyFacts and Nasdaq paths
remain authoritative for frozen base evidence.

The successor adds four shared capabilities:

1. H1: a policy-bound supplemental source authority that captures discovery
   bytes before parsing and selected child documents before normalization;
2. H2: a semantic-family metric resolver that prefers explicit unsupported,
   stale-only, or ambiguous receipts over unsafe fallback;
3. H3: one economic-period, comparative-role, and freshness state machine;
4. H4: an append-only operational ledger whose aggregate is derived evidence,
   never semantic authority.

## H1 contract and trust order

The immutable family is `SupplementalSourcePolicyIR@1`,
`DiscoveryRequestIR@1`, `DiscoveryCaptureReceiptIR@1`,
`DiscoveredSourceCandidateIR@1`, `DiscoveredSourceSetIR@1`,
`SupplementalCaptureReceiptIR@1`, `SupplementalEvidenceSetIR@1`, and
`DocumentObservationIR@1`.

The policy is self-hashed before the first network callback. HTTPS domain,
media-type, request-count, candidate-count, child-count, and byte limits fail
closed. Redirect targets are revalidated. Discovery parsers can read only a
verified content-addressed capture. Candidate and child identities are derived
from source family, issuer identity, accession/report identity, document name,
and parent discovery receipt. Offline replay performs no network call and
reconstructs the same evidence-set hash from immutable receipts and bytes.

Supported profiles are `sec_primary_document`, `sec_filed_exhibit`, and the
inactive `structured_regulatory_dataset` profile. The neutral normalizer emits
text blocks and table coordinates. Observation discovery requires an explicit
reported label and never trusts an ambiguous numeric cardinality. Source-layer
code contains no ticker-specific URL, regex, or issuer branch.

## H2 and H3

H2 resolves only registered semantic families, then checks authority, period,
unit, dimensions, freshness, primary/comparative role, and directness. Equal
top scores produce `AMBIGUOUS`; stale-only candidates produce `STALE_ONLY`;
unknown or incompatible evidence produces `UNSUPPORTED`.

H3 derives `INSTANT|DURATION`, duration role, comparative role, and
`CURRENT|AGING|STALE` from the economic period. A recent filing date never
makes an old economic period current. Derived inputs must share compatible
period and comparative states and must not be stale.

## H4

Stage events are canonical JSON lines linked by `previous_event_sha256` and
`event_sha256`. File locking serializes concurrent writers. Existing events are
validated before append, recovery adds new events, and missing terminal events
remain visible as incomplete runs. Batch gates block replay provider calls and
manual semantic intervention.

## Compatibility, rollback, and threat model

Compatibility is additive: no frozen source or archetype file is edited and
Product remains read-only. Rollback is removal of the RFC-0011 candidate commit
and its new paths; old evidence requires no migration.

Threats covered include parse-before-capture, domain/redirect escape,
oversized or excessive discovery, mutable child evidence, replay network use,
ambiguous number guessing, numeric-similarity synonym selection, stale-period
promotion by recent refiling, event tampering, duplicate/out-of-order append,
and hidden semantic intervention.

The binding acceptance matrix is the 61-row
`room16.alpha.shared_h1_h4_acceptance_matrix@1` supplied by the operator. This
candidate does not authorize the fixed 24-company batch, Product Report v2,
release, deploy, publication, or commerce.

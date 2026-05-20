# Room16 Media Ingest Integration

Status: integration policy  
Applies to: Quellwert / Room16 evidence and report pipelines

## Non-Mutation Rules

1. Media transcripts must not directly change `MetricsPacket`.
2. Media transcripts must not directly change `DecisionPacket`.
3. Media transcripts must not change ratings, guards, calibration or report status.
4. Media transcripts must not create public output.
5. Media claims may enter an EvidenceLedger only as candidates.

## Evidence Candidate Lane

Media-derived claims may be stored as `EvidenceCandidate`-style artifacts when they include:

- source metadata
- source type and owner
- timestamp
- speaker attribution
- transcript confidence
- rights/use status
- verification requirement
- proposed source rank
- reviewer status

## Promotion to EvidenceItem

Promotion from candidate to EvidenceItem requires:

- source authenticity check
- timestamp
- speaker attribution
- rights/use check
- hard financial claim verification against primary or official source
- source rank assignment
- Vivi or human reviewer approval
- explicit note that no packet/rating mutation occurred automatically

## Source Rank Rules

- Official IR/company source can be high-rank candidate evidence after review.
- Third-party YouTube, podcast, vendor or interview material remains low or medium rank unless independently verified.
- Hard financial claims from media must be checked against IR, SEC, filings, earnings release or official presentation before report use.

## Public Report Boundary

Reports may paraphrase and cite timestamps after review. Reports must not reproduce full third-party transcripts or long quotes. Public output remains Promotion-gated and Non-Advice-gated.

## Acceptance

Room16 integration is safe when media ingest only creates candidate artifacts, preserves auditability, and leaves packet, guard, rating, calibration and publication state unchanged.

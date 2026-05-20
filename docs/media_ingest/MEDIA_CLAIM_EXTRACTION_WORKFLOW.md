# Media Claim Extraction Workflow

Status: internal workflow  
Output lane: evidence candidates only

## Core Rule

Claims extracted from media transcripts are Evidence Candidates. They do not become EvidenceItems, report claims, packet metrics or public text until the relevant review gate promotes them.

## Extraction Steps

1. Read `transcript_metadata.json`.
2. Confirm rights, source type and allowed use.
3. Read `transcript_clean.md` with timestamps if available.
4. Extract only atomic claims.
5. Preserve speaker attribution.
6. Preserve timestamp or mark `timestamp_missing`.
7. Mark unclear transcription spans.
8. Mark hard claims as `requires_verification=true`.
9. Write:
   - `evidence_candidates.json`
   - `claim_candidates.md`

## Candidate Fields

- `claim_text`
- `speaker`
- `timestamp`
- `source_ref`
- `confidence`
- `requires_verification`
- `usable_in_report`
- `reason`

## Hard Claim Policy

Hard financial, KPI, guidance, valuation, strategy-commitment or regulatory claims require later verification against IR, SEC, official filing, official release or another approved primary source. YouTube, podcast or vendor media alone is not enough unless it is the official IR/company source and still passes review.

## Speaker Attribution

Speaker attribution must stay attached to each candidate. If the speaker is unknown, use `unknown_speaker` and set confidence below `medium`.

## Uncertain Transcript Text

Uncertain transcript passages must be marked in the candidate reason and cannot be promoted without review.

## Report Boundary

`usable_in_report=yes` may only be set when:

- the source is allowed
- the excerpt is paraphrased or short enough
- the candidate has timestamp and speaker attribution
- hard claims have independent verification or are explicitly framed as unverified context

## Acceptance

Claim extraction is complete when each candidate can be audited back to source metadata, timestamp, speaker and verification need.

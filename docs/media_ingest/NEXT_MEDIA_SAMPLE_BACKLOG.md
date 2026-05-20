# Next Media Sample Backlog

Status: active draft
Scope: Media Ingest Playbook next operator sample
Risk class: R0 doc-only pattern
Runtime changes: none

## Purpose

Prepare the next real Media Ingest dry run without downloads, API calls, YouTube fetches or automatic report use.

## Allowed Sample Types

- Operator-owned audio file.
- Operator-owned video file.
- Manually provided transcript.
- Public company webcast transcript supplied by the operator with source URL and allowed-use note.
- Synthetic internal test sample clearly marked not evidence.

## Operator Must Provide

- Source file or transcript path.
- Source title.
- Source owner.
- Source URL if public.
- Date and duration if known.
- Rights/use status.
- Allowed use.
- Confirmation that the sample may be processed locally.

## After Operator Input

The pipeline may create:

- `transcript_raw.txt`
- `transcript_clean.md`
- `transcript_metadata.json`
- `claim_candidates.md`
- `evidence_candidates.json`
- `METADATA_VALIDATION.md/json`
- `VIVI_MEDIA_INGEST_SAMPLE_REVIEW.json`
- `MEDIA_INGEST_DRY_RUN_SUMMARY.md/json`

## Why No Downloads/API Now

- No Operator-provided real sample is attached.
- No API key use is approved.
- No YouTube fetch is approved.
- No copyright or rights status has been established for a real source.

## Next Allowed Step

Wait for an operator-approved sample and run the existing Media Ingest dry-run workflow. Do not promote claims to EvidenceLedger or reports.

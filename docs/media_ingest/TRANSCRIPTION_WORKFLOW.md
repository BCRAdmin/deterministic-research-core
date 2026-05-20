# Transcription Workflow

Status: internal workflow  
Runtime: not activated by this document

## Workflow

1. Operator approves the source and intended use.
2. Source is referenced or locally stored only if allowed.
3. Transcription mode is selected:
   - local transcription, if local tooling is already available and permitted
   - API transcription only if a separate Operator-Go and credentials policy exists
   - manual transcript ingestion, if the transcript is provided by the Operator
4. Outputs are created in an ingest folder:
   - `transcript_raw.txt`
   - `transcript_clean.md`
   - `transcript_metadata.json`
5. Quality checks are documented.
6. No direct report use happens without review.

## Required Metadata

- `source_title`
- `source_url`
- `source_type`
- `source_owner`
- `date`
- `duration`
- `language`
- `transcription_method`
- `rights_status`
- `operator_approval`
- `allowed_use`
- `download_performed`
- `download_operator_approval`
- `public_output_allowed`
- `report_use_allowed`
- `evidence_use_allowed`
- `requires_human_review`

## Quality Checks

- language identified
- speaker changes marked where recognizable
- timestamps retained where available
- transcription confidence noted
- known transcription gaps listed
- uncertain text marked
- source reliability class recorded

## Output Rules

- `transcript_raw.txt` may contain rough machine or manual transcript text and must stay internal.
- `transcript_clean.md` may normalize formatting but must not add unverified claims.
- `transcript_metadata.json` is the controlling metadata artifact.
- No full third-party transcript is copied into public docs.
- Any extracted hard financial claim remains `requires_verification=true`.

## Stop Conditions

Stop and mark `manual_human_review` if:

- rights status is unclear
- source authenticity is unclear
- transcript quality is too poor for claims
- the source requires login/paywall/DRM circumvention
- the user asks for public output before Evidence Gate

## Acceptance

A transcription packet is complete only when the three core outputs exist, metadata validates, known gaps are documented and Vivi can review the packet without fetching or guessing missing source data.

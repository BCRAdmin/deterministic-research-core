# Media Ingest Helper Scripts

These helpers are safe local preparation tools for `docs/media_ingest`.

## Scripts

- `prepare_media_ingest_folder.sh`: creates a local ingest folder with conservative placeholder files and metadata.
- `validate_transcript_metadata.py`: validates `transcript_metadata.json` using `docs/media_ingest/transcript_metadata.schema.json`.

## Safety Boundary

- No downloads.
- No API calls.
- No YouTube fetches.
- No secrets.
- No report, packet, guard, rating, calibration or public-output changes.

## Example

```bash
scripts/media_ingest/prepare_media_ingest_folder.sh \
  --slug sample-earnings-call \
  --source-title "Sample Earnings Call" \
  --source-type official_ir_webcast

python3 scripts/media_ingest/validate_transcript_metadata.py \
  outputs/media_ingest/sample-earnings-call/transcript_metadata.json
```

The generated metadata defaults to draft/candidate status. A packet may still need Operator approval and Vivi review before it is usable.

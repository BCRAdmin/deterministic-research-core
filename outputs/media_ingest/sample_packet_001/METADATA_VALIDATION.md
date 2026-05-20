# Metadata Validation

Status: pass  
Validated at UTC: 2026-05-20T16:56:59Z  
Schema: `docs/media_ingest/transcript_metadata.schema.json`  
Validator: `scripts/media_ingest/validate_transcript_metadata.py`

## Command

```bash
python3 scripts/media_ingest/validate_transcript_metadata.py outputs/media_ingest/sample_packet_001/transcript_metadata.json --schema docs/media_ingest/transcript_metadata.schema.json
```

## Result

```text
metadata_ok outputs/media_ingest/sample_packet_001/transcript_metadata.json
```

## Notes

- Synthetic dry-run markers are present.
- `not_usable_as_evidence=true`.
- `report_use_allowed=false`.
- `public_output_allowed=false`.
- No download, API call or YouTube fetch occurred.

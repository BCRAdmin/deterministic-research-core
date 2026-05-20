#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  prepare_media_ingest_folder.sh --slug SLUG [options]

Options:
  --root PATH                    Output root (default: outputs/media_ingest)
  --slug SLUG                    Folder slug, letters/numbers/dot/underscore/dash only
  --source-title TITLE           Source title (default: Untitled media source)
  --source-url URL               Source URL, or not_provided
  --source-path PATH             Local source path, or not_provided
  --source-type TYPE             owned_file|official_ir_webcast|official_company_youtube|third_party_youtube|podcast|manual_transcript|other
  --source-owner OWNER           Source owner (default: not_provided)
  --date DATE                    Source date (default: unknown)
  --duration DURATION            Duration (default: unknown)
  --language LANGUAGE            Language (default: unknown)
  --transcription-method METHOD  local_whisper|manual_transcript|api_transcription_operator_approved|not_transcribed_yet|other
  --rights-status STATUS         owned|permitted_public_ir|permitted_summary_only|operator_provided|unknown|blocked
  --operator-approval            Mark operator_approval=true
  --allowed-use CSV              Allowed uses (default: internal_draft,evidence_candidate)
  -h, --help                     Show help

This script creates local placeholders only. It does not download, fetch YouTube,
call APIs, modify reports, or change any runtime state.
EOF
}

root="outputs/media_ingest"
slug=""
source_title="Untitled media source"
source_url="not_provided"
source_path="not_provided"
source_type="other"
source_owner="not_provided"
source_date="unknown"
duration="unknown"
language="unknown"
transcription_method="not_transcribed_yet"
rights_status="unknown"
operator_approval="false"
allowed_use="internal_draft,evidence_candidate"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)
      root="${2:?missing value for --root}"
      shift 2
      ;;
    --slug)
      slug="${2:?missing value for --slug}"
      shift 2
      ;;
    --source-title)
      source_title="${2:?missing value for --source-title}"
      shift 2
      ;;
    --source-url)
      source_url="${2:?missing value for --source-url}"
      shift 2
      ;;
    --source-path)
      source_path="${2:?missing value for --source-path}"
      shift 2
      ;;
    --source-type)
      source_type="${2:?missing value for --source-type}"
      shift 2
      ;;
    --source-owner)
      source_owner="${2:?missing value for --source-owner}"
      shift 2
      ;;
    --date)
      source_date="${2:?missing value for --date}"
      shift 2
      ;;
    --duration)
      duration="${2:?missing value for --duration}"
      shift 2
      ;;
    --language)
      language="${2:?missing value for --language}"
      shift 2
      ;;
    --transcription-method)
      transcription_method="${2:?missing value for --transcription-method}"
      shift 2
      ;;
    --rights-status)
      rights_status="${2:?missing value for --rights-status}"
      shift 2
      ;;
    --operator-approval)
      operator_approval="true"
      shift
      ;;
    --allowed-use)
      allowed_use="${2:?missing value for --allowed-use}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$slug" ]]; then
  echo "Missing required --slug" >&2
  usage >&2
  exit 2
fi

if [[ ! "$slug" =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "Invalid slug: use only letters, numbers, dot, underscore, dash" >&2
  exit 2
fi

target="$root/$slug"
if [[ -e "$target" ]]; then
  echo "Refusing to overwrite existing ingest folder: $target" >&2
  exit 1
fi

mkdir -p "$target/review"

: > "$target/transcript_raw.txt"
cat > "$target/transcript_clean.md" <<'EOF'
# Transcript Clean

Status: draft

No transcript has been added yet.
EOF

cat > "$target/claim_candidates.md" <<'EOF'
# Claim Candidates

Status: evidence candidates only

No claims extracted yet.
EOF

printf '[]\n' > "$target/evidence_candidates.json"

python3 - "$target/transcript_metadata.json" "$source_title" "$source_url" "$source_path" "$source_type" "$source_owner" "$source_date" "$duration" "$language" "$transcription_method" "$rights_status" "$operator_approval" "$allowed_use" <<'PY'
import json
import sys
from datetime import datetime, timezone

(
    output_path,
    source_title,
    source_url,
    source_path,
    source_type,
    source_owner,
    source_date,
    duration,
    language,
    transcription_method,
    rights_status,
    operator_approval,
    allowed_use,
) = sys.argv[1:]

metadata = {
    "schema_version": "media_ingest_metadata_v1",
    "source_title": source_title,
    "source_url": source_url,
    "source_path": source_path,
    "source_type": source_type,
    "source_owner": source_owner,
    "date": source_date,
    "duration": duration,
    "language": language,
    "transcription_method": transcription_method,
    "rights_status": rights_status,
    "operator_approval": operator_approval == "true",
    "allowed_use": [item.strip() for item in allowed_use.split(",") if item.strip()],
    "download_performed": False,
    "download_operator_approval": False,
    "public_output_allowed": False,
    "report_use_allowed": False,
    "evidence_use_allowed": "candidate_only",
    "requires_human_review": True,
    "known_transcription_gaps": [],
    "confidence_notes": "template_created_no_transcript_reviewed",
    "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
}

with open(output_path, "w", encoding="utf-8") as handle:
    json.dump(metadata, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY

cat > "$target/review/VIVI_MEDIA_INGEST_REVIEW_TEMPLATE.md" <<'EOF'
# Vivi Media Ingest Review

- Review status: manual_human_review
- Source allowed:
- Rights policy clear:
- Download gate ok:
- Transcript quality:
- Hard claims require verification:
- Long quotes present:
- Direct report promotion present:
- Obsidian gate ok:
- Room16 candidate lane ok:
- Recommended action:
EOF

echo "created_media_ingest_folder=$target"

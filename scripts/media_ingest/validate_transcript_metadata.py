#!/usr/bin/env python3
"""Validate media ingest transcript metadata without external dependencies."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def metadata_path(input_path: Path) -> Path:
    if input_path.is_dir():
        return input_path / "transcript_metadata.json"
    return input_path


def type_matches(value: Any, expected: str | list[str]) -> bool:
    if isinstance(expected, list):
        return any(type_matches(value, item) for item in expected)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    return True


def value_satisfies_rules(value: Any, rules: dict[str, Any]) -> bool:
    expected_type = rules.get("type")
    if expected_type and not type_matches(value, expected_type):
        return False
    if isinstance(value, str) and rules.get("minLength", 0) > 0 and not value.strip():
        return False
    if "const" in rules and value != rules["const"]:
        return False
    if "enum" in rules and value not in rules["enum"]:
        return False
    if isinstance(value, list):
        item_rules = rules.get("items", {})
        item_enum = item_rules.get("enum")
        item_type = item_rules.get("type")
        for item in value:
            if item_type and not type_matches(item, item_type):
                return False
            if item_enum and item not in item_enum:
                return False
    return True


def validate(metadata: dict[str, Any], schema: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    required = schema.get("required", [])
    properties = schema.get("properties", {})
    additional_properties = schema.get("additionalProperties", True)

    for field in required:
        if field not in metadata:
            errors.append(f"missing_required_field:{field}")

    if additional_properties is False:
        allowed = set(properties)
        for field in metadata:
            if field not in allowed:
                errors.append(f"unexpected_field:{field}")

    for field, rules in properties.items():
        if field not in metadata:
            continue
        value = metadata[field]
        if "oneOf" in rules:
            if not any(value_satisfies_rules(value, option) for option in rules["oneOf"]):
                errors.append(f"one_of_no_match:{field}")
            continue
        expected_type = rules.get("type")
        if expected_type and not type_matches(value, expected_type):
            errors.append(f"wrong_type:{field}:expected_{expected_type}")
            continue
        if isinstance(value, str) and rules.get("minLength", 0) > 0 and not value.strip():
            errors.append(f"empty_string:{field}")
        if "const" in rules and value != rules["const"]:
            errors.append(f"wrong_const:{field}:expected_{rules['const']}")
        if "enum" in rules and isinstance(value, str) and value not in rules["enum"]:
            errors.append(f"invalid_enum:{field}:{value}")
        if isinstance(value, list):
            item_rules = rules.get("items", {})
            item_enum = item_rules.get("enum")
            item_type = item_rules.get("type")
            for index, item in enumerate(value):
                if item_type and not type_matches(item, item_type):
                    errors.append(f"wrong_array_item_type:{field}[{index}]:expected_{item_type}")
                if item_enum and item not in item_enum:
                    errors.append(f"invalid_array_enum:{field}[{index}]:{item}")

    if metadata.get("download_performed") and not metadata.get("download_operator_approval"):
        errors.append("download_performed_without_download_operator_approval")

    if metadata.get("public_output_allowed"):
        errors.append("public_output_allowed_must_remain_false_for_ingest_packet")

    allowed_use = metadata.get("allowed_use", [])
    allowed_use_values = [allowed_use] if isinstance(allowed_use, str) else allowed_use

    if metadata.get("report_use_allowed") and "report_after_evidence_gate" not in allowed_use_values:
        errors.append("report_use_allowed_without_report_after_evidence_gate_allowed_use")

    if metadata.get("sample_type") == "synthetic_operator_test":
        if metadata.get("source_type") != "synthetic_test":
            errors.append("synthetic_operator_test_requires_source_type_synthetic_test")
        if metadata.get("rights_status") != "synthetic_internal_test_only":
            errors.append("synthetic_operator_test_requires_rights_status_synthetic_internal_test_only")
        if metadata.get("allowed_use") != "pipeline_dry_run_only":
            errors.append("synthetic_operator_test_requires_allowed_use_pipeline_dry_run_only")
        if metadata.get("not_real_source") is not True:
            errors.append("synthetic_operator_test_requires_not_real_source_true")
        if metadata.get("not_usable_as_evidence") is not True:
            errors.append("synthetic_operator_test_requires_not_usable_as_evidence_true")

    if not metadata.get("operator_approval"):
        warnings.append("operator_approval_false_packet_is_template_or_preapproval_only")

    if metadata.get("rights_status") in {"unknown", "blocked"}:
        warnings.append(f"rights_status_{metadata.get('rights_status')}_requires_manual_human_review")

    if metadata.get("transcription_method") == "not_transcribed_yet":
        warnings.append("transcription_method_not_transcribed_yet")

    if metadata.get("requires_human_review") is not True:
        warnings.append("requires_human_review_not_true")

    synthetic_test = metadata.get("sample_type") == "synthetic_operator_test"

    if metadata.get("evidence_use_allowed") != "candidate_only" and not (
        synthetic_test and metadata.get("evidence_use_allowed") == "no"
    ):
        warnings.append("evidence_use_allowed_is_not_candidate_only")

    return errors, warnings


def main() -> int:
    repo_default_schema = Path(__file__).resolve().parents[2] / "docs" / "media_ingest" / "transcript_metadata.schema.json"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Path to transcript_metadata.json or ingest folder")
    parser.add_argument("--schema", default=str(repo_default_schema), help="Path to transcript metadata schema")
    parser.add_argument("--strict-ready", action="store_true", help="Treat readiness warnings as validation errors")
    args = parser.parse_args()

    meta_path = metadata_path(Path(args.input))
    schema_path = Path(args.schema)

    if not meta_path.exists():
        print(f"metadata_error missing_metadata:{meta_path}", file=sys.stderr)
        return 1
    if not schema_path.exists():
        print(f"metadata_error missing_schema:{schema_path}", file=sys.stderr)
        return 1

    try:
        metadata = load_json(meta_path)
    except json.JSONDecodeError as exc:
        print(f"metadata_error invalid_metadata_json:{meta_path}:{exc}", file=sys.stderr)
        return 1

    try:
        schema = load_json(schema_path)
    except json.JSONDecodeError as exc:
        print(f"metadata_error invalid_schema_json:{schema_path}:{exc}", file=sys.stderr)
        return 1

    if not isinstance(metadata, dict):
        print("metadata_error metadata_root_not_object", file=sys.stderr)
        return 1
    if not isinstance(schema, dict):
        print("metadata_error schema_root_not_object", file=sys.stderr)
        return 1

    errors, warnings = validate(metadata, schema)
    if args.strict_ready and warnings:
        errors.extend(f"strict_warning:{warning}" for warning in warnings)

    for warning in warnings:
        print(f"metadata_warning {warning}")

    if errors:
        for error in errors:
            print(f"metadata_error {error}", file=sys.stderr)
        return 1

    print(f"metadata_ok {meta_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Generate strict BA11 JSON Schemas and the machine-readable contract catalog."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from research_agent.canary_governance.contracts import CONTRACT_MODELS
from research_agent.canary_governance.diagnostics import DIAGNOSTICS
from research_agent.compiler_foundation.canonical import sha256_json


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("research_agent/canary_governance/schemas"),
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    entries = []
    for model in sorted(CONTRACT_MODELS, key=lambda item: item.__name__):
        schema = model.model_json_schema(mode="validation")
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["x-room16-unknown-field-policy"] = "fail_closed"
        schema["x-room16-canonicalization"] = "room16.canonical_json@1"
        schema["x-room16-hash-algorithm"] = "sha256"
        filename = f"{model.__name__}.schema.json"
        encoded = json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
        (args.output / filename).write_text(encoded, encoding="utf-8")
        entries.append(
            {
                "model": model.__name__,
                "contract_id": model.model_fields["contract_id"].default,
                "schema_file": filename,
                "schema_sha256": sha256_json(schema),
                "unknown_field_policy": "fail_closed",
                "canonicalization_profile": "room16.canonical_json@1",
                "hash_algorithm": "sha256",
            }
        )
    catalog = {
        "contract_id": "room16.canary_contract_catalog",
        "schema_version": 1,
        "authority_owner": "research",
        "contracts": entries,
        "diagnostics": DIAGNOSTICS,
    }
    catalog["catalog_sha256"] = sha256_json(catalog)
    (args.output / "contract_catalog_v1.json").write_text(
        json.dumps(catalog, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "PASS", "contract_count": len(entries), "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

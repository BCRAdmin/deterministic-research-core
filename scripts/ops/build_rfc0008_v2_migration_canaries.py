#!/usr/bin/env python3
"""Build signed, deterministic WM/COST/ABT v2 migration canaries."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from nacl.signing import SigningKey

from research_agent.productization_v2.artifact_bundle import load_consumer_policy_v2
from research_agent.productization_v2.canary_migration import CANARY_STAMP, build_migration_canary
from research_agent.productization_v2.contracts import PublicKeyPolicyV2


ROOT = Path(__file__).resolve().parents[2]
PRODUCT = ROOT.parent / "company-dossier-lab"
CANARY_ROOT = (
    PRODUCT
    / ".runtime/cross-company-release-current"
    / f"ROOM16_WM_COST_ABT_CROSS_COMPANY_RC_{CANARY_STAMP}"
)
OUTPUT = ROOT / ".runtime/rfc0008/migration_canaries"
PRIVATE_KEY = ROOT / ".runtime/rfc0008/signing_key_ed25519.bin"
CONFIG = ROOT / "research_agent/productization_v2/config"


def export_review_fixtures(catalog: dict) -> None:
    fixture_root = CONFIG / "migration_canaries"
    if fixture_root.exists():
        shutil.rmtree(fixture_root)
    fixture_root.mkdir(parents=True)
    exported = []
    for item in catalog["canaries"]:
        ticker = item["ticker"]
        source_root = Path(item["bundle_root"])
        target = fixture_root / ticker
        target.mkdir()
        shutil.copyfile(source_root / "BUNDLE_MANIFEST.json", target / "BUNDLE_MANIFEST.json")
        shutil.copyfile(
            source_root / "migration/v1_manifest.json",
            target / "V1_BUNDLE_MANIFEST.json",
        )
        (target / "RECEIPT.json").write_text(
            json.dumps(item["receipt"], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        exported.append(
            {key: value for key, value in item.items() if key not in {"bundle_root", "receipt"}}
        )
    review_catalog = {
        **{key: value for key, value in catalog.items() if key != "canaries"},
        "canaries": exported,
    }
    (CONFIG / "migration_canary_catalog_v2.json").write_text(
        json.dumps(review_catalog, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-existing", action="store_true")
    args = parser.parse_args()
    if args.export_existing:
        catalog_path = OUTPUT / "migration_canary_catalog_v2.json"
        if not catalog_path.is_file():
            raise SystemExit("STOP existing RFC-0008 canary catalog is missing")
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        export_review_fixtures(catalog)
        print(json.dumps({"status": "PASS", "exported": len(catalog["canaries"])}, indent=2))
        return 0
    if not PRIVATE_KEY.is_file() or PRIVATE_KEY.stat().st_size != 32:
        raise SystemExit("STOP Research-only RFC-0008 signing key is missing")
    signing_key = SigningKey(PRIVATE_KEY.read_bytes())
    consumer_policy = load_consumer_policy_v2()
    key_policy = PublicKeyPolicyV2.model_validate_json(
        (CONFIG / "public_key_policy_v2.json").read_bytes()
    )
    key_policy.verify_self_hash()
    key_id = next(item.key_id for item in key_policy.keys if item.state == "active")
    results = []
    for counter, ticker in enumerate(("WM", "COST", "ABT"), start=1):
        archive = CANARY_ROOT / f"ROOM16_{ticker}_CROSS_COMPANY_RC_{CANARY_STAMP}.zip"
        results.append(
            build_migration_canary(
                ticker=ticker,
                archive=archive,
                output_root=OUTPUT / ticker,
                signing_key=signing_key,
                key_id=key_id,
                counter=counter,
                consumer_policy=consumer_policy,
                key_policy=key_policy,
            )
        )
    catalog = {
        "contract_id": "room16.rfc0008.migration_canary_catalog@1",
        "schema_version": 1,
        "consumer_policy_sha256": consumer_policy.policy_sha256,
        "key_policy_sha256": key_policy.policy_sha256,
        "canonical_runtime_changed": False,
        "native_source_production": False,
        "canaries": results,
    }
    catalog_path = OUTPUT / "migration_canary_catalog_v2.json"
    catalog_path.write_text(
        json.dumps(catalog, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    export_review_fixtures(catalog)
    print(json.dumps({**catalog, "catalog_path": str(catalog_path)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

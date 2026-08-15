# WM / COST / ABT Canary Results

| Company | Frozen ZIP SHA-256 | Double replay | Archive unchanged | Replay SHA-256 |
| --- | --- | --- | --- | --- |
| ABT | 0926d3cafd312556ec267b2b25214d255ff9352daed77a01b7852addbb48dc45 | True | True | b11915e9e66f805415487fe3898fd08f6c3a2b3a8abb1c92379edeebd442999a |
| COST | b97e6024855c7a772713ff9af4889987e4a9a8e5a3afca0d56a42a1ba8092ea4 | True | True | 07d9420b34bfc257b656e771dc8ad932cdbcd30d3144f153022babae46b22ba0 |
| WM | a6b6d15ad7004573a56ad057884563cfbeeb2c3162dae0641a1b361b5e416d72 | True | True | 1c5d74819831e3e0fb9b743dff99d081dbe45a4ce016af60be75eabbba7f278a |

```json
{
  "ABT": {
    "canary_unchanged": true,
    "double_replay_equal": true,
    "first": {
      "archive": "ROOM16_ABT_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448.zip",
      "archive_sha256_after": "0926d3cafd312556ec267b2b25214d255ff9352daed77a01b7852addbb48dc45",
      "archive_sha256_before": "0926d3cafd312556ec267b2b25214d255ff9352daed77a01b7852addbb48dc45",
      "as_of_date": "2026-08-13",
      "ba3_source_snapshot_ir_sha256": "bcd26cbd6c3774b8589e42c759dee2ae19010f4559c4bdd90519f17bcbbee5db",
      "ba4": {
        "discovered_table_count": 503,
        "legacy_table_bridge_count": 4,
        "parsed_document_count": 29
      },
      "ba5": {
        "normalized_record_count": 200,
        "normalized_records_sha256": "887bb1fe33840b809d3ff62f03c09e60ebbe1bea5b1abb2e252f6edf7bf35e05",
        "typed_fact_count": 200,
        "typed_facts_sha256": "5627bd446d49144303f491f375f7f3d61922ce6a9a55b0b0db16a72942a94ff6"
      },
      "ba6": {
        "formula_evaluation_count": 34,
        "formula_evaluations_sha256": "8c72223e3c9baa8cbcd1503db8ee2b8c3b6278a1472429c744278881fcc74f5d",
        "formula_marker_count": 7,
        "metric_count": 116,
        "metrics_sha256": "a801c7e06325f556378abeafc520e18c29b2d65ccf01f9916bf6796ad0b9f8b3"
      },
      "ba7": {
        "edge_count": 1626,
        "evidence_graph_sha256": "5509aa8577bc2d525031475c6ba78a785113295dfd1024b4b196e06335ce0387",
        "node_count": 1229,
        "orphan_fact_ids": []
      },
      "ba8": {
        "claim_graph_sha256": "c01e41af2957519b3b7bea8d0fde82b31a7145fea5f46a67a60fa362e678affd",
        "claims_without_definition": [],
        "claims_without_evidence": [],
        "edge_count": 344,
        "node_count": 313
      },
      "ba9": {
        "decision_graph_sha256": "47086b9a8c1364ee82c31ed16ad07210afda325441392f74c4a4400cd6093f4b",
        "edge_count": 61,
        "legacy_payload_sha256": "5ad7c37fdae6d64e4b2428fe294e59c1477d482e4da7391ce2de03505becd791",
        "node_count": 62,
        "permission_corridor_preserved": true,
        "rating_permission_preserved": true,
        "roundtrip_sha256": "5ad7c37fdae6d64e4b2428fe294e59c1477d482e4da7391ce2de03505becd791"
      },
      "coverage_gates": {
        "claim_instances_without_definition": 0,
        "claim_kind_alias_collisions": 0,
        "dimension_mismatches": 0,
        "lossy_formula_migrations": 0,
        "operand_role_mismatches": 0,
        "positional_metrics_promoted": 0,
        "semantic_metric_collisions": 0,
        "ticker_specific_metric_definitions": 0,
        "unknown_claim_kinds": 0,
        "unknown_executable_metric_ids": 0,
        "unknown_formula_ids": 0,
        "unregistered_decision_inputs": 0,
        "unregistered_decision_rules": 0,
        "used_claim_kinds_accounted_for": true,
        "used_formula_ids_accounted_for": true,
        "used_metric_ids_accounted_for": true
      },
      "gates": {
        "all_formula_evaluations_verified": true,
        "archive_unchanged": true,
        "authority_bundle_v3_unchanged": true,
        "ba10_not_started": true,
        "claim_definitions_complete": true,
        "claim_evidence_complete": true,
        "decision_roundtrip_lossless": true,
        "evidence_orphans_absent": true,
        "parsed_all_snapshot_artifacts": true,
        "source_snapshot_complete": true,
        "typed_all_legacy_facts": true
      },
      "pass_contracts_sha256": "f78cac545eeaa9d61407a61cb1f2ada09088b4e7028e5e620a45d4f374f0b1a0",
      "registry_authority_sha256": "55585f2242f32da4cc401455cd3186a97bf74f2c4a7feb5078e00d6a6e1ea5fb",
      "replay_sha256": "b11915e9e66f805415487fe3898fd08f6c3a2b3a8abb1c92379edeebd442999a",
      "ticker": "ABT"
    },
    "second_replay_sha256": "b11915e9e66f805415487fe3898fd08f6c3a2b3a8abb1c92379edeebd442999a"
  },
  "COST": {
    "canary_unchanged": true,
    "double_replay_equal": true,
    "first": {
      "archive": "ROOM16_COST_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448.zip",
      "archive_sha256_after": "b97e6024855c7a772713ff9af4889987e4a9a8e5a3afca0d56a42a1ba8092ea4",
      "archive_sha256_before": "b97e6024855c7a772713ff9af4889987e4a9a8e5a3afca0d56a42a1ba8092ea4",
      "as_of_date": "2026-08-13",
      "ba3_source_snapshot_ir_sha256": "fe827655f9f05d409f687f5f57d052d619ad2d184cc74330e722a498f907cd60",
      "ba4": {
        "discovered_table_count": 492,
        "legacy_table_bridge_count": 2,
        "parsed_document_count": 23
      },
      "ba5": {
        "normalized_record_count": 177,
        "normalized_records_sha256": "cfe59f4155619da2c971f113d2086f7af1dfb859e2bd2fe1b85a603457fd654e",
        "typed_fact_count": 177,
        "typed_facts_sha256": "7e1fdb3136643bea6eb318431fd85f844fbbbd117dfbbd4ab81905ba2612a31e"
      },
      "ba6": {
        "formula_evaluation_count": 33,
        "formula_evaluations_sha256": "a4f841d98f278b93813686359aed074fa7676e2278d3ca8ee985e47cbb0b0eed",
        "formula_marker_count": 7,
        "metric_count": 95,
        "metrics_sha256": "f74222baedb85cf5f82c4eef0159f375d1fe4814cc7e6c2debfafb9e2c3c0ef9"
      },
      "ba7": {
        "edge_count": 1517,
        "evidence_graph_sha256": "09b8b24ed59a2b897cd6d0a080daeb51d6f97e072b71b61c7e1279042a7a0d2f",
        "node_count": 1136,
        "orphan_fact_ids": []
      },
      "ba8": {
        "claim_graph_sha256": "3365245213ce433f5a9cf933674aff52f5bc9433ebf6434a33143bd98c4344e6",
        "claims_without_definition": [],
        "claims_without_evidence": [],
        "edge_count": 293,
        "node_count": 249
      },
      "ba9": {
        "decision_graph_sha256": "d6424e057bcb3674867d0a530b5ca5304fe27f9c28af12df090124d488867d8e",
        "edge_count": 48,
        "legacy_payload_sha256": "b3103e364214ecd197cd52d7b0266f6166c97af07686749236fd2280280d5744",
        "node_count": 49,
        "permission_corridor_preserved": true,
        "rating_permission_preserved": true,
        "roundtrip_sha256": "b3103e364214ecd197cd52d7b0266f6166c97af07686749236fd2280280d5744"
      },
      "coverage_gates": {
        "claim_instances_without_definition": 0,
        "claim_kind_alias_collisions": 0,
        "dimension_mismatches": 0,
        "lossy_formula_migrations": 0,
        "operand_role_mismatches": 0,
        "positional_metrics_promoted": 0,
        "semantic_metric_collisions": 0,
        "ticker_specific_metric_definitions": 0,
        "unknown_claim_kinds": 0,
        "unknown_executable_metric_ids": 0,
        "unknown_formula_ids": 0,
        "unregistered_decision_inputs": 0,
        "unregistered_decision_rules": 0,
        "used_claim_kinds_accounted_for": true,
        "used_formula_ids_accounted_for": true,
        "used_metric_ids_accounted_for": true
      },
      "gates": {
        "all_formula_evaluations_verified": true,
        "archive_unchanged": true,
        "authority_bundle_v3_unchanged": true,
        "ba10_not_started": true,
        "claim_definitions_complete": true,
        "claim_evidence_complete": true,
        "decision_roundtrip_lossless": true,
        "evidence_orphans_absent": true,
        "parsed_all_snapshot_artifacts": true,
        "source_snapshot_complete": true,
        "typed_all_legacy_facts": true
      },
      "pass_contracts_sha256": "f78cac545eeaa9d61407a61cb1f2ada09088b4e7028e5e620a45d4f374f0b1a0",
      "registry_authority_sha256": "55585f2242f32da4cc401455cd3186a97bf74f2c4a7feb5078e00d6a6e1ea5fb",
      "replay_sha256": "07d9420b34bfc257b656e771dc8ad932cdbcd30d3144f153022babae46b22ba0",
      "ticker": "COST"
    },
    "second_replay_sha256": "07d9420b34bfc257b656e771dc8ad932cdbcd30d3144f153022babae46b22ba0"
  },
  "WM": {
    "canary_unchanged": true,
    "double_replay_equal": true,
    "first": {
      "archive": "ROOM16_WM_CROSS_COMPANY_RC_8cf064d75c8c-20260814-115448.zip",
      "archive_sha256_after": "a6b6d15ad7004573a56ad057884563cfbeeb2c3162dae0641a1b361b5e416d72",
      "archive_sha256_before": "a6b6d15ad7004573a56ad057884563cfbeeb2c3162dae0641a1b361b5e416d72",
      "as_of_date": "2026-08-11",
      "ba3_source_snapshot_ir_sha256": "48ecc6a5ae27e576d8fb97943132d56df84c5618edf3d90174843ecbc849c459",
      "ba4": {
        "discovered_table_count": 673,
        "legacy_table_bridge_count": 4,
        "parsed_document_count": 27
      },
      "ba5": {
        "normalized_record_count": 256,
        "normalized_records_sha256": "84d6aa113bc8a698bd55677cff190c8ddfa93cca1ddec7eb08e7a51b0a012f83",
        "typed_fact_count": 256,
        "typed_facts_sha256": "36cf1b48d9ed72b6f94e7b691dde76c17f150421557ee6fa07d51f17f9cee5bf"
      },
      "ba6": {
        "formula_evaluation_count": 35,
        "formula_evaluations_sha256": "67b596d1933fc2d0c5654c025020c5960f436d9250aea8363681e89205a2c5c0",
        "formula_marker_count": 7,
        "metric_count": 171,
        "metrics_sha256": "1d1e899c991d4534a1a9a631ac6a4ffafec126adbe94fee8b0a7e70da6cab78e"
      },
      "ba7": {
        "edge_count": 1559,
        "evidence_graph_sha256": "1e32706363de710f11f26540923339b1d0e1ab57c82728041785e96082f813c1",
        "node_count": 1236,
        "orphan_fact_ids": []
      },
      "ba8": {
        "claim_graph_sha256": "204c076e60ebda76e2556fb6eef78d7024181ab8a5c784469261022bd6278f59",
        "claims_without_definition": [],
        "claims_without_evidence": [],
        "edge_count": 417,
        "node_count": 385
      },
      "ba9": {
        "decision_graph_sha256": "afe2ddc660ad1d2df18ea5baa961e3b7eb29a4d95df11e6c2efb25fa76363d0c",
        "edge_count": 73,
        "legacy_payload_sha256": "459ef4395babcb4c86179dc084d82a1d32df1ff7d4c9288a4236d26e33c4ceed",
        "node_count": 74,
        "permission_corridor_preserved": true,
        "rating_permission_preserved": true,
        "roundtrip_sha256": "459ef4395babcb4c86179dc084d82a1d32df1ff7d4c9288a4236d26e33c4ceed"
      },
      "coverage_gates": {
        "claim_instances_without_definition": 0,
        "claim_kind_alias_collisions": 0,
        "dimension_mismatches": 0,
        "lossy_formula_migrations": 0,
        "operand_role_mismatches": 0,
        "positional_metrics_promoted": 0,
        "semantic_metric_collisions": 0,
        "ticker_specific_metric_definitions": 0,
        "unknown_claim_kinds": 0,
        "unknown_executable_metric_ids": 0,
        "unknown_formula_ids": 0,
        "unregistered_decision_inputs": 0,
        "unregistered_decision_rules": 0,
        "used_claim_kinds_accounted_for": true,
        "used_formula_ids_accounted_for": true,
        "used_metric_ids_accounted_for": true
      },
      "gates": {
        "all_formula_evaluations_verified": true,
        "archive_unchanged": true,
        "authority_bundle_v3_unchanged": true,
        "ba10_not_started": true,
        "claim_definitions_complete": true,
        "claim_evidence_complete": true,
        "decision_roundtrip_lossless": true,
        "evidence_orphans_absent": true,
        "parsed_all_snapshot_artifacts": true,
        "source_snapshot_complete": true,
        "typed_all_legacy_facts": true
      },
      "pass_contracts_sha256": "f78cac545eeaa9d61407a61cb1f2ada09088b4e7028e5e620a45d4f374f0b1a0",
      "registry_authority_sha256": "55585f2242f32da4cc401455cd3186a97bf74f2c4a7feb5078e00d6a6e1ea5fb",
      "replay_sha256": "1c5d74819831e3e0fb9b743dff99d081dbe45a4ce016af60be75eabbba7f278a",
      "ticker": "WM"
    },
    "second_replay_sha256": "1c5d74819831e3e0fb9b743dff99d081dbe45a4ce016af60be75eabbba7f278a"
  }
}
```

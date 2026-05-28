from research_agent.publishing import (
    scan_publication_policy,
    validate_artifact_state,
    validate_outcome_readiness,
    validate_publishable_source_registry,
)
from research_agent.research_core.ingestion.source_registry import SourceRegistry, SourceRegistryEntry


def test_internal_review_blocks_public_visibility_leak():
    result = validate_artifact_state(
        {
            "publication_state": "internal_review",
            "ticker": "TEST",
            "public_member_status": "blocked",
            "public_ready": True,
        }
    )

    assert result.status == "blocked"
    assert result.block_count == 1
    assert result.findings[0].code == "INTERNAL_ARTIFACT_VISIBILITY_LEAK"


def test_research_seed_stays_internal_when_explicitly_blocked():
    result = validate_artifact_state(
        {
            "decision": "reject_public_packet_keep_internal_seed",
            "public_member_status": "blocked",
            "allowed_use": "internal research seed",
        }
    )

    assert result.status == "pass"
    assert result.state == "research_seed"


def test_policy_gate_blocks_rating_and_transaction_language():
    result = scan_publication_policy(
        "Final rating: Buy\nInvestors should start a position now.",
        artifact_state="public_brief",
    )

    assert result.status == "blocked"
    assert {finding.code for finding in result.findings} >= {"RATING_LANGUAGE", "TRANSACTION_LANGUAGE"}


def test_policy_gate_ignores_negated_no_advice_language():
    result = scan_publication_policy(
        "Keine Kauf- oder Verkaufsempfehlung. This is non-advice research context.",
        artifact_state="public_brief",
    )

    assert result.status == "pass"


def test_source_registry_gate_requires_claim_mapping_and_primary_source():
    registry = SourceRegistry(
        registry_id="TEST",
        sources=[
            SourceRegistryEntry(
                source_id="vendor_price",
                ticker="TEST",
                source_type="yahoo_finance",
                used_for=["price"],
                retrieved_at="2026-05-28T00:00:00Z",
            )
        ],
    )

    result = validate_publishable_source_registry(
        registry,
        required_claims=["revenue"],
        as_of_date="2026-05-28",
        require_owner=False,
    )

    assert result.status == "blocked"
    assert {finding.code for finding in result.findings} >= {
        "MISSING_SOURCE_FOR_CLAIM",
        "MISSING_PRIMARY_SOURCE_FOR_HARD_CLAIM",
    }


def test_outcome_readiness_allows_pending_price_data_stop():
    result = validate_outcome_readiness(
        {
            "status": "pending_price_data",
            "earliest_evaluation_date": "2026-06-01",
            "policy": {
                "no_synthetic_prices": True,
                "no_forward_fill": True,
                "no_replacement_end_date": True,
            },
            "coverage": {
                "missing_price_tickers": ["AAPL"],
                "missing_benchmark_tickers": ["SPY"],
            },
        }
    )

    assert result.status == "pass"


def test_outcome_readiness_blocks_ready_state_with_missing_prices():
    result = validate_outcome_readiness(
        {
            "status": "ready_to_compute",
            "earliest_evaluation_date": "2026-06-01",
            "policy": {
                "no_synthetic_prices": True,
                "no_forward_fill": True,
                "no_replacement_end_date": True,
            },
            "coverage": {
                "missing_price_tickers": ["AAPL"],
                "missing_benchmark_tickers": [],
            },
        }
    )

    assert result.status == "blocked"
    assert result.findings[0].code == "OUTCOME_READY_WITH_MISSING_PRICES"

from __future__ import annotations

import pytest

from research_agent.alpha_shared.issuer_identity import (
    IssuerAliasEvidence,
    resolve_issuer_identity,
)


DIRECTORY = {
    "147": {"cik_str": 1390777, "ticker": "BNY", "title": "Bank of New York Mellon Corp"},
    "999": {"cik_str": 999, "ticker": "OTHER", "title": "Other Corp"},
}
SOURCE = "a" * 64


def _bk_alias(cik: str = "0001390777") -> IssuerAliasEvidence:
    return IssuerAliasEvidence("BK", "BNY", cik, "2024-06-12", SOURCE)


def test_bk_lifecycle_preserves_requested_and_effective_ticker() -> None:
    identity = resolve_issuer_identity(
        requested_ticker="BK",
        canonical_company_name="The Bank of New York Mellon Corporation",
        as_of_date="2026-08-30",
        current_directory=DIRECTORY,
        source_receipt_sha256=SOURCE,
        pinned_cik="0001390777",
        alias_history=(_bk_alias(),),
    )
    assert identity["requested_ticker"] == "BK"
    assert identity["effective_ticker"] == "BNY"
    assert identity["cik"] == "0001390777"
    assert identity["resolution_method"] == "trusted_historical_ticker_alias_same_cik"


def test_alias_to_different_cik_blocks() -> None:
    with pytest.raises(RuntimeError, match="PINNED_CIK_MISMATCH"):
        resolve_issuer_identity(
            requested_ticker="BK", canonical_company_name="The Bank of New York Mellon Corporation",
            as_of_date="2026-08-30", current_directory=DIRECTORY,
            source_receipt_sha256=SOURCE, pinned_cik="0001390777",
            alias_history=(_bk_alias("0000000999"),),
        )


def test_fuzzy_name_alone_never_resolves() -> None:
    with pytest.raises(RuntimeError, match="ALIAS_NOT_UNIQUE"):
        resolve_issuer_identity(
            requested_ticker="BK", canonical_company_name="Bank New York Mellon",
            as_of_date="2026-08-30", current_directory=DIRECTORY,
            source_receipt_sha256=SOURCE, pinned_cik="0001390777",
        )


def test_current_exact_ticker_remains_supported() -> None:
    identity = resolve_issuer_identity(
        requested_ticker="BNY", canonical_company_name="Bank of New York Mellon Corp",
        as_of_date="2026-08-30", current_directory=DIRECTORY,
        source_receipt_sha256=SOURCE, pinned_cik="1390777",
    )
    assert identity["requested_ticker"] == identity["effective_ticker"] == "BNY"


@pytest.mark.parametrize(
    ("canonical_name", "sec_name", "ticker", "cik"),
    (
        ("Valero Energy Corporation", "VALERO ENERGY CORP/TX", "VLO", "0001035002"),
        ("Example Holdings Corporation", "EXAMPLE HOLDINGS CORP/DE", "EX", "0000000042"),
    ),
)
def test_terminal_recognized_sec_jurisdiction_suffix_is_equivalent(
    canonical_name: str, sec_name: str, ticker: str, cik: str
) -> None:
    identity = resolve_issuer_identity(
        requested_ticker=ticker,
        canonical_company_name=canonical_name,
        as_of_date="2026-08-31",
        current_directory={"0": {"cik_str": cik, "ticker": ticker, "title": sec_name}},
        source_receipt_sha256=SOURCE,
        pinned_cik=cik,
    )
    assert identity["requested_ticker"] == identity["effective_ticker"] == ticker
    assert identity["cik"] == cik


@pytest.mark.parametrize(
    ("sec_name", "canonical_name"),
    (
        ("ACME/TECH CORP", "ACME TECH CORP"),
        ("ACME CORP/XYZ", "ACME CORP"),
        ("ACME CORP/TEXAS", "ACME CORP"),
        ("ACME / TX HOLDINGS", "ACME HOLDINGS"),
    ),
)
def test_unsupported_or_nonterminal_slash_is_not_stripped(
    sec_name: str, canonical_name: str
) -> None:
    with pytest.raises(RuntimeError, match="ISSUER_IDENTITY_CANONICAL_NAME_MISMATCH"):
        resolve_issuer_identity(
            requested_ticker="ACME",
            canonical_company_name=canonical_name,
            as_of_date="2026-08-31",
            current_directory={
                "0": {"cik_str": "0000000042", "ticker": "ACME", "title": sec_name}
            },
            source_receipt_sha256=SOURCE,
            pinned_cik="0000000042",
        )


def test_terminal_jurisdiction_normalization_does_not_weaken_cik_binding() -> None:
    with pytest.raises(RuntimeError, match="ISSUER_IDENTITY_PINNED_CIK_MISMATCH"):
        resolve_issuer_identity(
            requested_ticker="VLO",
            canonical_company_name="Valero Energy Corporation",
            as_of_date="2026-08-31",
            current_directory={
                "0": {
                    "cik_str": "0000000042",
                    "ticker": "VLO",
                    "title": "VALERO ENERGY CORP/TX",
                }
            },
            source_receipt_sha256=SOURCE,
            pinned_cik="0001035002",
        )

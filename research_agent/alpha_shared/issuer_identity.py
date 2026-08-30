"""Deterministic issuer identity lifecycle resolution.

Trading symbols are aliases.  The stable identity is the issuer CIK and a
trusted alias transition may only route within that same issuer.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha256_json(value: object) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _ticker(value: object) -> str:
    return str(value or "").strip().upper()


def _cik(value: object) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if not digits:
        raise RuntimeError("ISSUER_IDENTITY_CIK_MISSING")
    return digits.zfill(10)


def _legal_name(value: object) -> str:
    text = str(value or "").casefold().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    if text.startswith("the "):
        text = text[4:]
    replacements = {
        " corporation": " corp",
        " incorporated": " inc",
        " company": " co",
    }
    for old, new in replacements.items():
        if text.endswith(old):
            text = text[: -len(old)] + new
    return text


@dataclass(frozen=True)
class IssuerAliasEvidence:
    requested_ticker: str
    effective_ticker: str
    cik: str
    valid_from: str
    source_receipt_sha256: str
    valid_to: str | None = None

    def normalized(self) -> "IssuerAliasEvidence":
        return IssuerAliasEvidence(
            requested_ticker=_ticker(self.requested_ticker),
            effective_ticker=_ticker(self.effective_ticker),
            cik=_cik(self.cik),
            valid_from=self.valid_from,
            valid_to=self.valid_to,
            source_receipt_sha256=self.source_receipt_sha256,
        )


def resolve_issuer_identity(
    *,
    requested_ticker: str,
    canonical_company_name: str,
    as_of_date: str,
    current_directory: Mapping[str, Mapping[str, Any]] | Iterable[Mapping[str, Any]],
    source_receipt_sha256: str,
    pinned_cik: str | None = None,
    alias_history: Iterable[IssuerAliasEvidence] = (),
) -> dict[str, Any]:
    """Resolve an issuer without fuzzy names or cross-CIK ticker substitution."""

    requested = _ticker(requested_ticker)
    rows = list(current_directory.values()) if isinstance(current_directory, Mapping) else list(current_directory)
    exact = [row for row in rows if _ticker(row.get("ticker")) == requested]
    aliases = tuple(item.normalized() for item in alias_history)
    pinned = _cik(pinned_cik) if pinned_cik is not None else None

    method: str
    match: Mapping[str, Any]
    if len(exact) == 1:
        match = exact[0]
        method = "exact_current_ticker"
        if pinned is not None and _cik(match.get("cik_str")) != pinned:
            raise RuntimeError("ISSUER_IDENTITY_PINNED_CIK_MISMATCH")
    elif len(exact) > 1:
        raise RuntimeError(f"ISSUER_IDENTITY_CURRENT_TICKER_AMBIGUOUS:{requested}:{len(exact)}")
    else:
        eligible = [
            item
            for item in aliases
            if item.requested_ticker == requested
            and item.valid_from <= as_of_date
            and (item.valid_to is None or as_of_date <= item.valid_to)
        ]
        if len(eligible) != 1:
            raise RuntimeError(f"ISSUER_IDENTITY_ALIAS_NOT_UNIQUE:{requested}:{len(eligible)}")
        alias = eligible[0]
        if pinned is not None and alias.cik != pinned:
            raise RuntimeError("ISSUER_IDENTITY_ALIAS_PINNED_CIK_MISMATCH")
        same_cik = [row for row in rows if _cik(row.get("cik_str")) == alias.cik]
        effective = [row for row in same_cik if _ticker(row.get("ticker")) == alias.effective_ticker]
        if len(effective) != 1:
            raise RuntimeError(
                f"ISSUER_IDENTITY_EFFECTIVE_TICKER_NOT_UNIQUE:{alias.effective_ticker}:{len(effective)}"
            )
        match = effective[0]
        method = "trusted_historical_ticker_alias_same_cik"

    resolved_cik = _cik(match.get("cik_str"))
    if pinned is not None and resolved_cik != pinned:
        raise RuntimeError("ISSUER_IDENTITY_CIK_CONTINUITY_FAILED")
    if _legal_name(match.get("title")) != _legal_name(canonical_company_name):
        raise RuntimeError("ISSUER_IDENTITY_CANONICAL_NAME_MISMATCH")

    history = [asdict(item) for item in aliases]
    body = {
        "contract_id": "room16.issuer_identity_ir",
        "contract_version": 1,
        "logical_company_id": f"sec-cik-{resolved_cik}",
        "canonical_company_name": canonical_company_name,
        "cik": resolved_cik,
        "requested_ticker": requested,
        "effective_ticker": _ticker(match.get("ticker")),
        "ticker_alias_history": history,
        "as_of_date": as_of_date,
        "source_receipt_sha256": source_receipt_sha256,
        "resolution_method": method,
    }
    return {**body, "identity_sha256": _sha256_json(body)}


"""External, hash-bound authorization for RFC-0011 live case execution."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import Field, model_validator

from research_agent.compiler_foundation.canonical import sha256_json
from research_agent.compiler_foundation.contracts import StrictModel

SHA256 = r"^[0-9a-f]{64}$"
GIT_COMMIT = r"^[0-9a-f]{40}$"
ArchetypeProfileId = Literal["saas", "reit", "bank", "energy"]
AuthorityKind = Literal["DEVELOPMENT_VALIDATION", "FIXED_BATCH"]

_ARCHETYPE_PROFILE_IDS = {
    "Software/SaaS": "saas",
    "REIT": "reit",
    "Bank": "bank",
    "Integrated Energy": "energy",
}


class ExecutionAuthorityError(RuntimeError):
    """Fail-closed execution-authority error with a stable code."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


class RuntimeIdentityIR(StrictModel):
    """Exact checked-out runtime identity evaluated before provider access."""

    research_commit: str = Field(pattern=GIT_COMMIT)
    research_tree: str = Field(pattern=GIT_COMMIT)
    product_commit: str = Field(pattern=GIT_COMMIT)
    product_tree: str = Field(pattern=GIT_COMMIT)
    as_of_date: str

    @model_validator(mode="after")
    def validate_date(self) -> "RuntimeIdentityIR":
        date.fromisoformat(self.as_of_date)
        return self


class BatchExecutionCaseIR(StrictModel):
    """One ordered externally authorized case, never an internal allowlist."""

    sequence: int = Field(ge=1)
    ticker: str = Field(pattern=r"^[A-Z][A-Z0-9.-]{0,9}$")
    company_name: str = Field(min_length=1)
    archetype_profile_id: ArchetypeProfileId


class SharedFreezeBindingIR(StrictModel):
    """Verified Shared Freeze identity required for live fixed-batch access."""

    contract_id: Literal["room16.shared_freeze_execution_binding"] = (
        "room16.shared_freeze_execution_binding"
    )
    contract_version: Literal[1] = 1
    freeze_sha256: str = Field(pattern=SHA256)
    fixed_company_list_sha256: str = Field(pattern=SHA256)
    threshold_sha256: str = Field(pattern=SHA256)
    research_commit: str = Field(pattern=GIT_COMMIT)
    research_tree: str = Field(pattern=GIT_COMMIT)
    product_commit: str = Field(pattern=GIT_COMMIT)
    product_tree: str = Field(pattern=GIT_COMMIT)
    verified: Literal[True] = True
    binding_sha256: str = Field(pattern=SHA256)

    @classmethod
    def create(cls, **values: object) -> "SharedFreezeBindingIR":
        body = {
            "contract_id": "room16.shared_freeze_execution_binding",
            "contract_version": 1,
            "verified": True,
            **values,
        }
        return cls(**body, binding_sha256=sha256_json(body))

    @model_validator(mode="after")
    def verify_selfhash(self) -> "SharedFreezeBindingIR":
        body = self.model_dump(mode="json", exclude={"binding_sha256"})
        if sha256_json(body) != self.binding_sha256:
            raise ValueError("shared freeze binding self-hash mismatch")
        return self


class BatchExecutionAuthorityIR(StrictModel):
    """Immutable external execution-control contract; it carries no semantics."""

    contract_id: Literal["room16.batch_execution_authority"] = (
        "room16.batch_execution_authority"
    )
    contract_version: Literal[1] = 1
    authority_kind: AuthorityKind
    as_of_date: str
    research_commit: str = Field(pattern=GIT_COMMIT)
    research_tree: str = Field(pattern=GIT_COMMIT)
    product_commit: str = Field(pattern=GIT_COMMIT)
    product_tree: str = Field(pattern=GIT_COMMIT)
    shared_freeze_sha256: str | None = Field(default=None, pattern=SHA256)
    fixed_company_list_sha256: str | None = Field(default=None, pattern=SHA256)
    threshold_sha256: str | None = Field(default=None, pattern=SHA256)
    ordered_cases: tuple[BatchExecutionCaseIR, ...]
    network_live_authorized: bool
    semantic_changes_authorized: Literal[False] = False
    company_replacement_authorized: Literal[False] = False
    ticker_specific_rules_authorized: Literal[False] = False
    authority_sha256: str = Field(pattern=SHA256)

    @classmethod
    def create(cls, **values: object) -> "BatchExecutionAuthorityIR":
        body = {
            "contract_id": "room16.batch_execution_authority",
            "contract_version": 1,
            "semantic_changes_authorized": False,
            "company_replacement_authorized": False,
            "ticker_specific_rules_authorized": False,
            **values,
        }
        return cls(**body, authority_sha256=sha256_json(body))

    @model_validator(mode="after")
    def verify_contract(self) -> "BatchExecutionAuthorityIR":
        date.fromisoformat(self.as_of_date)
        body = self.model_dump(mode="json", exclude={"authority_sha256"})
        if sha256_json(body) != self.authority_sha256:
            raise ValueError("execution authority self-hash mismatch")
        sequences = tuple(item.sequence for item in self.ordered_cases)
        if sequences != tuple(range(1, len(self.ordered_cases) + 1)):
            raise ValueError("execution authority cases must be contiguous and ordered")
        tickers = tuple(item.ticker for item in self.ordered_cases)
        if len(set(tickers)) != len(tickers):
            raise ValueError("execution authority tickers must be unique")
        if self.authority_kind == "FIXED_BATCH":
            if self.fixed_company_list_sha256 is None or self.threshold_sha256 is None:
                raise ValueError("fixed-batch authority requires list and threshold hashes")
            if self.network_live_authorized and self.shared_freeze_sha256 is None:
                raise ValueError("live fixed-batch authority requires a Shared Freeze hash")
        elif any(
            value is not None
            for value in (
                self.shared_freeze_sha256,
                self.fixed_company_list_sha256,
                self.threshold_sha256,
            )
        ):
            raise ValueError("Development authority cannot impersonate fixed-batch bindings")
        return self


class AuthorizationReceiptIR(StrictModel):
    """Pre-network authorization result consumed by the canonical runner."""

    contract_id: Literal["room16.batch_execution_authorization_receipt"] = (
        "room16.batch_execution_authorization_receipt"
    )
    contract_version: Literal[1] = 1
    authority_sha256: str = Field(pattern=SHA256)
    authority_kind: AuthorityKind
    sequence: int = Field(ge=1)
    ticker: str = Field(pattern=r"^[A-Z][A-Z0-9.-]{0,9}$")
    archetype_profile_id: ArchetypeProfileId
    as_of_date: str
    research_commit: str = Field(pattern=GIT_COMMIT)
    research_tree: str = Field(pattern=GIT_COMMIT)
    product_commit: str = Field(pattern=GIT_COMMIT)
    product_tree: str = Field(pattern=GIT_COMMIT)
    authorization_mode: Literal["PREFLIGHT_ONLY", "LIVE_AUTHORIZED"]
    network_live_authorized: bool
    authorization_preflight_count: Literal[1] = 1
    case_attempt_count: Literal[0] = 0
    live_network_query_count: Literal[0] = 0
    completed_case_count: Literal[0] = 0
    status: Literal["PASS"] = "PASS"
    receipt_sha256: str = Field(pattern=SHA256)

    @classmethod
    def create(cls, **values: object) -> "AuthorizationReceiptIR":
        body = {
            "contract_id": "room16.batch_execution_authorization_receipt",
            "contract_version": 1,
            "authorization_preflight_count": 1,
            "case_attempt_count": 0,
            "live_network_query_count": 0,
            "completed_case_count": 0,
            "status": "PASS",
            **values,
        }
        return cls(**body, receipt_sha256=sha256_json(body))

    @model_validator(mode="after")
    def verify_selfhash(self) -> "AuthorizationReceiptIR":
        body = self.model_dump(mode="json", exclude={"receipt_sha256"})
        if sha256_json(body) != self.receipt_sha256:
            raise ValueError("authorization receipt self-hash mismatch")
        if self.network_live_authorized != (self.authorization_mode == "LIVE_AUTHORIZED"):
            raise ValueError("authorization receipt mode/live flag mismatch")
        return self


def fixed_company_list_sha256(document: dict[str, Any]) -> str:
    companies = document.get("companies")
    if not isinstance(companies, list) or not companies:
        raise ExecutionAuthorityError(
            "EXEC_AUTH_FIXED_LIST_INVALID", "companies must be a non-empty list"
        )
    return sha256_json(companies)


def threshold_authority_sha256(document: dict[str, Any]) -> str:
    if document.get("contract_id") != "room16.alpha.fixed_24_batch_acceptance_thresholds@1":
        raise ExecutionAuthorityError(
            "EXEC_AUTH_THRESHOLD_INVALID", "threshold contract identity mismatch"
        )
    return sha256_json(document)


def _authority_integrity(authority: BatchExecutionAuthorityIR) -> None:
    body = authority.model_dump(mode="json", exclude={"authority_sha256"})
    if sha256_json(body) != authority.authority_sha256:
        raise ExecutionAuthorityError(
            "EXEC_AUTH_SELFHASH_MISMATCH", "authority self-hash does not match"
        )
    if any(
        (
            authority.semantic_changes_authorized,
            authority.company_replacement_authorized,
            authority.ticker_specific_rules_authorized,
        )
    ):
        raise ExecutionAuthorityError(
            "EXEC_AUTH_FORBIDDEN_CAPABILITY", "authority requests forbidden semantics"
        )


def _runtime_matches(
    authority: BatchExecutionAuthorityIR, runtime_identity: RuntimeIdentityIR
) -> bool:
    return all(
        (
            authority.research_commit == runtime_identity.research_commit,
            authority.research_tree == runtime_identity.research_tree,
            authority.product_commit == runtime_identity.product_commit,
            authority.product_tree == runtime_identity.product_tree,
            authority.as_of_date == runtime_identity.as_of_date,
        )
    )


def _project_fixed_cases(document: dict[str, Any]) -> tuple[dict[str, object], ...]:
    projected = []
    for raw in document.get("companies", []):
        try:
            projected.append(
                {
                    "sequence": raw["sequence"],
                    "ticker": raw["ticker"],
                    "company_name": raw["company_name"],
                    "archetype_profile_id": _ARCHETYPE_PROFILE_IDS[raw["archetype"]],
                }
            )
        except (KeyError, TypeError) as exc:
            raise ExecutionAuthorityError(
                "EXEC_AUTH_FIXED_LIST_INVALID", "fixed list case projection failed"
            ) from exc
    return tuple(projected)


def ordered_cases_from_fixed_company_list(
    document: dict[str, Any],
) -> tuple[BatchExecutionCaseIR, ...]:
    """Project the external frozen company document into execution-only cases."""

    return tuple(BatchExecutionCaseIR(**item) for item in _project_fixed_cases(document))


def authorize_case_before_network(
    *,
    ticker: str,
    archetype_profile_id: str,
    sequence: int,
    authority: BatchExecutionAuthorityIR,
    runtime_identity: RuntimeIdentityIR,
    shared_freeze: SharedFreezeBindingIR | None = None,
    fixed_company_list: dict[str, Any] | None = None,
    threshold_authority: dict[str, Any] | None = None,
) -> AuthorizationReceiptIR:
    """Authorize one case without contacting or incrementing any provider."""

    _authority_integrity(authority)
    if not _runtime_matches(authority, runtime_identity):
        raise ExecutionAuthorityError(
            "EXEC_AUTH_RUNTIME_MISMATCH", "checked-out runtime is not authority-bound"
        )
    matches = [
        item
        for item in authority.ordered_cases
        if item.ticker == ticker and item.sequence == sequence
    ]
    if not matches:
        raise ExecutionAuthorityError(
            "EXEC_AUTH_CASE_NOT_ORDERED", "ticker/sequence is absent from authority"
        )
    case = matches[0]
    if case.archetype_profile_id != archetype_profile_id:
        raise ExecutionAuthorityError(
            "EXEC_AUTH_PROFILE_MISMATCH", "archetype profile is not authority-bound"
        )

    if authority.authority_kind == "FIXED_BATCH":
        if fixed_company_list is None or threshold_authority is None:
            raise ExecutionAuthorityError(
                "EXEC_AUTH_FIXED_DOCUMENTS_MISSING", "fixed list/threshold documents required"
            )
        if fixed_company_list_sha256(fixed_company_list) != authority.fixed_company_list_sha256:
            raise ExecutionAuthorityError(
                "EXEC_AUTH_FIXED_LIST_HASH_MISMATCH", "fixed list hash mismatch"
            )
        if threshold_authority_sha256(threshold_authority) != authority.threshold_sha256:
            raise ExecutionAuthorityError(
                "EXEC_AUTH_THRESHOLD_HASH_MISMATCH", "threshold hash mismatch"
            )
        expected_cases = tuple(item.model_dump(mode="json") for item in authority.ordered_cases)
        if _project_fixed_cases(fixed_company_list) != expected_cases:
            raise ExecutionAuthorityError(
                "EXEC_AUTH_ORDERED_CASES_MISMATCH", "authority cases differ from frozen list"
            )
        if authority.network_live_authorized:
            if shared_freeze is None:
                raise ExecutionAuthorityError(
                    "EXEC_AUTH_SHARED_FREEZE_MISSING", "live fixed batch requires Shared Freeze"
                )
            freeze_body = shared_freeze.model_dump(mode="json", exclude={"binding_sha256"})
            if sha256_json(freeze_body) != shared_freeze.binding_sha256:
                raise ExecutionAuthorityError(
                    "EXEC_AUTH_SHARED_FREEZE_SELFHASH_MISMATCH",
                    "Shared Freeze binding self-hash mismatch",
                )
            binding = shared_freeze.model_dump(mode="json")
            expected_binding = {
                "freeze_sha256": authority.shared_freeze_sha256,
                "fixed_company_list_sha256": authority.fixed_company_list_sha256,
                "threshold_sha256": authority.threshold_sha256,
                "research_commit": authority.research_commit,
                "research_tree": authority.research_tree,
                "product_commit": authority.product_commit,
                "product_tree": authority.product_tree,
            }
            if any(binding[key] != value for key, value in expected_binding.items()):
                raise ExecutionAuthorityError(
                    "EXEC_AUTH_SHARED_FREEZE_MISMATCH", "Shared Freeze binding mismatch"
                )

    live = authority.network_live_authorized
    return AuthorizationReceiptIR.create(
        authority_sha256=authority.authority_sha256,
        authority_kind=authority.authority_kind,
        sequence=case.sequence,
        ticker=case.ticker,
        archetype_profile_id=case.archetype_profile_id,
        as_of_date=authority.as_of_date,
        research_commit=authority.research_commit,
        research_tree=authority.research_tree,
        product_commit=authority.product_commit,
        product_tree=authority.product_tree,
        authorization_mode="LIVE_AUTHORIZED" if live else "PREFLIGHT_ONLY",
        network_live_authorized=live,
    )


def verify_receipt_for_live_case(
    *,
    receipt: AuthorizationReceiptIR | None,
    ticker: str,
    archetype_profile_id: str,
    as_of_date: str,
    research_commit: str,
    research_tree: str,
) -> AuthorizationReceiptIR:
    """Fail before provider accounting unless a live receipt matches the case."""

    if receipt is None:
        raise ExecutionAuthorityError(
            "EXEC_AUTH_RECEIPT_REQUIRED", "verified live capture requires a receipt"
        )
    body = receipt.model_dump(mode="json", exclude={"receipt_sha256"})
    if sha256_json(body) != receipt.receipt_sha256:
        raise ExecutionAuthorityError(
            "EXEC_AUTH_RECEIPT_SELFHASH_MISMATCH", "receipt self-hash mismatch"
        )
    if not receipt.network_live_authorized or receipt.authorization_mode != "LIVE_AUTHORIZED":
        raise ExecutionAuthorityError(
            "EXEC_AUTH_LIVE_NOT_AUTHORIZED", "preflight-only receipt cannot reach providers"
        )
    if (
        receipt.ticker != ticker
        or receipt.archetype_profile_id != archetype_profile_id
        or receipt.as_of_date != as_of_date
        or receipt.research_commit != research_commit
        or receipt.research_tree != research_tree
    ):
        raise ExecutionAuthorityError(
            "EXEC_AUTH_RECEIPT_CASE_MISMATCH", "receipt does not bind this runner call"
        )
    return receipt

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence

from research_agent.research_core.ingestion.source_registry import SourceRegistry


PRIMARY_SOURCE_TYPES = {
    "company_ir",
    "sec_filing",
    "earnings_release",
    "official_press_release",
}

HARD_FINANCIAL_CLAIMS = {
    "revenue",
    "operating_income",
    "operating_margin",
    "free_cash_flow",
    "fcf",
    "operating_cash_flow",
    "capex",
    "eps",
    "cash",
    "debt",
    "sbc",
}


@dataclass(frozen=True)
class SourceRegistryGateFinding:
    code: str
    severity: str
    message: str
    claim: str | None = None
    source_id: str | None = None
    found: Any = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SourceRegistryGateResult:
    registry_id: str
    status: str
    findings: list[SourceRegistryGateFinding] = field(default_factory=list)

    @property
    def block_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "block")

    @property
    def warn_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "warning")

    def to_dict(self) -> dict[str, Any]:
        return {
            "registry_id": self.registry_id,
            "status": self.status,
            "block_count": self.block_count,
            "warn_count": self.warn_count,
            "findings": [finding.to_dict() for finding in self.findings],
        }


def validate_publishable_source_registry(
    registry: SourceRegistry,
    *,
    required_claims: Sequence[str] = (),
    as_of_date: str | None = None,
    max_source_age_days: int | None = None,
    require_owner: bool = True,
) -> SourceRegistryGateResult:
    findings: list[SourceRegistryGateFinding] = []

    if not registry.sources:
        findings.append(
            SourceRegistryGateFinding(
                code="EMPTY_SOURCE_REGISTRY",
                severity="block",
                message="Publishable briefs require at least one source.",
            )
        )

    required = sorted({_norm_claim(claim) for claim in required_claims if str(claim).strip()})
    used_for_by_source = {
        source.source_id: {_norm_claim(claim) for claim in source.used_for}
        for source in registry.sources
    }
    all_claims = set().union(*used_for_by_source.values()) if used_for_by_source else set()

    for claim in required:
        if claim not in all_claims:
            findings.append(
                SourceRegistryGateFinding(
                    code="MISSING_SOURCE_FOR_CLAIM",
                    severity="block",
                    message="Required claim has no SourceRegistry mapping.",
                    claim=claim,
                )
            )
        if claim in HARD_FINANCIAL_CLAIMS and not _has_primary_source_for_claim(registry, claim):
            findings.append(
                SourceRegistryGateFinding(
                    code="MISSING_PRIMARY_SOURCE_FOR_HARD_CLAIM",
                    severity="block",
                    message="Hard financial claims require a primary/official source.",
                    claim=claim,
                )
            )

    as_of = _parse_datetime(as_of_date) if as_of_date else None
    for source in registry.sources:
        if not source.url:
            findings.append(
                SourceRegistryGateFinding(
                    code="SOURCE_URL_MISSING",
                    severity="warning",
                    message="Source has no URL or local source locator.",
                    source_id=source.source_id,
                )
            )
        if require_owner and not getattr(source, "owner", None):
            findings.append(
                SourceRegistryGateFinding(
                    code="SOURCE_OWNER_MISSING",
                    severity="warning",
                    message="Publishable-source ownership is not assigned yet.",
                    source_id=source.source_id,
                )
            )
        if max_source_age_days is not None and as_of is not None:
            retrieved = _parse_datetime(source.retrieved_at)
            if retrieved is None:
                findings.append(
                    SourceRegistryGateFinding(
                        code="SOURCE_RETRIEVED_AT_MISSING",
                        severity="warning",
                        message="Freshness cannot be evaluated without retrieved_at.",
                        source_id=source.source_id,
                    )
                )
            else:
                age_days = (as_of - retrieved).days
                if age_days > max_source_age_days:
                    findings.append(
                        SourceRegistryGateFinding(
                            code="SOURCE_STALE_FOR_PUBLISHABLE_BRIEF",
                            severity="block",
                            message="Source is older than the publishable freshness threshold.",
                            source_id=source.source_id,
                            found=age_days,
                        )
                    )

    status = "pass" if not findings else ("blocked" if any(f.severity == "block" for f in findings) else "warn")
    return SourceRegistryGateResult(registry_id=registry.registry_id, status=status, findings=findings)


def _has_primary_source_for_claim(registry: SourceRegistry, claim: str) -> bool:
    return any(
        source.source_type in PRIMARY_SOURCE_TYPES and claim in {_norm_claim(c) for c in source.used_for}
        for source in registry.sources
    )


def _norm_claim(value: str) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    try:
        if text.endswith("Z"):
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None

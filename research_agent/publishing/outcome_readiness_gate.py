from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any, Mapping


@dataclass(frozen=True)
class OutcomeReadinessFinding:
    code: str
    severity: str
    message: str
    field: str | None = None
    found: Any = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class OutcomeReadinessResult:
    status: str
    findings: list[OutcomeReadinessFinding] = field(default_factory=list)

    @property
    def block_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "block")

    @property
    def warn_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "warning")

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "block_count": self.block_count,
            "warn_count": self.warn_count,
            "findings": [finding.to_dict() for finding in self.findings],
        }


def validate_outcome_readiness(payload: Mapping[str, Any]) -> OutcomeReadinessResult:
    findings: list[OutcomeReadinessFinding] = []
    policy = payload.get("policy") if isinstance(payload.get("policy"), Mapping) else {}
    for field_name in ("no_synthetic_prices", "no_forward_fill", "no_replacement_end_date"):
        if policy.get(field_name) is not True:
            findings.append(
                OutcomeReadinessFinding(
                    code="OUTCOME_FALLBACK_POLICY_NOT_ENFORCED",
                    severity="block",
                    message="Outcome readiness must explicitly reject synthetic prices, forward-fill and replacement dates.",
                    field=f"policy.{field_name}",
                    found=policy.get(field_name),
                )
            )

    target = str(payload.get("earliest_evaluation_date") or "")
    if target and not is_weekday_market_session(target):
        findings.append(
            OutcomeReadinessFinding(
                code="OUTCOME_TARGET_NOT_MARKET_SESSION",
                severity="block",
                message="Outcome target date is not a weekday market session.",
                field="earliest_evaluation_date",
                found=target,
            )
        )

    coverage = payload.get("coverage") if isinstance(payload.get("coverage"), Mapping) else {}
    missing_prices = list(coverage.get("missing_price_tickers") or [])
    missing_benchmarks = list(coverage.get("missing_benchmark_tickers") or [])
    status = str(payload.get("status") or "")
    if status == "ready_to_compute" and (missing_prices or missing_benchmarks):
        findings.append(
            OutcomeReadinessFinding(
                code="OUTCOME_READY_WITH_MISSING_PRICES",
                severity="block",
                message="Readiness cannot be ready_to_compute while ticker or benchmark closes are missing.",
                field="status",
                found={"missing_price_tickers": missing_prices, "missing_benchmark_tickers": missing_benchmarks},
            )
        )
    if status == "pending_price_data" and not (missing_prices or missing_benchmarks):
        findings.append(
            OutcomeReadinessFinding(
                code="OUTCOME_PENDING_WITH_COMPLETE_COVERAGE",
                severity="warning",
                message="Readiness is pending_price_data although coverage appears complete.",
                field="status",
                found=status,
            )
        )

    result_status = "pass" if not findings else ("blocked" if any(f.severity == "block" for f in findings) else "warn")
    return OutcomeReadinessResult(status=result_status, findings=findings)


def is_weekday_market_session(value: str) -> bool:
    parsed = date.fromisoformat(value)
    return parsed.weekday() < 5

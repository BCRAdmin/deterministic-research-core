from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True)
class PolicyGateFinding:
    code: str
    category: str
    severity: str
    message: str
    line: int
    evidence: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PolicyGateResult:
    status: str
    findings: list[PolicyGateFinding] = field(default_factory=list)

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


@dataclass(frozen=True)
class _PolicyRule:
    code: str
    category: str
    severity: str
    message: str
    pattern: re.Pattern[str]


POLICY_RULES: tuple[_PolicyRule, ...] = (
    _PolicyRule(
        "ADVICE_LANGUAGE",
        "advice",
        "block",
        "Publication copy contains advice-like language.",
        re.compile(
            r"\b(we\s+recommend|recommendation|recommended\s+action|"
            r"investors\s+should|anleger\s+sollten|anlageempfehlung|empfehlen\s+wir)\b",
            re.I,
        ),
    ),
    _PolicyRule(
        "RATING_LANGUAGE",
        "rating",
        "block",
        "Publication copy contains rating or recommendation framing.",
        re.compile(
            r"\b(final\s+rating|rating|recommendation|anlageurteil|urteil|"
            r"display\s+rating|external\s+display)\b\s*[:/-]?\s*"
            r"(strong\s+buy|buy|accumulate|hold|sell|underweight|overweight|outperform|avoid)",
            re.I,
        ),
    ),
    _PolicyRule(
        "TRANSACTION_LANGUAGE",
        "transaction",
        "block",
        "Publication copy contains transaction or portfolio-action language.",
        re.compile(
            r"\b(buy|sell|accumulate|trim|reduce|exit|close\s+position|"
            r"start\s+position|staged\s+entry|portfolio\s+action|position\s+sizing|"
            r"kaufen|verkaufen|position\s+schliessen|position\s+schließen)\b",
            re.I,
        ),
    ),
    _PolicyRule(
        "PRICE_TARGET_LANGUAGE",
        "price_target",
        "block",
        "Publication copy contains price-target language.",
        re.compile(r"\b(price\s+target|target\s+price|kursziel|zielkurs)\b", re.I),
    ),
    _PolicyRule(
        "TRADING_LEVEL_LANGUAGE",
        "trading",
        "block",
        "Publication copy contains trading-level language.",
        re.compile(r"\b(stop[- ]?loss|take[- ]?profit|entry\s+level|breakout|pullback|support\s+level)\b", re.I),
    ),
    _PolicyRule(
        "URGENCY_LANGUAGE",
        "urgency",
        "block",
        "Publication copy contains urgency or scarcity pressure.",
        re.compile(r"\b(act\s+now|urgent|before\s+it\s+is\s+too\s+late|dringend|sofort\s+kaufen|jetzt\s+kaufen)\b", re.I),
    ),
)


def scan_publication_policy(text: str, *, artifact_state: str = "public_brief") -> PolicyGateResult:
    findings: list[PolicyGateFinding] = []
    if artifact_state in {"internal_review", "research_seed"}:
        return PolicyGateResult(status="internal_not_scanned_for_public_copy", findings=[])

    for line_no, line in enumerate(text.splitlines() or [text], 1):
        if _skip_policy_line(line):
            continue
        for rule in POLICY_RULES:
            if rule.pattern.search(line):
                findings.append(
                    PolicyGateFinding(
                        code=rule.code,
                        category=rule.category,
                        severity=rule.severity,
                        message=rule.message,
                        line=line_no,
                        evidence=_redact(line),
                    )
                )
    status = "pass" if not findings else "blocked"
    return PolicyGateResult(status=status, findings=findings)


def scan_many_publication_texts(texts: Iterable[str], *, artifact_state: str = "public_brief") -> PolicyGateResult:
    findings: list[PolicyGateFinding] = []
    for text in texts:
        findings.extend(scan_publication_policy(text, artifact_state=artifact_state).findings)
    return PolicyGateResult(status="pass" if not findings else "blocked", findings=findings)


def _skip_policy_line(line: str) -> bool:
    lower = f" {line.lower()} "
    negation_markers = (
        " no ",
        " not ",
        " never ",
        " without ",
        " blocked ",
        " forbidden ",
        " reject ",
        " kein ",
        " keine ",
        " nicht ",
        " verboten ",
        " gesperrt ",
        " blockiert ",
        " non-advice ",
        " no-advice ",
    )
    return any(marker in lower for marker in negation_markers)


def _redact(line: str) -> str:
    return " ".join(line.strip().split())[:220]

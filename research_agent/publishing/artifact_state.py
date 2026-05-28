from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping


PUBLICATION_STATES = ("internal_review", "research_seed", "public_brief", "member_brief")
INTERNAL_STATES = {"internal_review", "research_seed"}
VISIBLE_STATES = {"public_brief", "member_brief"}

_BLOCKED_STATUS_VALUES = {
    "blocked",
    "hidden",
    "internal",
    "internal_only",
    "manual_review",
    "rejected",
    "reject",
    "keep_hidden",
    "archive_internal",
    "closed_no_packet_publishable",
}


@dataclass(frozen=True)
class PublicationGateFinding:
    code: str
    severity: str
    message: str
    field: str | None = None
    expected: Any = None
    found: Any = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ArtifactGateResult:
    artifact_id: str
    state: str
    status: str
    findings: list[PublicationGateFinding] = field(default_factory=list)

    @property
    def block_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "block")

    @property
    def warn_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "warning")

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "state": self.state,
            "status": self.status,
            "block_count": self.block_count,
            "warn_count": self.warn_count,
            "findings": [finding.to_dict() for finding in self.findings],
        }


def infer_publication_state(payload: Mapping[str, Any]) -> str:
    for key in ("artifact_state", "publication_state", "artifact_class", "state"):
        value = _norm(payload.get(key))
        if value in PUBLICATION_STATES:
            return value

    decision = _norm(payload.get("decision"))
    allowed_use = _norm(payload.get("allowed_use"))
    status = _norm(payload.get("status"))
    visibility = _norm(payload.get("visibility"))
    public_member_status = _norm(payload.get("public_member_status"))

    if "research_seed" in decision or "internal_seed" in decision or "research seed" in allowed_use:
        return "research_seed"
    if public_member_status in _BLOCKED_STATUS_VALUES or status in _BLOCKED_STATUS_VALUES:
        return "internal_review"
    if visibility == "member" or _truthy(payload.get("member_ready")):
        return "member_brief"
    if visibility == "public" or _truthy(payload.get("public_ready")) or _truthy(payload.get("publishable")):
        return "public_brief"
    return "internal_review"


def validate_artifact_state(
    payload: Mapping[str, Any],
    *,
    artifact_id: str | None = None,
) -> ArtifactGateResult:
    state = infer_publication_state(payload)
    artifact = artifact_id or str(payload.get("ticker") or payload.get("artifact_id") or "<artifact>")
    findings: list[PublicationGateFinding] = []

    if state not in PUBLICATION_STATES:
        findings.append(
            PublicationGateFinding(
                code="UNKNOWN_ARTIFACT_STATE",
                severity="block",
                message="Artifact state must be one of the publication state machine values.",
                field="publication_state",
                expected=list(PUBLICATION_STATES),
                found=state,
            )
        )
    elif state in INTERNAL_STATES:
        findings.extend(_validate_internal_artifact(payload))
    else:
        findings.extend(_validate_visible_artifact(payload, state=state))

    status = "pass" if not findings else ("blocked" if any(f.severity == "block" for f in findings) else "warn")
    return ArtifactGateResult(artifact_id=artifact, state=state, status=status, findings=findings)


def _validate_internal_artifact(payload: Mapping[str, Any]) -> list[PublicationGateFinding]:
    findings: list[PublicationGateFinding] = []
    truthy_forbidden = {
        "publishable": "Internal artifacts must not be marked publishable.",
        "public_ready": "Internal artifacts must not be marked public-ready.",
        "member_ready": "Internal artifacts must not be marked member-ready.",
        "effective_public": "Internal artifacts must not become effectively public.",
        "route_public": "Internal artifacts must not have public routes.",
        "api_public": "Internal artifacts must not be exposed by public APIs.",
        "sitemap_public": "Internal artifacts must not be included in public sitemaps.",
        "externalPublicationReady": "Internal artifacts must not be externally publication-ready.",
    }
    for field_name, message in truthy_forbidden.items():
        value = _lookup(payload, field_name)
        if _truthy(value):
            findings.append(
                PublicationGateFinding(
                    code="INTERNAL_ARTIFACT_VISIBILITY_LEAK",
                    severity="block",
                    message=message,
                    field=field_name,
                    expected=False,
                    found=value,
                )
            )

    visibility = _norm(payload.get("visibility") or payload.get("requested_visibility"))
    if visibility in {"public", "member"}:
        findings.append(
            PublicationGateFinding(
                code="INTERNAL_ARTIFACT_VISIBILITY_LEAK",
                severity="block",
                message="Internal artifacts must not request public or member visibility.",
                field="visibility",
                expected="internal",
                found=visibility,
            )
        )

    public_member_status = _norm(payload.get("public_member_status"))
    if public_member_status and public_member_status not in _BLOCKED_STATUS_VALUES:
        findings.append(
            PublicationGateFinding(
                code="INTERNAL_ARTIFACT_NOT_EXPLICITLY_BLOCKED",
                severity="warning",
                message="Internal artifacts should carry an explicit blocked/hidden public-member status.",
                field="public_member_status",
                expected="blocked",
                found=public_member_status,
            )
        )
    return findings


def _validate_visible_artifact(payload: Mapping[str, Any], *, state: str) -> list[PublicationGateFinding]:
    findings: list[PublicationGateFinding] = []
    required_truthy = {
        "publishable": "Visible briefs require publishable=true.",
        "policy_gate_passed": "Visible briefs require a passed policy-as-code gate.",
        "source_gate_passed": "Visible briefs require a passed source/provenance gate.",
        "freshness_gate_passed": "Visible briefs require a passed data freshness gate.",
    }
    for field_name, message in required_truthy.items():
        value = _lookup(payload, field_name)
        if not _truthy(value):
            findings.append(
                PublicationGateFinding(
                    code="VISIBLE_ARTIFACT_MISSING_GATE",
                    severity="block",
                    message=message,
                    field=field_name,
                    expected=True,
                    found=value,
                )
            )

    if state == "member_brief" and not _truthy(_lookup(payload, "member_access_gate_passed")):
        findings.append(
            PublicationGateFinding(
                code="MEMBER_BRIEF_MISSING_ACCESS_GATE",
                severity="block",
                message="Member briefs require an explicit member access gate before routing.",
                field="member_access_gate_passed",
                expected=True,
                found=_lookup(payload, "member_access_gate_passed"),
            )
        )

    external_visibility = _truthy(payload.get("external_visibility")) or _truthy(
        _lookup(payload, "externalPublicationReady")
    )
    if external_visibility and not _truthy(payload.get("operator_go")):
        findings.append(
            PublicationGateFinding(
                code="EXTERNAL_VISIBILITY_WITHOUT_OPERATOR_GO",
                severity="block",
                message="External visibility requires explicit operator/legal go.",
                field="operator_go",
                expected=True,
                found=payload.get("operator_go"),
            )
        )
    return findings


def _lookup(payload: Mapping[str, Any], key: str) -> Any:
    if key in payload:
        return payload.get(key)
    gate_state = payload.get("gate_state")
    if isinstance(gate_state, Mapping) and key in gate_state:
        return gate_state.get(key)
    gates = payload.get("gates")
    if isinstance(gates, Mapping) and key in gates:
        return gates.get(key)
    return None


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    return str(value).strip().lower() in {"1", "true", "yes", "y", "pass", "passed", "ready"}


def _norm(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_")

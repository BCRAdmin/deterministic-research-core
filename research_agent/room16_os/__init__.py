"""Room16 personal research-OS contracts and read-only compiler projections.

The package deliberately sits above the deterministic research compiler.  It
does not replace a source, calculate a metric, or make a publication live.
"""

from .contracts import (
    ApprovalReceipt,
    CommissionBrief,
    CopilotSession,
    DecisionRecord,
    DossierReference,
    DossierVersion,
    EvidenceGraph,
    FactLedgerEntry,
    IssuerIdentity,
    PortfolioLedger,
    ProviderEntitlement,
    PublicationEdition,
    ResearchRun,
    ReviewAlert,
    SourceSnapshot,
    ThesisVersion,
    WatchRule,
)
from .projection import (
    AuthorityProjectionError,
    HistoricalAuthorityProjection,
    build_verified_dossier,
    project_historical_authority_bundle,
)

__all__ = [
    "ApprovalReceipt",
    "AuthorityProjectionError",
    "CommissionBrief",
    "CopilotSession",
    "DecisionRecord",
    "DossierReference",
    "DossierVersion",
    "EvidenceGraph",
    "FactLedgerEntry",
    "HistoricalAuthorityProjection",
    "IssuerIdentity",
    "PortfolioLedger",
    "ProviderEntitlement",
    "PublicationEdition",
    "ResearchRun",
    "ReviewAlert",
    "SourceSnapshot",
    "ThesisVersion",
    "WatchRule",
    "build_verified_dossier",
    "project_historical_authority_bundle",
]

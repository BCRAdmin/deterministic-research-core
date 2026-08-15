# Registry Foundation 1.1.0 Freeze

Status: **ACCEPTED / FROZEN** seit 2026-08-15.

Registry Foundation 1.1.0 ist der additive, rückwärtskompatible Nachfolger der
unveränderten Compiler Foundation 1.0.0. Research bleibt alleinige fachliche
Autorität. Product besitzt ausschließlich den hashverifizierten Read-only-Mirror.
Authority Bundle v3 bleibt das Übergangs-ABI und wurde nicht verändert.

Eingefroren sind:

- getrennte Definition-/Instance-Contracts für Metrics, Formulas, Claim Kinds,
  Decision Nodes, Risks und Permission Corridors;
- die vollständige Klassifikation aller in WM, COST und ABT verwendeten
  Metric-, Formula-, Claim- und Decision-Identifiers;
- fail-closed Behandlung unbekannter, positionaler, `event_*`- und kollidierender
  IDs;
- Formelrollen, Ergebnisdimensionen und deterministische Auswertungsregeln;
- die neun genehmigten Pass-Contracts für BA4–BA9;
- Registry Authority, Product-Mirror und Mirror-Lock.

Freeze-Koordinaten:

- Git-Tag: `room16-registry-foundation-v1.1.0`
- Research: `607cdc98e17caf35e47850e73c6b90487bba4193`
- Product: `82c5525f3291ace4e3d8c0fdeee6bd67348f5a38`
- Authority SHA-256: `55585f2242f32da4cc401455cd3186a97bf74f2c4a7feb5078e00d6a6e1ea5fb`
- Pass-Contract SHA-256: `f78cac545eeaa9d61407a61cb1f2ada09088b4e7028e5e620a45d4f374f0b1a0`
- Freeze-Manifest SHA-256: `96797bc6014f42dec0eeefbc576361d6e0ba1bbb5683a59254d29a273a58b00d`

Jede Änderung an eingefrorener Registry-Semantik, Identifier-Klassifikation,
Pass-Contract, Product-Authority oder Authority-Bundle-ABI verlangt ein neues
RFC. Unternehmensdaten dürfen die Registry prüfen, aber keine Sonderdefinition
erzwingen.

BA4–BA9 werden ausschließlich oberhalb dieses Freeze umgesetzt. BA10 ist nicht
autorisiert.

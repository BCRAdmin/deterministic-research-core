
# Compatibility- und Versioning-Policy

- Major 1 ist der eingefrorene Foundation-Vertrag.
- Minor-Änderungen dürfen nur additiv sein und benötigen neue Conformance-Fixtures.
- Major-Änderungen benötigen explizite Migration, Dual-Read-Phase und neue Operatorfreigabe.
- Unbekannte Felder, IDs, Major-Versionen und Registry-Einträge scheitern geschlossen.
- Kanonisches JSON sortiert Objektschlüssel, bewahrt Arrayreihenfolge, nutzt kompaktes UTF-8,
  normalisiert negative Null und verbietet NaN/Infinity.
- Python und JavaScript müssen denselben Conformance-Korpus byte- und hashgleich bestehen.
- Authority Bundle v3 bleibt während der Strangler-Phase der Legacy-Handoff-Vertrag.

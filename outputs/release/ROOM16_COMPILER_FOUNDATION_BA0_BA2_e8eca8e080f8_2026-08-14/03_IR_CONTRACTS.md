
# IR Contracts

BA0 friert folgende Hüllen auf Major-Version 1 ein:

- `IREnvelope`: IR-Typ, Layer, Producer, Payload-Hash, Provenance und Quarantäne.
- `PassManifest`: vollständiger Passvertrag ohne implizite Defaults außerhalb des Schemas.
- `RegistryEnvelope`: Research-Owner, sortierte eindeutige Einträge und Content-Hash.
- `DiagnosticIR`: stabiler Code plus Layer-, Pass-, Subject-, Source-, Root-Cause- und Fixture-Referenzen.
- `CompileVerdictIR`: deterministisch aus Diagnostics abgeleitete Compile-/Release-Wirkung.
- `ProvenanceRef`: Source-ID, Artefaktpfad, SHA-256 und optionaler Locator.
- `QuarantineState`: clear, quarantined oder release_blocked mit Gründen.
- `CompatibilityPolicy`: unbekannte Felder/IDs fail-closed; Major-Wechsel nur mit Migration.

Das Payload-Hashfeld wird bei jeder Nutzung neu berechnet. Ein inhaltlich verändertes Objekt
mit altem Hash ist kein gültiges IR.

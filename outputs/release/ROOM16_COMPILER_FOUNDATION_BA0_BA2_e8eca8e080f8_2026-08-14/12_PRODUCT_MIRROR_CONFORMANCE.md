
# Product Mirror Conformance

| Prüfung | Ergebnis |
|---|---|
| canonical_bytes_equal | PASS |
| authority_sha256_equal | PASS |
| lock_owner_is_research | PASS |
| lock_mode_is_hash_verified_mirror | PASS |
| lock_canonical_sha256_equal | PASS |

Research Authority: `3cbaea421c51e6a3f1b5dad14fc619fd66d1b5420322b619b76455ac9416a239`. Product enthält eine kanonisch identische,
hashgebundene Read-only-Kopie. Der Product-Code darf weder Einträge ergänzen noch Semantik
ändern. Die Quellprüfung und der gemeinsame Python-/JavaScript-Conformance-Korpus blockieren
bei Drift. Der JavaScript-Prüfer validiert alle 12 Pass-Manifeste, alle 10 Registry-Envelopes,
deren Content-Hashes und die vier portablen Canonical-JSON-Fixtures.

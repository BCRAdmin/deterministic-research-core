# Python / JavaScript Conformance Plan

## Ownership

Research owns the ABI schema, canonicalization profile, diagnostic contract and
golden corpus. Python and JavaScript consumers implement only generic
conformance. Product must not encode financial semantics in its validator.

## Shared corpus

One versioned corpus contains:

- canonical input fixtures;
- expected canonical JSON bytes and SHA-256 values;
- expected acceptance/rejection outcome;
- exact stable diagnostic code, severity and release effect;
- supported capability declarations and expected negotiation result;
- bundle, bridge and rendered-artifact examples;
- mutation recipes for tamper/reintroduction tests.

Corpus fixtures are content-addressed and referenced by the BA10 evidence
manifest. Both language runners must consume the exact same bytes.

## Mandatory fixture families

| Family | Positive | Negative/fail-closed evidence |
|---|---|---|
| Canonical JSON | nested objects, arrays, decimals | duplicate keys, float/NaN, noncanonical bytes |
| SHA-256 | manifest and artifacts | manifest/artifact/dependency tamper |
| Unknown fields | additive optional field | unknown required field/artifact/enum |
| Versioning | supported 1.x | unsupported major, below minimum minor |
| Missing artifacts | optional absent | required artifact absent or zero bytes |
| Enum handling | known value | unknown semantic/compatibility/verdict value |
| Null/missing | explicit nullable and absent optional | null required value, undeclared default |
| Numeric range | exact decimal strings, boundary integers | JS unsafe integer, exponent ambiguity, negative zero |
| Unicode | NFC German and issuer names | NFD mismatch, invalid surrogate, invalid UTF-8 |
| Ordering | declared ordered and set-like lists | unsorted set, changed semantic order |
| Capability | exact and superset support | missing required renderer/artifact capability |
| Bridge | byte and semantic parity | cycle, field loss, compatibility mismatch |
| Renderer | full token lineage | unbound number, claim or decision |

## Differential execution

For every fixture, Python and JavaScript emit the same normalized result:

```json
{
  "accepted": false,
  "canonical_sha256": "...",
  "diagnostic_codes": ["ABI_ARTIFACT_HASH_MISMATCH"],
  "release_effect": "block",
  "capability_result": "not_applicable"
}
```

CI compares these result bytes. A differing diagnostic order, null behavior,
hash, capability or verdict blocks BA10.

## Implementation rule

Prefer schema-generated or generic envelope validators. JavaScript may validate
shape, canonical bytes, hashes, versions, required artifacts and capabilities;
it may not recode Fact/Metric/Claim/Decision business rules. Those conclusions
arrive as verified compiler artifacts and diagnostics.

## Existing code migration

- retain mirror hash verifiers as consumer conformance tools;
- cover both existing Authority-v3 readers with bridge fixtures;
- replace JS report-semantic scanning with RenderedArtifactSet parity;
- retire Product Python metric/claim/decision validation only after every old
  negative fixture has a compiler-owned equivalent diagnostic;
- preserve operational/human/publication gates as Product-owned state.


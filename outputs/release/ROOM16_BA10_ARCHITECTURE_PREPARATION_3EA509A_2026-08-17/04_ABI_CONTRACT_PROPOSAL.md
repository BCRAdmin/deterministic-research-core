# ABI Contract Proposal

## Identity

- Contract ID: `room16.compiler_artifact_bundle`
- Contract version: `1.0.0`
- Human shorthand: `room16.compiler_artifact_bundle@1`
- Contract owner: Research
- Consumer authority: transport, schema, hash and declared-capability checks
  only

## Canonical serialization

1. UTF-8 without BOM.
2. Unicode normalized to NFC.
3. JSON object keys sorted lexicographically by Unicode code point.
4. Arrays preserve semantic order only where the contract declares it;
   set-like arrays are sorted by stable ID.
5. Integers remain integers. Decimal financial values are serialized as
   canonical decimal strings with explicit scale/unit metadata; binary floats
   are forbidden in semantic IR.
6. No NaN, Infinity, negative zero, duplicate keys or implementation-specific
   number coercion.
7. Timestamps use RFC 3339 UTC. Environment/run timestamps are excluded from
   semantic identity unless they are source provenance.
8. Canonical JSON bytes are hashed with SHA-256.

`bundle_id` is computed over the canonical manifest with `bundle_id` omitted
and signatures/transport timestamps excluded. Each artifact hash covers its
canonical bytes. A bundle verifies only when both manifest and every required
artifact verify.

## Mandatory sections

- identity and version fields;
- compiler/compile/instrument identity;
- registry and pass locks;
- artifact index;
- L10 verdict and diagnostics reference;
- compatibility state;
- renderer/release eligibility;
- capability declarations.

Missing mandatory sections block. Optional sections never substitute for a
mandatory artifact.

## Optional sections

- non-authoritative annotation references;
- optional source attachments that are already represented by a required
  snapshot record;
- locale/theme catalogs;
- forward-compatible extension namespaces;
- Authority-v3 byte container when semantic compatibility is already proven.

Optional sections are still hash-bound when present.

## Compatibility policy

- Same major: consumers must accept additive unknown optional fields and
  ignore them after preserving their hashes.
- Same major with unknown required artifact kind, enum value affecting
  semantics, or capability: fail closed.
- Higher major: fail closed until explicitly supported.
- Lower supported major: accept only through a declared, tested compatibility
  adapter; never silently upgrade semantics.
- Field removal, changed meaning, changed canonicalization or changed hash
  domain requires a major version.
- New optional artifact kinds and non-semantic metadata may use a minor bump.
- Clarifications that do not alter bytes or behavior may use a patch bump.

## Capability negotiation

Consumers declare supported:

- bundle major/minor range;
- artifact kinds and schema versions;
- canonicalization profiles;
- renderer profiles/locales;
- Authority-v3 bridge mode;
- maximum safe integer/decimal constraints;
- optional extension namespaces.

The producer emits a deterministic capability decision. A consumer cannot
choose a weaker profile when the bundle requires a stronger one. Required
capability mismatch blocks before rendering.

## Unknown and missing behavior

| Condition | Behavior |
|---|---|
| Unknown optional object field | Preserve hash, ignore semantic use, log informational diagnostic |
| Unknown required section/artifact/enum | Block |
| Missing optional section | Continue with explicit absent state |
| Missing required section/artifact | Block |
| `null` where field is optional-nullable | Preserve explicit null |
| Missing field | Apply only contract-declared default; otherwise block |
| Unknown diagnostic code | Preserve and apply its embedded release effect; block if effect cannot be understood |

## Fail-closed rules

The consumer must not render or expose compiler results when the manifest,
artifact, registry, pass, schema, capability, verdict or bridge verification
fails. Product may display the failure and operational diagnostics. It may not
reconstruct data from legacy files unless the manifest explicitly authorizes a
shadow comparison path, and that path may not become canonical output.

## ABI change governance

The proposed ABI and additive L11 emitter require the BA10 RFC. Any discovered
need to alter frozen Foundation envelopes, PassKernel semantics, Registry
Foundation or L3–L10 IR is a separate RFC stop condition.


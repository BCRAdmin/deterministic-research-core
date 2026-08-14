# Room16 Compiler Foundation v1 Freeze

## Frozen baseline

Compiler Foundation `1.0.0` freezes BA0 Architecture Freeze, BA1 Compiler
Kernel and BA2 Registry Authority as accepted on 2026-08-15.

The freeze binds:

- layers L0 through L11;
- Research as sole semantic truth owner;
- Product as a non-semantic consumer;
- Authority Bundle v3 as transition ABI;
- shadow/strangler migration;
- deterministic pass, hash, cache and replay semantics;
- Research Registry Authority and Product's hash-verified mirror;
- WM, COST and ABT candidate bytes and version lock.

## Immutable references

| Item | Frozen value |
|---|---|
| Foundation version | `1.0.0` |
| Git tag | `room16-compiler-foundation-v1.0.0` |
| Research commit | `e8b75cca33bc8436640872a5ccd7698b43a01e56` |
| Product commit | `089982f039d96065d61537f60591777cd985f14c` |
| Foundation version lock | `8b9b7b2f59aa2cfed8280389f14c0e4edd11846d56c1d78e0dbf2c574da7d518` |
| Registry Authority version | `1` |
| Registry Authority SHA-256 | `3cbaea421c51e6a3f1b5dad14fc619fd66d1b5420322b619b76455ac9416a239` |
| Authority Bundle version | `3` |
| Canary version lock | `8cf064d75c8cc3bf23f947189f25ee2de3f2bd0c5356b51d5d7f37d631085333` |

## Change boundary

No BA0–BA2 implementation or contract may change through a normal feature
commit. An approved RFC is mandatory for any layer, ownership, registry, pass,
IR or ABI change. The RFC must define compatibility, migration, rollback,
canary impact, independent review triggers and a new Foundation version.

BA3 and later work must import or consume Foundation contracts without editing
the frozen Foundation implementation. New companies remain fixtures and
validation cases, never architectural exceptions.

## Verification

Run:

```bash
.venv/bin/python scripts/ops/verify_compiler_foundation_freeze.py \
  --product-repo ../company-dossier-lab
```

The verifier checks the version lock, source hashes, Git tag targets, Registry
Authority, Product mirror, canary freeze and Foundation evidence archive.

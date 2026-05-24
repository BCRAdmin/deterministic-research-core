# Block 6 Portfolio Preflight

Status: active

This preflight is the local replacement layer while GitHub Branch Protection, Required Checks, Secret Scanning and Push Protection are blocked by plan/private-repo limits.

It does not equal GitHub protection. It only catches common local mistakes before handoff, commit or push.

## Command

```bash
python3 scripts/ops/portfolio_preflight_scan.py
```

Use strict review mode before portfolio pushes:

```bash
python3 scripts/ops/portfolio_preflight_scan.py --strict-review
```

## Checks

- changed generated/runtime/build paths such as `.runtime`, `.next`, `dist-desktop`, `node_modules`, `out`
- changed archive or release artifacts such as `.zip`, `.dmg`, `.tar`, `.gz`
- changed files above `50 MB`
- changed `outputs/` files as review-only evidence/generated-state warnings
- obvious secret patterns in changed text files, without printing the secret value

## Gates

- Blocking findings must be fixed before commit or handoff.
- Review findings need an explicit decision. `outputs/` changes are sometimes valid evidence, but they must not silently enter a commit.
- GitHub Pro/Public-repo, Branch Protection, Required Checks, Secret Scanning and Push Protection remain Operator decisions.

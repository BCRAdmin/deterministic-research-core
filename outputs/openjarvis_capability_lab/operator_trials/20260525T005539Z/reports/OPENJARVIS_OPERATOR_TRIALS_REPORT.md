# OpenJarvis Operator Trials Report

- Trial ID: `20260525T005539Z`
- Overall decision: `do_not_adopt_openjarvis_as_write_worker; keep_shadow_and_read_only_digest_patterns`
- Runtime sandbox: `PASS_WITH_WARNINGS`
- GitHub/Dependabot digest: `PASS`
- Write/fix sandbox: `FAIL_FOR_OPENJARVIS_ADOPTION`

## Runtime Sandbox

OpenJarvis `1.0.1` installed in an isolated sandbox. `jarvis --help`, `jarvis --version`, `jarvis doctor`, preset init, tool registry listing and a minimal calculator ask worked. The calculator ask returned `437` for `19*23`.

Warnings:

- `uv` was not globally installed; it was installed only in the sandbox venv.
- OpenJarvis/uv pulled CPython `3.14.5` into the sandbox.
- `code-assistant` enables `file_write`, `shell_exec`, `git_commit`, `http_request` and `web_search` by default.
- `doctor` can see local Ollama/model inventory, so future runtime tests need explicit local-engine policy.
- Current CLI uses `--no-scan`, not `--skip-scan`.

## GitHub / Dependabot Digest

Read-only scan over `BCRAdmin` found `10` repos, `12` open PRs and `12` open Dependabot PRs. No comments, labels, branches, commits, merges, notifications mutations or pushes were attempted.

Conclusion: existing `gh` is enough for the digest. Jarvis connector adoption would add integration risk without immediate functional gain.

## Write / Fix Sandbox

OpenJarvis was allowed to write only inside disposable `toy_bug_repo`. The seed repo had 4 failing unittest cases. OpenJarvis produced no patch within the bounded manual window and tests remained red. Vega/Codex baseline then fixed `calc.py` with a two-line patch and `python3 -m unittest -v` passed all 4 tests.

Conclusion: do not adopt OpenJarvis as write/fix worker right now.

## Final Recommendation

Use OpenJarvis as capability reference and benchmark subject. Adopt or rebuild only the read-only digest/reporting ideas. Keep PIG, Obsidian, LIONCOM and deterministic verifiers as source of truth. Do not give OpenJarvis write/shell access to real repos.

## Source Links

- [OpenJarvis GitHub](https://github.com/open-jarvis/OpenJarvis)
- [OpenJarvis Quick Start](https://open-jarvis.github.io/OpenJarvis/getting-started/quickstart/)
- [OpenJarvis Installation](https://open-jarvis.github.io/OpenJarvis/getting-started/installation/)
- [OpenJarvis Configuration](https://open-jarvis.github.io/OpenJarvis/getting-started/configuration/)

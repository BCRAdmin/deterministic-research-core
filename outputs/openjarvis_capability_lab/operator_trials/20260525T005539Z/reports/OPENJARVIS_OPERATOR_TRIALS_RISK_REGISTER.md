# OpenJarvis Operator Trials Risk Register

## High

- `code-assistant` default toolset includes file writes, shell execution, git commit, HTTP and web search. Never run it in real repos without a wrapper.
- Write/fix sandbox failed to produce a patch within the manual bound. Not reliable enough for worker adoption.

## Medium

- Runtime setup pulls its own CPython and many dependencies. This increases operational complexity.
- `doctor` can see local Ollama/model inventory. Runtime policies must define whether that is allowed.
- Documentation/API drift exists around `--skip-scan` vs current `--no-scan`.

## Low

- Read-only GitHub digest via `gh` works and does not need Jarvis.
- Sandbox installation produced no evidence of secret leakage in packaged artifacts.

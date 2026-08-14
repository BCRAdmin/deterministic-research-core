
# Diagnostic- und Verdict-Contract

`semantic_severity` besitzt `info`, `warning`, `error`, `critical`.
`release_effect` besitzt `none`, `review_required`, `compile_block`, `release_block`.
Diese Achsen sind unabhängig.

Diagnostics verwenden stabile Codes und tragen Layer, Pass, Subject, Source-Provenance,
Root Cause und Fixture-Referenzen. Der Verdict sortiert Diagnostics stabil, hasht die
vollständige Liste und leitet `compile_allowed`, `release_allowed` sowie `review_required`
ohne Freitextinterpretation ab.

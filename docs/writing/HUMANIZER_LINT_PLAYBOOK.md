# Humanizer Lint Playbook

Status: active
Scope: Utility copy / Room16 reports / operator copy / document-like reports
Risk class: R0/R1 review pattern
Runtime changes: none
Source checked: GitHub `blader/humanizer` v2.7.0 and local ClawHub copy v2.1.1
Decision: adopt as Humanizer lint, not as an autonomous rewrite skill

## Purpose

Humanizer lint removes generic machine-like prose and AI slop while preserving truth. It can make wording clearer, more concrete and more human, but it must not change facts, numbers, ratings, evidence, legal posture, financial claims, source meaning or uncertainty.

This playbook is review-only for research, finance, legal, YMYL, Room16 and operator-truth outputs. It may suggest rewrites; it does not approve them.

## Operating Rule

1. First preserve evidence truth.
2. Then mark AI-sounding patterns.
3. Rewrite only as a suggestion unless the auto-apply rule explicitly allows it.
4. If a rewrite needs a new source, stronger claim or changed uncertainty, block it as `blocked_fact_or_policy_risk`.
5. For technical, legal, financial or reference text, plain neutral language is the correct human voice. Do not inject first person, warmth, jokes or opinion.

## Pattern Taxonomy

Use these stable `issue_type` values when reviewing copy:

- `significance_inflation`: words such as "serves as", "stands as", "testament", "pivotal", "underscores", "broader trend", "evolving landscape" or abstract importance claims that make ordinary facts sound bigger than the evidence supports.
- `notability_padding`: unsupported name-dropping, media-coverage lists, "active social media presence" or authority claims without a concrete cited point.
- `superficial_ing_analysis`: trailing "-ing" clauses such as "highlighting", "showcasing", "reflecting", "underscoring" or "contributing to" that add fake depth.
- `promotional_language`: ad-like wording such as "boasts", "vibrant", "rich", "breathtaking", "must-visit", "stunning", "commitment to" or "in the heart of" when the output should be neutral.
- `vague_attribution`: "experts argue", "observers have cited", "industry reports", "some critics argue" or similar claims without named evidence.
- `formulaic_challenges_future`: generic "challenges and future outlook" sections that summarize pressure without concrete source-backed detail.
- `ai_vocabulary_cluster`: repeated AI-favored words such as "crucial", "delve", "enhance", "foster", "garner", "interplay", "intricate", "key", "landscape", "pivotal", "showcase", "tapestry", "testament", "underscore", "valuable" or "vibrant".
- `copula_avoidance`: overbuilt phrases such as "serves as", "stands as", "features" or "boasts" where "is" or "has" is clearer.
- `negative_parallelism`: "not only... but also", "not just... it is..." or tailing negations such as "no guessing" when a direct sentence is clearer.
- `rule_of_three`: forced triples that make a sentence feel comprehensive without adding evidence.
- `synonym_cycling`: repeated renaming of the same thing to avoid repetition, especially in reports where a stable term is clearer.
- `false_range`: "from X to Y" constructions where the items are not a real range or scale.
- `passive_or_subjectless_fragment`: missing actor or dropped subject where active wording would make responsibility clearer.
- `dash_overuse`: em dash or en dash used as the default rhythm instead of simpler punctuation.
- `boldface_or_inline_header_overuse`: bold labels or mini-headings that make prose feel templated.
- `emoji_decoration`: emojis used as tone filler in professional or evidence-facing outputs.
- `chatbot_artifact`: phrases such as "great question", "I hope this helps", "let me know if" or model-capability disclaimers leaking into deliverables.
- `cutoff_disclaimer`: stale knowledge-cutoff or browsing disclaimers in final user-facing artifacts.
- `sycophantic_tone`: excessive agreement, praise or reassurance that does not help the task.
- `filler_or_excessive_hedging`: "could potentially", "in order to", "due to the fact that" or stacked caveats that weaken clear statements.
- `generic_conclusion`: final paragraphs that say little beyond "overall", "in conclusion" or "moving forward".
- `diff_anchored_writing`: prose that talks about the edit process instead of the reader-facing result.

## Allowed Findings

- Mark generic SEO or AI-sounding phrasing.
- Mark repetition, synonym cycling and forced triples.
- Mark internal system language that leaks into user-facing copy.
- Mark overly long sentences, weak CTAs, passive wording and subjectless fragments.
- Suggest concrete wording that helps the reader without changing claims.
- Flag `vague_attribution` when a claim needs a source instead of inventing one.

## Forbidden Changes

- Must not change facts.
- Must not change numbers.
- Must not change ratings.
- Must not strengthen or weaken claims.
- Must not add, remove or reinterpret sources.
- Must not make legal or financial statements stronger.
- Must not bypass evidence requirements.
- Must not write away YMYL uncertainty.
- Must not turn a cautious report into promotional copy.
- Must not auto-rewrite research truth, operator truth, source meaning or policy gates.

## Voice Calibration

If the operator gives a writing sample, match that sample's rhythm, sentence length, word level and transition style. If no sample exists, choose plain, concrete, varied prose.

Voice calibration is not a license to add personality everywhere. Blog posts, essays and personal notes may carry more voice. Encyclopedic, technical, legal, financial, reference and audit text should stay neutral, precise and plain.

## Lint Output

Each issue should include:

- `issue_type`
- `severity`
- `current_text`
- `suggested_rewrite`
- `risk`
- `requires_human_review`
- `allowed_auto_apply`
- `evidence_preservation_note`

## Auto-Apply Rule

Auto-apply is allowed only for:

- obvious typos
- duplicate words
- placeholders
- internal UI labels

Everything else is a suggestion that needs review. For Room16, Quellwert, legal, financial, YMYL and operator-truth outputs, set `requires_human_review=true` unless the change is one of the four auto-apply cases above.

## Use Cases

- Materialbedarf copy.
- Elterngeld trust copy.
- Room16 `internal_best_report`.
- Room16 `publish_report` prose.
- Dashboard and operator copy.
- Readable DR-style reports and PDF-ready summaries.
- Non-evidence website copy after project-specific facts are already checked.

## Stop Conditions

Stop and report instead of rewriting when:

- the only improvement would require new evidence,
- the rewrite changes a number, rating, legal posture or financial claim,
- the original text contains unresolved source conflict,
- the target tone would hide uncertainty,
- the text is generated evidence or a policy surface that must stay literal.

## Verification

Minimum checks for this playbook:

- `python3 scripts/project_intelligence_graph/pig.py german-output-quality`
- `python3 scripts/project_intelligence_graph/pig.py rule-propagation`
- project-specific verifier for the output being edited
- tests that assert this playbook keeps `significance_inflation`, `promotional_language`, `superficial_ing_analysis`, `vague_attribution`, `voice_calibration`, `review_only`, and `no_auto_rewrite_research_truth` visible

## Vivi Review

Vivi should check whether suggested rewrites preserve facts, evidence, uncertainty, source meaning and project gates before any user-facing copy is changed.

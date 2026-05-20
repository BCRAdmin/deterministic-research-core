# Humanizer Lint Playbook

Status: active draft
Scope: Utility copy / Room16 reports / operator copy
Risk class: R0 doc-only pattern
Runtime changes: none

## Purpose

Humanizer lint improves clarity and removes generic machine-like prose. It must not change facts, ratings, evidence, legal posture or financial claims.

## Allowed

- Mark generic SEO phrases.
- Mark repetition.
- Mark internal system language that leaks into user-facing copy.
- Mark overly long sentences.
- Mark weak or vague CTAs.
- Mark passive or imprecise wording.
- Suggest concrete user-help wording.

## Forbidden

- Change facts.
- Change numbers.
- Change ratings.
- Strengthen claims.
- Add or remove sources.
- Make legal or financial statements stronger.
- Bypass evidence requirements.
- Write away YMYL uncertainty.
- Turn a cautious report into promotional copy.

## Use Cases

- Materialbedarf copy.
- Elterngeld trust copy.
- Room16 `internal_best_report`.
- Room16 `publish_report` prose.
- Dashboard and operator copy.

## Lint Output

Each issue should include:

- `issue_type`
- `severity`
- `current_text`
- `suggested_rewrite`
- `risk`
- `requires_human_review`
- `allowed_auto_apply`

## Auto-Apply Rule

Auto-apply is allowed only for:

- obvious typos
- duplicate words
- placeholders
- internal UI labels

Everything else is a suggestion that needs review.

## Vivi Review

Vivi should check whether suggested rewrites preserve facts, evidence, uncertainty and project gates before any user-facing copy is changed.

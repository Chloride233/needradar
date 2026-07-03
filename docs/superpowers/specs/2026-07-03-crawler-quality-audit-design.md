# NeedRadar Crawler Quality Audit Design

## Status

Approved for implementation planning.

## Context

NeedRadar depends on crawlers to collect real user discussions before LLM extraction, quality gates, reports, and verification can work. Recent CI/CD failures showed that green tests are not enough unless the project can prove its foundations are reliable. Crawler quality is one of those foundations: if crawlers silently return empty, noisy, duplicated, or malformed data, the downstream AI pipeline will look functional while producing weak insights.

The current crawler layer covers multiple platforms with very different stability profiles:

- API-oriented sources: GitHub, Stack Overflow, Juejin, CSDN, Zhihu.
- HTML or page-structure sources: Douban, Tieba, GitHub Trending.
- high-friction dynamic sources: Bilibili, Xiaohongshu.

The first version of the audit should create a reproducible quality baseline, not rewrite all crawlers.

## Goals

1. Establish an offline, repeatable audit that shows whether each crawler can parse representative platform samples into valid `RawDiscussionItem` objects.
2. Measure whether crawler output is useful for user-need mining, not merely whether requests succeed.
3. Surface platform-specific risks such as fragile HTML parsing, missing fields, duplicate URLs, empty normal fixtures, or high noise.
4. Add a CI-safe quality gate that fails only on structural crawler regressions and reports softer semantic/data-quality issues as warnings.
5. Produce a report that helps decide which platforms are production-ready, warning-level, or blocked.

## Non-Goals

- Do not make CI call real external platforms.
- Do not rewrite the crawler architecture in the first iteration.
- Do not remove or demote platforms automatically.
- Do not introduce browser automation as a required CI dependency.
- Do not invent a single opaque "crawler quality score" that hides failure reasons.

## Reference Frameworks

The audit model is based on established software and data quality frameworks, then narrowed to NeedRadar's crawler domain.

- ISO/IEC 25012 for data quality characteristics such as completeness, accuracy, consistency, credibility, and currentness.
- ISO/IEC 25010 for software quality characteristics such as functional suitability, reliability, maintainability, and testability.
- W3C Data Quality Vocabulary for structuring quality evidence as dimension, metric, and measurement.
- Deequ-style constraint verification for turning data quality expectations into automated checks.

References:

- https://iso25000.com/index.php/en/iso-25000-standards/iso-25012
- https://iso25000.com/index.php/en/iso-25000-standards/iso-25010
- https://www.w3.org/TR/vocab-dqv/
- https://aws.amazon.com/blogs/big-data/test-data-quality-at-scale-with-deequ/

## Quality Dimensions

### 1. Acquisition Reliability

Purpose: determine whether the crawler can collect or parse source data predictably.

Metrics:

- `normal_fixture_parse_success`: normal fixture parses without exception.
- `normal_fixture_item_count`: normal fixture produces at least one item.
- `empty_fixture_behavior`: empty fixture returns an empty list without error.
- `error_fixture_behavior`: malformed or rate-limited fixture produces a classified failure or safe empty result.
- `fallback_path_covered`: crawler-specific fallbacks are covered where relevant.
- `platform_risk_level`: `low`, `medium`, or `high` based on API stability, auth/cookie need, HTML fragility, and dynamic rendering.

Gate behavior:

- Block if a normal fixture crashes.
- Block if a normal fixture produces zero items.
- Warn if only the happy path is covered for a high-risk platform.

### 2. Structural Completeness

Purpose: ensure crawler output satisfies the minimum schema needed by downstream extraction.

Required fields:

- `platform`
- `source_url`
- `title`
- `content`

Metrics:

- `required_field_completeness`: ratio of items with all required fields populated.
- `content_length_p50` and `content_length_p10`: detect thin output that will not support extraction.
- `title_length_p50`: detect empty or broken title parsing.
- `optional_author_fill_rate`
- `optional_tags_fill_rate`
- `field_type_validity`: fields match expected types.

Gate behavior:

- Block if required field completeness is below `0.95` for normal fixtures.
- Warn if median content length is below platform-specific minimums.
- Warn if optional fields are unexpectedly always empty on platforms where they are normally available.

### 3. Semantic Usefulness

Purpose: judge whether the output looks like user-need evidence rather than generic content.

Metrics:

- `need_signal_rate`: ratio of items containing clear demand, pain, comparison, workaround, recommendation, complaint, or purchase/evaluation intent.
- `noise_rate`: ratio of items that are tutorials, marketing, spam, bot summons, generic news, or unrelated content.
- `title_content_alignment`: whether title and content describe the same topic.
- `discussion_nature`: whether the item is from user discussion, issue/comment, Q&A, or article-style source.

Gate behavior:

- First implementation reports semantic metrics as warnings only.
- Human-reviewed fixture labels are required before semantic metrics become blocking.

### 4. Deduplication and Consistency

Purpose: detect repeated pages, unstable identifiers, and pagination bugs.

Metrics:

- `source_url_duplicate_rate`
- `normalized_url_duplicate_rate`
- `platform_item_duplicate_rate`
- `pagination_repeat_detected`
- `source_url_stability`: URL points to the original discussion or content page, not a generic search page.

Gate behavior:

- Block if duplicate rate is above `0.50` on a normal fixture.
- Warn if source URLs are missing stable item identifiers.
- Warn if pagination appears to repeat the same page.

### 5. Maintainability and Observability

Purpose: make future crawler breakage easy to detect and fix.

Metrics:

- `fixture_coverage_level`: `none`, `basic`, `normal_plus_empty`, or `normal_empty_error`.
- `parser_fragility`: `low`, `medium`, or `high`, based on API vs HTML regex vs dynamic browser parsing.
- `failure_reason_classification`: whether failures report useful categories.
- `test_granularity`: whether parser logic can be tested without network.
- `quality_report_available`: whether a platform appears in the generated report.

Gate behavior:

- Warn if a platform has no fixture coverage.
- Warn if a high-fragility parser lacks an error fixture.
- Warn if failures collapse into generic empty results with no reason.

## Platform Risk Classification

Initial classification:

- `github`: low risk. Stable API, auth optional but useful for rate limits.
- `stackoverflow`: low to medium risk. Stable API, but content excerpts may be thin.
- `juejin`: medium risk. API available but less formally stable.
- `csdn`: medium risk. API-like endpoint but platform format may change.
- `zhihu`: medium to high risk. API structure and access rules may change.
- `bilibili`: high risk. WBI signing, comments pagination, anti-bot behavior, and content filtering.
- `xiaohongshu`: high risk. SSR/API/browser fallback, cookie-dependent behavior, anti-bot risk.
- `douban`: high risk. HTML parsing with regex, likely page structure changes.
- `tieba`: high risk. HTML parsing with regex, potential encoding and layout drift.
- `github_trending`: medium risk. HTML parsing, but page structure is relatively predictable.

## Fixture Strategy

Each platform should have fixture files under a crawler-audit fixture directory. The implementation plan can choose the exact path, but the structure should support:

- `normal`: representative successful response with at least two valid items.
- `empty`: valid response with no results.
- `error_or_changed`: malformed, limited, blocked, or changed response shape.

Fixtures should be small and sanitized. They should not include cookies, tokens, personal private data, or large raw pages. For HTML platforms, keep only the minimal DOM fragments needed to test parser behavior.

High-risk platforms should prioritize fixture realism over coverage breadth. For example, one realistic Bilibili comment fixture is more valuable than many synthetic snippets.

## Report Design

The report should have both machine-readable and human-readable forms:

- JSON for CI and future dashboards.
- Markdown for humans reviewing platform readiness.

Report shape:

- Summary table: platform, status, risk level, blocking issues, warnings.
- Per-platform section: metrics by dimension, failed constraints, sample failure reasons.
- Recommendations: immediate fix, later hardening, or mark as experimental.

Platform status:

- `Pass`: structural gates pass and warnings are acceptable.
- `Warning`: crawler is usable but has data quality, coverage, fragility, or semantic concerns.
- `Blocked`: normal fixture fails, required fields are missing, output is empty, or duplicate rate is severe.

## CI Gate Design

First version CI should block only on objective, offline, structural regressions:

- Parser exception on normal fixture.
- Zero items from normal fixture.
- Required field completeness below threshold.
- Severe duplicate rate.
- Invalid field types.

CI should not block on:

- Semantic usefulness before human labels exist.
- Optional field fill rate.
- Platform risk level alone.
- Lack of live network health.

This keeps CI stable while still detecting the class of crawler failures that would poison the pipeline.

## Implementation Shape

The implementation should be small and isolated:

- A crawler audit module that computes metrics from `RawDiscussionItem` lists.
- Platform fixture loaders.
- Tests that run the evaluator against fixtures.
- A CLI or script command that writes JSON and Markdown reports.
- A CI step that runs the offline audit.

Crawler source changes should be limited to small parser extraction improvements if needed for testability. Broad crawler rewrites should be separate follow-up work.

## Success Criteria

The first implementation is complete when:

- Every current platform appears in the audit report.
- Each platform has at least one normal fixture.
- High-risk platforms have normal and failure/changed-shape fixtures.
- The report classifies each platform as `Pass`, `Warning`, or `Blocked`.
- CI can run the offline audit without network access.
- The audit identifies concrete failures without hiding them behind a single aggregate score.

## Open Decisions for Implementation Planning

- Exact fixture directory path.
- Exact CLI command name.
- Whether to include semantic labels in the first implementation or defer them to a second pass.
- Whether to include the audit report in CI artifacts, repository files, or both.

## Self-Review Notes

- No implementation work is included in this design.
- Scope is limited to offline reproducible audit and first-pass CI gates.
- The design avoids requiring live network calls or browser automation in CI.
- The design explicitly separates blocking structural quality from warning-level semantic quality.

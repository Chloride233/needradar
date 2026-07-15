# Crawler audit

This table is the Phase 1 inventory for keyword crawlers returned by
`needradar.crawlers.factory.available_platforms()`. "Implemented" means the
crawler is auto-discovered and has a `crawl()` implementation; it does not
claim that the upstream service guarantees access.

All keyword crawlers inherit the shared HTTP behavior in
`src/needradar/crawlers/base.py`: each request observes the configured minimum
request interval (default 0.5 seconds); HTTP 429 responses honor `Retry-After`
when present and otherwise use exponential backoff, with at most three
attempts. The same request helper retries transient 5xx, timeout, and network
failures; the pipeline does not add another retry layer. Failed tasks remain
available for explicit same-ID requeue. Upstream quotas can change independently
of NeedRadar.

Support tiers use repository evidence rather than the existence of a crawler
class alone:

- **Full:** enabled by the CLI default and covered by parser tests.
- **Experimental:** implemented, but uses an upstream interface without a
  stability commitment, needs a browser/cookie fallback, or lacks crawler tests.
- **Planned:** explicitly committed in project documentation but not implemented.

| Platform | Completion | Support tier | Authentication | Rate-limit behavior | Test coverage |
| --- | --- | --- | --- | --- | --- |
| `bilibili` | Implemented | Experimental | No account or API key; obtains public WBI keys | Shared 429 retry; 1 s between search pages and 0.3 s between reply pages | None (known gap) |
| `csdn` | Implemented | Experimental | None | Shared 429 retry | Parser, empty result, and API error tests in `tests/unit/test_csdn_crawler.py` |
| `douban` | Implemented | Experimental | None | Shared 429 retry | HTML parser and dedup tests in `tests/unit/test_douban_crawler.py` |
| `github` | Implemented | Full | `GITHUB_TOKEN` optional; unauthenticated GitHub API quota otherwise | Shared 429 retry; records GitHub's remaining quota header | Parser and pagination tests in `tests/unit/test_crawlers.py` |
| `juejin` | Implemented | Full | None | Shared 429 retry | Factory and parser tests in `tests/unit/test_crawlers.py` |
| `stackoverflow` | Implemented | Full | `STACKEXCHANGE_KEY` optional; anonymous Stack Exchange quota otherwise | Shared 429 retry | Parser and pagination tests in `tests/unit/test_crawlers.py` |
| `tieba` | Implemented | Experimental | None | Shared 429 retry | HTML parser, dedup, and empty result tests in `tests/unit/test_tieba_crawler.py` |
| `xiaohongshu` | Implemented | Experimental | SSR path needs none; `NR_XHS_COOKIE` enables API fallback | Shared 429 retry | SSR and API fallback tests in `tests/unit/test_xiaohongshu_crawler.py` |
| `zhihu` | Implemented | Experimental | None | Shared 429 retry | Parser, dedup, limit, and empty result tests in `tests/unit/test_zhihu_crawler.py` |

There are currently **no planned keyword platforms** in the repository. A
platform is not counted as planned until a project document names it explicitly.

`GitHubTrendingCrawler` is not a keyword crawler and is not registered as a
platform. It powers the separate trending workflow by scraping GitHub's public
Trending HTML page. It needs no authentication, does not use the shared retry
helper, and is covered through the trending API/service tests rather than the
keyword-crawler suite. This utility is experimental and does not change the
keyword-platform counts above.

## Optional Go collector

`services/collector-go/` provides an opt-in collection and scheduling path for
the three Full Support platforms: GitHub, Stack Overflow, and Juejin. The Go
service has a bounded worker pool, platform-local rate limiting, at most three
attempts for 429/5xx/timeout/network failures, `Retry-After` support, URL and
normalized content SHA-256 deduplication, same-ID failed task retry, cancellation,
SSE progress, health, and JSON runtime metrics. Its adapters and HTTP slice are
verified against local fake providers; this does not establish public-platform
availability, quota behavior, production throughput, or persistence across a Go
service restart.

Python remains the default collection backend and the owner of SQLite task
records, cross-run incremental fingerprints, Vault writes, LLM/RAG/report work,
and budget alerts. Set `NR_COLLECTOR_BACKEND=go` to opt in; the default
`NR_COLLECTOR_GO_FALLBACK_TO_PYTHON=true` preserves the Python crawler when the
Go service is unavailable.

## Reproduce

```bash
.venv/bin/python -m needradar.cli stats
.venv/bin/python -c "from needradar.crawlers.factory import available_platforms; print('\\n'.join(available_platforms()))"
.venv/bin/python -m pytest -q tests/unit/test_crawler_audit.py tests/unit/test_factory.py tests/unit/test_crawlers.py tests/unit/test_csdn_crawler.py tests/unit/test_douban_crawler.py tests/unit/test_tieba_crawler.py tests/unit/test_xiaohongshu_crawler.py tests/unit/test_zhihu_crawler.py
PYTHONPATH=src .venv/bin/python -m pytest -q tests/unit/test_crawl_reliability.py tests/unit/test_base_crawler.py
cd services/collector-go && go test ./... && go test -race ./... && go vet ./...
go test -run TestFakeProviderEndToEnd -v ./internal/collector
cd ../.. && PYTHONPATH=src .venv/bin/python scripts/run_collector_comparison.py --quick
PYTHONPATH=src .venv/bin/python scripts/run_collector_comparison.py --report-only
```

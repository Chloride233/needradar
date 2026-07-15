# Phase 4 Public Collection Stability Observation

Date: 2026-07-14

## Scope

After explicit authorization, NeedRadar ran a bounded crawl-only observation
for the public keyword `AI agent`.

No LLM extraction, report generation, verification, or paid model call was
performed. The runner stored aggregate observation fields only. It did not
store discussion URLs, titles, content, authors, or tags.

| Platform | Attempts | Successes | Success rate | Median elapsed seconds | Returned items | Within-response duplicates |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| GitHub | 3 | 3 | 1.0000 | 0.229 | 60 | 0 |
| Stack Overflow | 3 | 3 | 1.0000 | 0.697 | 60 | 0 |
| Juejin | 3 | 3 | 1.0000 | 0.369 | 60 | 0 |

The plan issued nine sequential public requests: three platforms, three runs
per platform, and at most 20 returned items per request. No request produced a
retryable failure in this window.

## Reproducibility

- Observation artifact: [stability-observations.json](stability-observations.json)
- Artifact SHA-256: `9729b3178dc73de28b898208a73bee53e7c60d037ddc5079c24c2b1c4f889d7c`
- Plan SHA-256: `e84946f623633b45f50fd0c19a14928e6d8d9c52f60f58d2b85eb0f19bd667ff`

The artifact is immutable evidence for this exact keyword, platform set, run
count, time window, and local network conditions. It is not a claim of
long-term platform uptime, crawl completeness, or general performance.

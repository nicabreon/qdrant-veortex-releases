# Shared three-CPU benchmark — live results

**Revision note — 10 November 2026 (WIB).** Earlier reports and README sections remain unchanged.

Campaign `shared3cpu-20261110t021202z`: **4/48 rows recorded; 4 accepted**. Status: `TIMING`.

Three Docker nodes, each with three shared CPUs; disjoint cpusets `4,5,6` / `7,8,9` / `10,11,12`. No per-thread pinning or 1+2 reservation. Native search threads = 3; Veortex permits 3 unpinned rings per local shard with split TopK disabled. Every arm uses the same newly validated Go client.

3M normalized 512D vectors, SQ8 flat search, HNSW disabled, three one-million-point shards, metadata on every point. Top10 per query, 12 candidates per segment, 1,024 fixed test queries per category, scores checked against independent FP32 truth within `1e-6`.

Each row: 16 validated warmup HTTP requests, 60-second dispatch, then drain. HTTP RPS = successful HTTP requests / actual elapsed including drain. Query/s = batch size × HTTP RPS. Percentiles describe whole HTTP responses (the full batch for B64/B128).

[JSON evidence](shared3-live-20261110.json) · [CSV](shared3-live-20261110.csv)

| Engine | Category | B / C | HTTP RPS | Query/s | p50 / p95 / p99 ms | Success / failed |
|---|---|---:|---:|---:|---:|---:|
| native | No filter, no payload | 1 / 64 | 55.43 | 55.43 | 1137.39 / 1546.88 / 1881.56 | 3387 / 0 |
| native | No filter, no payload | 1 / 128 | 55.71 | 55.71 | 2280.24 / 2461.91 / 2854.50 | 3464 / 0 |
| native | No filter, no payload | 64 / 4 | 4.02 | 257.33 | 986.82 / 1078.83 / 1261.08 | 245 / 0 |
| native | No filter, no payload | 128 / 4 | 2.03 | 259.37 | 1965.13 / 2419.23 / 2990.62 | 125 / 0 |

Rejected measurements: 0. They remain in JSON/CSV and are excluded from the successful-results table.

CPU evidence includes full sampled thread masks, active-worker counts, and whole-process CPU equivalents; worker counts do not establish saturation. Native ISA selection was not profiled per request. Compiler builds differ, so this is a shared-budget system comparison.

A separate C160 preflight was stopped when the requested matrix changed. It is retained privately and is not mixed into these C64/C128/B64/B128 results.

Original cluster restored: `pending`. Immutable dataset inventory unchanged: `pending`.

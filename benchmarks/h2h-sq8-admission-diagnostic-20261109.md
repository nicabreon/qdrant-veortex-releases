# Qdrant 1.20.0 vs Veortex V45: fresh SQ8 batch matrix

Campaign status: **MEASUREMENTS_COMPLETE_RECORDED_SCOPE**, **1/1 rows recorded**. No missing cell is estimated.

3,000,000 × 512D vectors; Docker 3 nodes, 3 CPUs/node: one compute CPU and two support CPUs. Flat search, HNSW disabled, SQ8 candidate cap 12/segment, Top10 per query. Metadata exists in every category. The same 1,024-query corpus, independent FP32 truth, and common Go executable are used in both arms.

**B** = queries/HTTP request; **C** = simultaneous HTTP requests. HTTP RPS and query/s both use actual elapsed time including final drain. Each row uses at most 16 warm-up HTTP requests before its 60-second timed dispatch window. At B1, that is only 16 cache-warm-up queries rather than all 1024. Latency percentiles cover all measured HTTP attempts, including rejected/error responses.

Native puts its entire search closure, including TopK/rerank, on its compute CPU. V45 distributes support stages onto its two support CPUs. Compiler flags are not matched. This is an end-to-end system comparison under the stated total CPU budget; it does not isolate a kernel-only causal speedup. The JSON records each engine's pinned source commit and binary digest, plus the common client digest and per-row manifest/report digests.

[Protocol and exact matrix](../reproduce/BATCH_MATRIX_PROTOCOL.md) · [CSV](h2h-sq8-admission-diagnostic-20261109.csv) · [JSON and identities](h2h-sq8-admission-diagnostic-20261109.json)

The table reports accepted measured points, not a certified maximum capacity. C4 is fixed for the batch-size comparison. B1 additionally has a concurrency sweep. All recorded rows, including rejected requests and their full evidence, remain in CSV/JSON and row reports.

## Tanpa filter / tanpa payload

| B | C | Native HTTP RPS | Native query/s | Native p95 / p99 ms | V45 HTTP RPS | V45 query/s | V45 p95 / p99 ms |
|---:|---:|---:|---:|---:|---:|---:|---:|
| — | — | No planned or recorded rows in this run | — | — | — | — | — |

## Tanpa filter / payload true

| B | C | Native HTTP RPS | Native query/s | Native p95 / p99 ms | V45 HTTP RPS | V45 query/s | V45 p95 / p99 ms |
|---:|---:|---:|---:|---:|---:|---:|---:|
| — | — | No planned or recorded rows in this run | — | — | — | — | — |

## Filter aktif (~90%) / payload true

| B | C | Native HTTP RPS | Native query/s | Native p95 / p99 ms | V45 HTTP RPS | V45 query/s | V45 p95 / p99 ms |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 64 | 4 | — | — | — | not accepted; see failure note | not accepted; see failure note | not accepted; see failure note |

## Filter aktif + posisi + pengecualian (~9%) / payload true

| B | C | Native HTTP RPS | Native query/s | Native p95 / p99 ms | V45 HTTP RPS | V45 query/s | V45 p95 / p99 ms |
|---:|---:|---:|---:|---:|---:|---:|---:|
| — | — | No planned or recorded rows in this run | — | — | — | — | — |

## Validation and scope

Timed successful HTTP requests: **235**; failed: **5,694**. Exact ordered Top10 matches on returned queries: **15,040/15,040 successful queries**. Actual correctness-failed requests: **0**. The denominator is successful queries; dispatched queries rejected before returning results are excluded from accuracy.

CPU masks and active worker ticks were sampled during each row. Short-lived or cached filter-worker phases may be unobserved; absence of a sample is disclosed as coverage, while an observed wrong mask fails the CPU contract. V45 route counters record query work, AMX activity, and zero/fallback/HNSW checks per node.

Original cluster restored healthy: **True**. Original donor/lower metadata unchanged: **True**.

Full private campaign receipt SHA-256: `324b7692cc632f1e57ed167841ca2249e3612ed7780c7a19805634ded0220d7d`.

This is a single paired campaign, not a long-duration stability claim or a universal recall guarantee. The gallery is Gaussian and the query corpus fixed. Fresh generated reproduction data uses the published generator seed; that is distributional reproduction rather than a claim that it reconstructs the older gallery byte-for-byte.

### Request-acceptance failures and remediation

1 row(s) were not accepted for throughput comparison. They returned **5,694 HTTP 429 responses**; **364,416 dispatched query executions** in those rejected requests returned no result. These are request-acceptance failures, not accuracy failures: the rejected rows recorded **0 correctness-failed requests** among completed responses. Their throughput and p95/p99 cells are withheld above. The raw latency distributions remain in JSON and include every HTTP attempt, including 429s, rather than successful responses only.

A separate B64/C4 active_only diagnostic with `QDRANT_VEORTEX_SINGLETON_ADMISSION_WAIT_MS=1000` still returned 5,694 HTTP 429s; no C2 test was performed. Across the three nodes, only `reason="query_bytes"` admission counters increased (46,589 / 26,733 / 27,039); all other admission-rejection reason counters remained zero. The configured 384 MiB queue limit (402,653,184 bytes) reached a 402,218,600-byte peak, identifying the queued-query-byte admission limit as the confirmed rejection cause.

The user-approved candidate raises the configurable maximum to 2 GiB while leaving the 384 MiB default unchanged. It is built from source commit `a1a2af190e6f03508efa0b9105b88507dec9f7aa`; its test profile uses `QDRANT_VEORTEX_MAX_QUEUED_QUERY_BYTES=671088640` (640 MiB). The kernel is unchanged, as are the 60-second default request timeout and 90 ms singleton wait. The all-category B64/C4 four-row supplement is still building and has no result yet; its separate report will be linked at [the admission-remediation supplement](h2h-sq8-admission-remediation-20261109.md). Keep this primary 80-row receipt unchanged and retain its rejected measurements as failure evidence.

Rejected cells:

- veortex active_only B64/C4: 5,694 failed HTTP requests, including 5,694 HTTP 429s; 0 correctness-failed requests; CPU observation PASSED, route evidence valid=True.

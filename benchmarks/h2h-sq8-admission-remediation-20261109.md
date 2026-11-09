# SQ8 B64/C4: admission-budget remediation (V45.1)

**4/4 candidate rows accepted**, with zero HTTP errors, HTTP 429s, transport errors, or correctness failures. The original cluster was restored healthy and immutable donor metadata was unchanged.

The workload remains 3,000,000 × 512D, three Docker nodes in one VM, three CPUs per node: one scan/score CPU and two support CPUs. Every HTTP request contains **64 queries**, each returning **Top10**. **C4** means four simultaneous HTTP requests. Metadata exists on every point in every category.

The new binary only expands the configurable queue-byte ceiling to **2 GiB**. Its unset default stays **384 MiB**; this run explicitly sets `QDRANT_VEORTEX_MAX_QUEUED_QUERY_BYTES=671088640` (**640 MiB**) on each node. Singleton admission remains 160 permits/90 ms, and search/client timeouts remain 60 seconds. No scan, TopK, rerank, data-format, or clustering algorithm was changed.

## Successful results

Native values below are the accepted B64/C4 baseline rows from the [primary campaign](h2h-sq8-batch-20261109.md); Native was not rerun in this supplement. Both cohorts use the same fixed query corpus, independent FP32 truth, request bodies, dataset, hardware, and common Go client. They were measured at different times.

| Category | Native query/s | Native p95 / p99 ms | V45.1 HTTP RPS | V45.1 query/s | V45.1 p95 / p99 ms |
|---|---:|---:|---:|---:|---:|
| No filter, no payload | 114.18 | 2,836.55 / 2,853.36 | 15.59 | 997.60 | 307.46 / 320.49 |
| No filter, payload | 115.17 | 2,822.78 / 3,210.61 | 13.98 | 894.44 | 342.98 / 354.04 |
| Active filter (~90%), payload | 120.25 | 2,685.54 / 2,737.10 | 15.18 | 971.73 | 317.63 / 330.22 |
| Active + position + exclusion (~9%), payload | 516.40 | 631.78 / 653.65 | 45.25 | 2,895.74 | 110.04 / 121.89 |

HTTP RPS counts fully successful HTTP batches; query/s counts their 64 validated queries. Throughput uses actual elapsed time including final drain. Each row has 16 validated sequential warmup HTTP requests, followed by 60 seconds of timed dispatch. Latency covers the full batch response and client validation.

## Validation and provenance

- Three focused Rust tests passed: parser bounds/default, B64/C4 reservation estimates, and reservation rollback/rejection reasons.
- Initial accuracy: **4,096/4,096** query checks, covering all 1,024 query vectors in each category.
- Timed load: **5,412 HTTP requests**, **346,368/346,368** returned queries with ordered Top10 IDs identical to independent FP32 truth, score tolerance `1e-6`, and matching payloads where requested.
- All four rows passed sampled CPU-affinity/activity checks on all three nodes and the intended kernel-route checks; HNSW, ring fallback, and dense FP32 batch4 counters stayed zero.
- The effective queue cap gauge was **671,088,640 bytes** on every node in every row. Every per-reason admission rejection delta was zero.
- Source: `a1a2af190e6f03508efa0b9105b88507dec9f7aa`; ELF SHA-256: `90d54aeabbaa17350b94161f6a7926528b13452b0b50296f0bc45fc0e96969e0`.

[CSV](h2h-sq8-admission-remediation-20261109.csv) · [JSON, runtime counters, CPU evidence and identities](h2h-sq8-admission-remediation-20261109.json) · [Release manifest](../releases/admission-budget-20261109-manifest.json) · [Node0 environment example](../configs/admission-budget-node0.env.example)

## Failure diagnosis and limits

The two rejected filtered V45 B64/C4 rows remain in the original raw evidence. The separate 1-second singleton-wait diagnostic still produced 5,694 HTTP 429s and confirmed query-byte admission as the cause on all three nodes. The Rust estimator measured 541,936,640 bytes for active-only B64/C4 and 542,903,296 bytes for the narrower filter, both above the old configurable maximum of 512 MiB. See the [full diagnosis](ADMISSION_REMEDIATION.md). The rejected rows are not used as successful performance comparisons; their percentiles include fast error responses.

This remedies admission for the measured B64/C4 workload. Higher concurrency, larger result limits, larger metadata, or overlapping collections can still reach bounded admission limits. The 640 MiB cap reserves a budget; it is not preallocated RAM.

These are single finite measurements, not maximum-capacity, long-duration stability, or universal-recall claims. The unfiltered V45.1 observations are about 3.0% lower without payload and 5.1% lower with payload than the earlier V45 B64/C4 observations; this run does not establish the cause of that difference. B1 was not remeasured with V45.1. Native keeps TopK/rerank on its compute closure while Veortex uses the support CPUs, and upstream compiler flags are not matched: this is a system comparison under the stated three-CPU budget, not a pure kernel-only comparison.

Final private receipt SHA-256: `be8d576e7e9d258584c001c868960e7d91f05165160b832eefbaa749d28b5413`.

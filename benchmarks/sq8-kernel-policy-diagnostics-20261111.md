# SQ8 kernel-policy diagnostics — 11 November 2026 (WIB)

This is a diagnostic comparison of three profiles on one candidate ELF. It preserves all six accepted timing rows, including the slower profiles. It does not promote a faster candidate.

## Scope

The gallery contains **3,000,000 Gaussian vectors × 512 dimensions**, split into three 1,000,000-point shards. The historically saved gallery seed is unknown. Query sets and F32 truth are preserved and reused; these timing requests do not constitute a new holdout. Metadata is present and indexed on every point in both categories.

- Source: `bc2c7a9ccedd3ba40925220e6a3b7313719ae763` (tree `ce764c2ad2abb4ef44a64ee23505a81941dfb8c9`), based on `560259c84af2b292867b9b2970ec731bcd33e07f`; 30 changed files pinned by source-pin SHA `f600ceee31b54c94f7cdea08ca58a3c7f8ffc56ee8cfa96a911f1b03dc2662fc`.
- Candidate ELF SHA-256: `f6539288d8661e2a1a2e6de2fe0c29d3803415842848fda802eb6520345441eb`; the same ELF served every profile.
- Candidate build: `41cf5b783d4c4ca07a549a5d3a23c0ca2102627d25516485e052b33373320383`; the pinned `quantization / turboquant::` focused selection passed 128 cases. This is the selected focused test scope, not a full-workspace test claim.
- Load: B1/C512 for `unfiltered_no_payload, active_only`, 3 nodes with shared CPU masks `[[4, 5, 6], [7, 8, 9], [10, 11, 12]]` and a 3-CPU container quota each; per-thread pinning was disabled.
- Fixed search contract: SQ8 cosine, Top10, quantization oversampling 1.2, derived candidate count 12 per segment, metadata present in all categories, 16 warmups and 30 seconds of dispatch per row.
- Admission and support limits stayed fixed at 640 singleton permits, 640 in-flight shard/singleton searches, 64 fast-join capacity, and 3 ring workers. Shared postprocessing kept supporting TopK enabled.
- The full common environment was pinned from the accepted prior PFH13 C512 environment receipt. That receipt contributes environment settings only; its source and ELF are not evidence for this run.

## Results

| Profile | Category | Successful HTTP RPS | Successful / failed HTTP | Query QPS | Actual elapsed (s) | p50 / p95 / p99 (ms) | F32 checks |
|---|---|---:|---:|---:|---:|---:|---:|
| PFH9 / private stores off | Unfiltered, no payload | 1844.83 | 55,733 / 0 | 1844.83 | 30.21 | 282.23 / 387.99 / 438.30 | 1,024/1,024 |
| PFH9 / private stores off | ~90% eligible filter + payload | 1698.40 | 51,368 / 0 | 1698.40 | 30.25 | 299.79 / 440.51 / 489.99 | 1,024/1,024 |
| PFH41 odd pair / private stores off | Unfiltered, no payload | 1815.67 | 54,787 / 0 | 1815.67 | 30.17 | 275.60 / 418.60 / 477.33 | 1,024/1,024 |
| PFH41 odd pair / private stores off | ~90% eligible filter + payload | 1719.90 | 51,990 / 0 | 1719.90 | 30.23 | 282.96 / 472.56 / 528.54 | 1,024/1,024 |
| PFH9 / private stores on | Unfiltered, no payload | 1364.44 | 41,314 / 0 | 1364.44 | 30.28 | 377.45 / 523.98 / 576.09 | 1,024/1,024 |
| PFH9 / private stores on | ~90% eligible filter + payload | 1295.07 | 39,201 / 0 | 1295.07 | 30.27 | 395.87 / 579.08 / 652.93 | 1,024/1,024 |

Every timed response was checked against the same category’s preserved 1,024-query truth set. Reported latency includes client transfer, response decoding, and validation.

All six rows passed client correctness, full-mask CPU, intended AMX route, ring admission, and zero fallback gates. No HTTP/client errors, HNSW calls, ring fallback queries, or nonzero ring fallback reasons were recorded. F32 accuracy covered 1,024 distinct manifest queries for each profile/category pair; the pinned checker recorded all 1,024 passing at score tolerance 1e-6.

The PFH9/private-stores-on arm is compared only with its same-PFH9/private-stores-off control. Its process-global streaming calls and score-cell rates increased on each node. These metrics are global SQ8 telemetry, not private-store-only counters; they do not independently prove exclusive private-path use. Attribution is scoped to the pinned source policy and the controlled pair, whose only environment change is the private-store flag.

Both private-stores-on PFH9 rows have lower successful RPS than their same-PFH9 cached controls, so the measurements do not support promoting the private-store setting.

The PFH41 arm is the odd-pair cached diagnostic profile. The historical `074f45…` ELF and source `0aa62c…` are a separate previous-run reference only; they are not the candidate here and do not support a same-ELF or causal comparison.

## Preserved first attempt

The first harness attempt `7a25a65b0b4c51d40cb16c5ef58502540c1786dd57d86a72b0e7be6c87f975b1` is rejected and contributes no measurements: it stopped before timing or accuracy because the row observer raised `KeyError('max_ring_workers')`. Its receipt records zero rows and reports, healthy restored originals, unchanged lower metadata, and no cleanup errors. This report uses only the separate completed run `sq8-amx-source-optimization-20261111-20261110t234634z`.

Run receipt SHA-256: `f852fa3174d3dffb0e195a9ba4ac91621cb8886f30055e26b7676a127432c62f`.

The public [JSON](sq8-kernel-policy-diagnostics-20261111.json) and [CSV](sq8-kernel-policy-diagnostics-20261111.csv) contain the curated measurements and validation evidence. Engine source, query vectors, request/response bodies, and per-query identifiers are excluded. These diagnostics do not replace the released full benchmark matrix or establish a maximum-throughput result. No experimental option was promoted; the 5,000 HTTP RPS target remains unmet.

# Matched batched-search matrix protocol

This document defines a prospective measurement protocol for stock Qdrant 1.20.0 and the frozen Veortex V45 executable. It records no results. Publish measured rows separately, with their receipts and validation status; do not treat the protocol or historical measurements as results from this matrix.

## Workload and matrix

Use the same frozen 3,000,000-vector, 512-dimensional gallery, query vectors, metadata, exact FP32 truth, and collection configuration for both engines. Each request returns ordered Top10 results for every query vector in its batch. The four category manifests are `unfiltered_no_payload`, `unfiltered_payload`, `active_only`, and `active_position_exclude`. Each category uses the same fixed corpus of 1,024 queries and its recorded payload contract. Use SQ8 with a candidate cap of 12 per segment and Top10 oversampling of 1.2; this is a profile setting, not a general minimum. Keep the search path flat and verify that HNSW work is absent from timed rows.

Here, **B** is the number of query vectors in one HTTP request and **C** is the number of concurrently in-flight HTTP requests. Run every category at each of these settings:

| Batch size B | Concurrency C |
|---:|---|
| 1 | 1, 4, 32, 64, 128, 160 |
| 4 | 4 |
| 16 | 4 |
| 32 | 4 |
| 64 | 4 |

That is 10 cells per category, 40 cells per engine, and 80 cells across both engines. Do not substitute query-vector throughput for HTTP request throughput when naming or comparing metrics.

## Shared client and row settings

Build the common client once from `reproduce/cmd/bench-matrix` and use the same executable for every batch size, category, and engine. Store the ignored build output at `reproduce/bench-matrix`. Record the client source revision and the executable SHA-256 emitted in each row report in the campaign manifest and row receipts. Do not mix rows from the legacy `bench.go` client or another client build into this matrix.

The current per-row client controls are:

```sh
go build -o reproduce/bench-matrix reproduce/cmd/bench-matrix/main.go

reproduce/bench-matrix \
  --manifest "$MANIFEST" \
  --output "$ROW_OUTPUT" \
  --mode closed-loop \
  --concurrency "$C" \
  --max-inflight "$C" \
  --batch-size "$B" \
  --seconds 60 \
  --gomaxprocs 7 \
  --warmup-requests 16 \
  --timeout 60s \
  --score-tolerance 0.000001
```

Run that command once for each category and matrix cell, setting `MANIFEST`, `ROW_OUTPUT`, `B`, and `C` to the planned values. The B1 manifests bind the endpoint and frozen query/truth inputs; use the matching engine-specific manifest for its independent data copy. The matrix client keeps the manifest query string and uses `/points/search/batch` for B greater than 1. Export the local cluster's API key as `QDRANT_API_KEY`; never place credentials in a checked-in manifest or receipt. Keep the query, truth, and gallery identity the same across engine manifests; endpoint or collection identifiers may differ. `--help` is the source of truth for the finalized command interface.

### One-arm runner

`reproduce/run-batch-matrix.py` automates the 40 timed rows for one already-started engine arm. It accepts the short manifest filenames emitted by `workload.py` (`nf_false.json`, `nf_true.json`, `active90_payload.json`, and `narrow9_payload.json`) and the canonical `*-manifest.json` names used by paired-run preparation. It first checks the category filters, payload modes, shared endpoint and ordered queries, then runs the common client's offline validator on every manifest. No timed request starts unless all four offline checks pass.

Build the common client before invoking the wrapper. Preview the row plan and complete offline validation without setting an API key:

```sh
python3 reproduce/run-batch-matrix.py \
  --manifest-dir ./reproduce-manifests \
  --client ./reproduce/bench-matrix \
  --engine-label native120 \
  --output ./matrix-output/native120-plan \
  --plan-only
```

For timed rows, point the wrapper at the currently healthy engine arm and use a new output directory:

```sh
export QDRANT_API_KEY='…'
python3 reproduce/run-batch-matrix.py \
  --manifest-dir ./reproduce-manifests \
  --client ./reproduce/bench-matrix \
  --engine-label native120 \
  --output ./matrix-output/native120-run
```

Use `--engine-label veortex-v45` for the other arm. The default run is serial and follows the listed B/C blocks, with all four categories in the protocol order inside each block. `--batch-sizes 1` selects only the six B1 concurrency settings; all four manifests are still preflighted. The optional `--client-cpus` value uses `taskset` on the client process only and does not set server worker affinity. Each invocation requires an output path that does not already exist. It writes `plan.json`, per-manifest offline reports, one report and stdout/stderr pair per timed row, and an incrementally updated `summary.json`; it never retries a row and exits nonzero if any row fails.

This helper runs a single engine arm. It does not start or stop Docker, prepare or switch copy-on-write datasets, run the separate live 4,096-query accuracy preflight, capture node runtime/CPU receipts, or alternate engines. Those lifecycle and paired-order steps remain external to the helper; running the helper for all cells on one engine does not implement the interleaved two-engine campaign schedule below. The `--plan-only` mode and manifest validation make no HTTP calls and do not read `QDRANT_API_KEY`.

Each row is a `qdrant_search_batch_matrix_http_v1` JSON report. Preserve its manifest and client executable hashes, concurrency and batch settings, warm-up and timed request/query totals, `actual_elapsed_s`, dispatch and drain durations, `successful_http_rps`, `query_qps`, full-response latency percentiles, server-time and connection-acquire percentiles, and HTTP/protocol/failure counts. The report's `executable_sha256` identifies the `bench-matrix` client; record the Qdrant server ELF hash separately from the per-row runtime capture. The report reads the API key only from `QDRANT_API_KEY` and records no credential value.

Each cell receives 16 successful, fully validated warm-up HTTP requests before its timed dispatch window; this applies to B1 and every larger batch. Begin the 60-second dispatch window after warm-up, stop dispatch at its deadline, and drain all in-flight requests before closing the row. Include drain time in actual elapsed time. The 60-second request timeout includes response-body reading; it is a client-side failure bound, not a latency target or service-level objective. Record timeouts and every other failed request; never remove failed work from a row or silently rerun it as if the original row passed.

Before timing an engine, validate all 1,024 queries in each of the four categories against the frozen exact FP32 truth on its live collection (4,096 category/query checks per engine, once per engine). Also validate every timed response: Top10 IDs must be in the expected order, absolute score error must be at most `1e-6`, and the category's payload/metadata contract must pass for each result. For requests with `with_payload=true`, validate every returned result's metadata; for `with_payload=false`, confirm the response contains no payload. Batching must not change query order or content between engines. A failed accuracy preflight, warm-up, HTTP response, result check, or metadata check makes the affected row fail validation; retain its output and failure counts.

## Resource profile and comparison scope

Give every node a three-vCPU container quota and a cpuset containing one designated scan/score compute CPU plus two support CPUs. The reference IDs below are from the test VM and must be remapped together if that host is unavailable:

| Node | Three-CPU cpuset | Compute CPU | Support CPUs |
|---|---|---:|---|
| node0 | `4,5,6` | `4` | `5,6` |
| node1 | `7,8,9` | `7` | `8,9` |
| node2 | `10,11,12` | `10` | `11,12` |

Pin the one-CPU compute assignment and two-CPU support assignment in the per-engine environment. For V45, set `QDRANT_VEORTEX_COMPUTE_CPUS` to the node's single compute ID (`4`, `7`, or `10`) and `QDRANT_VEORTEX_SUPPORT_CPUS` to that node's two support IDs (`5,6`, `8,9`, or `11,12`). For the native affinity shim, set `BENCH_COMPUTE_CPU` and `BENCH_SUPPORT_CPUS` to the corresponding IDs. Both arms use `QDRANT__STORAGE__PERFORMANCE__MAX_SEARCH_THREADS=1` and `RAYON_NUM_THREADS=2`; V45 additionally uses `QDRANT_VEORTEX_MAX_RING_WORKERS=1`. Verify each node's effective cgroup quota and cpuset and capture active thread masks and cumulative CPU ticks while each row is running. Save these checks with the row, not just once at startup.

The resource budget is three vCPUs per node in both arms, but the work is distributed differently: stock Qdrant's full native flat-search closure, including scoring and TopK/rerank, runs on its designated compute CPU; Veortex assigns scan/score work to the compute CPU and uses its two support CPUs for support stages such as TopK/rerank. This is an end-to-end system comparison under the stated CPU budget, not an isolated kernel comparison. The builds do not have matched compiler-flag provenance, so the matrix cannot establish a causal kernel speedup.

Capture per-row runtime identity, CPU affinity and tick evidence, and before/after per-node route and search counters. Preserve the effective environment, binary hashes, client hash, dataset/query/truth/manifest hashes, and every counter delta with the row. Confirm the expected flat-search path and absence of HNSW or fallback work before treating a row as valid for the intended comparison. Require strict observed singleton affinity for active search/score compute workers and treat any observed mask violation as a failed CPU-affinity check. Record phase-coverage statuses explicitly: for example, a filter/support worker reported as `NOT_OBSERVED` because it did not execute in the warm steady phase is a coverage limitation, not evidence of a wrong mask and not proof of support-CPU placement. Throughput alone does not prove which path ran.

## Engine lifecycle and run order

Keep an immutable read-only baseline for the dataset and truth. Prepare independent copy-on-write data copies for the native and V45 arms, and verify they represent the same gallery, metadata, collection settings, and query truth. Never let the two engines write to the same storage, and never keep both engine arms active at the same time. Stop and quiesce all nodes before switching binaries or data copies; verify cluster convergence and collection readiness before measuring the next arm.

Run paired category/cell blocks across engines using the frozen schedule below.

Each block runs all four categories in this order: `unfiltered_no_payload`, `unfiltered_payload`, `active_only`, `active_position_exclude`. Within each block, run the two engines in the listed order:

| Block | B | C | Engine order |
|---:|---:|---:|---|
| 1 | 1 | 1 | Native, V45 |
| 2 | 1 | 4 | V45, native |
| 3 | 1 | 32 | Native, V45 |
| 4 | 1 | 64 | V45, native |
| 5 | 1 | 128 | Native, V45 |
| 6 | 1 | 160 | V45, native |
| 7 | 4 | 4 | Native, V45 |
| 8 | 16 | 4 | V45, native |
| 9 | 32 | 4 | Native, V45 |
| 10 | 64 | 4 | V45, native |

Run an independent cold first startup and the 4,096-query accuracy preflight once for each engine before its first measured block. Adjacent blocks can begin with the same engine; keep that cluster running across the boundary rather than restarting it. Stop and quiesce all nodes only when switching engines. Never finish all 40 cells of one engine before beginning the other. Keep this schedule in the campaign record so time drift and engine order are visible.

Keep every scheduled row, including failures, in the final matrix. A complete campaign has 40 rows for each engine and 80 rows total. Report `successful_http_rps` as successful fully validated HTTP requests divided by actual elapsed seconds, including drain. Report query-vector throughput separately as `query_qps`: count B query vectors only for each fully valid successful HTTP batch, divided by the same elapsed time. Partial batch responses may have a separately recorded count of individually valid queries, but do not add them to `query_qps`; under this conservative rule, `query_qps = B × successful_http_rps` even when some requests fail. Keep full-response latency percentiles and HTTP, transport, timeout, and correctness failures alongside both throughput metrics.

## Interpretation boundary

Only a complete, validated, receipt-backed matrix supports claims about this workload and host. Results describe the fixed gallery, query corpus, categories, Top10 response, candidate cap, CPU allocation, software builds, and run window. They do not establish maximum RPS, single-request latency, long-duration stability, production capacity, or all-host behavior. The different placement of native versus Veortex support work and the unmatched compiler provenance also preclude interpreting an end-to-end difference as a pure kernel effect.

The recorded native arm uses the official downloaded GNU executable, not a matched local rebuild. Read the [build flags and CPU acceleration note](../benchmarks/BUILD_FLAGS_AND_CPU_ACCELERATION.md) for embedded toolchain versions, known versus unknown flags, and the distinction between supported and observed ISA paths.

## Observer correction before the primary matrix

The initial R1 attempt stopped after five rows because the external observer classified the dedicated `veortex-flat-*` compute pool as support threads and required stable CPU-tick intervals for short-lived ring threads. The engine and common client did not change. R1 results remain in [the retired-attempt receipt](../benchmarks/h2h-sq8-batch-r1-observer-failure-20261109.json); they are not substituted into the primary matrix.

The corrected observer requires exact compute affinity for both dedicated flat workers and active ring workers. It preserves stable interval CPU-tick totals and separately records positive nanosecond lifetime execution for workers whose verified birth time falls after observation began. Lifetime values are evidence of activity, not an interval-utilization estimate. Process-global quantized search counters still establish positive work on all three shards; actual wrong CPU masks remain failures. The new observer hash is pinned before the primary campaign.

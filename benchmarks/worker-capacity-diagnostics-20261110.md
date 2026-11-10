# SQ8 worker and admission diagnostics — 10 November 2026

These are configuration diagnostics on the same candidate engine, not a new native-Qdrant comparison or a maximum-capacity claim. Each row is one 30-second closed-loop dispatch window plus final drain. The [latest complete four-category matrix](runtime-limits-20261110.md) used 60-second windows and remains a separate benchmark.

The workload is B1: one query per HTTP request, searching all 3,000,000 512D cosine vectors across three one-million-point shards. Each Docker node has three shared guest CPUs with disjoint masks (`4,5,6`, `7,8,9`, `10,11,12`). Scan, separate TopK/rerank support, payload and service threads share those CPUs; there is no per-thread affinity. RF=1, HNSW is disabled, and metadata/indexes remain present for every point even when payload is not returned. The host reports Intel Xeon Silver 4510, 16 guest vCPUs and 47.04 GiB RAM; dedicated physical cores and physical cache topology were not established.

Auto/AMX SQ8 scoring returns ordered Top10 after FP32 reranking of up to 12 candidates per segment. Before every timed cell, all 1,024 saved queries in that category are checked against saved independent FP32 truth, then 16 HTTP warmups run. Every timed response is also validated for ordered IDs/scores (tolerance 1e-6) and payload policy. These same queries are reused for accuracy and timing; they are not held out. The historical gallery seed is unknown, so generator-based reproduction is comparable rather than byte-identical.

HTTP RPS = successful completed HTTP requests / actual monotonic elapsed seconds, including drain and response validation. Since B=1, query/s equals HTTP RPS here. p50/p95/p99 below are end-to-end full-response milliseconds.

## Worker-count and fast-join comparison

All rows in this section use B1/C128. The first six rows change only the maximum ring-worker count (1/2/3). Admission remains 160 singleton permits per local shard, a 90 ms admission wait and an explicit shard-search cap of 480. Fast join 64 prefers an existing compatible ring while its queued/active count is below 64, before opening another ring; it is not the 96-lane execution limit. The last two rows lower only this threshold to 32 with three workers. TopK remains on supporting threads in all rows.

| Max workers | Fast join | Category | HTTP RPS | p50 ms | p95 ms | p99 ms | Failed |
| ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | 64 | No filter / no payload | 972.30 | 129.86 | 173.30 | 190.36 | 0 |
| 1 | 64 | Active filter (~90%) + payload | 984.23 | 130.76 | 156.42 | 168.98 | 0 |
| 2 | 64 | No filter / no payload | 1,280.23 | 96.67 | 123.79 | 149.75 | 0 |
| 2 | 64 | Active filter (~90%) + payload | 984.56 | 109.10 | 248.77 | 443.08 | 0 |
| 3 | 64 | No filter / no payload | 1,292.29 | 96.44 | 119.03 | 139.49 | 0 |
| 3 | 64 | Active filter (~90%) + payload | 1,187.43 | 104.07 | 138.70 | 158.30 | 0 |
| 3 | 32 | No filter / no payload | 1,099.20 | 114.34 | 156.34 | 171.83 | 0 |
| 3 | 32 | Active filter (~90%) + payload | 1,098.05 | 113.03 | 160.42 | 179.03 | 0 |

At C128, fast join 64 with a three-worker limit sampled only two active rings per node. Fast join 32 sampled three active rings, but unfiltered throughput fell from 1,292.29 to 1,099.20 RPS. Whole-process CPU utilization rose from 2.24–2.54 CPU equivalents per node to 2.84–2.88; cluster-summed observed CPU time per query rose about 42%.

The work-weighted logical ratio `query_vector_dots / gallery_vectors_read` fell from 58.99/48.26/42.79 to 40.57/30.21/25.95 queries per gallery-vector read on nodes 0/1/2. Smaller groups made the additional ring less efficient in this run. This counter measures logical work/reuse, **not physical DRAM bandwidth**. Cumulative stage timers overlap across threads and must not be added as request latency.

The warmed worker-2 active-filter cell had a 443.08 ms p99 alongside high host I/O and memory pressure. Aggregate stage counters cannot attribute that tail to an individual request stage. The initial diagnostic used a different warmup policy and had a 480.66 RPS worker-1 active-filter outlier; after per-cell 1,024-query warmup that point measured 984.23 RPS. That initial result is retained in the private evidence and is not used for causal worker scaling.

The auxiliary sampler reads three existing metrics endpoints every two seconds. Its worker-1 timing window was missed in the warmed campaign; ring-limit 1 is not represented as a sampled active-ring observation. All timed rows separately passed full CPU-mask, active-work, ring submit/completion, zero-fallback, zero-HNSW and ISA checks.

## Interpretation and evidence

5,000 HTTP RPS B1 is an exploratory target, not an achieved result. At C128 it would require mean latency no higher than 25.6 ms. At the measured three-worker fast-join-64 means (~99/108 ms), it would require roughly 494/538 concurrent requests if latency stayed unchanged. Higher concurrency can also raise latency and contention; this arithmetic is not a throughput forecast.

Each campaign uses one COW set across its arms; host page cache is not reset and arm order is fixed. Host/VM I/O variability limits causal comparisons. These short cells do not establish long-run stability, maximum capacity, write/failover acceptance or performance of TQ2/TQ4/AVX-only/other operators. Native results are not rerun here. Payload-only and narrow-filter categories remain available in the complete matrix rather than being inferred from these two categories.

All 8 rows passed, with 267,657 timed HTTP requests matching saved FP32 truth and zero failures/fallback/HNSW calls. Originals were restored healthy after each campaign, immutable lower metadata matched, and cleanup passed.

Engine source commit: `0aa62c281b7262368ca6f1ed69de71647be10ac0`. ELF SHA-256: `074f45b364a8e80da3fb9307d637812072fd755f56b91aeb8bdd4bf92b1ba60d`. This measured candidate is distinct from the downloadable V45.1 binary; engine source remains private.

Machine-readable data: [JSON](worker-capacity-diagnostics-20261110.json), [CSV](worker-capacity-diagnostics-20261110.csv). Campaign and client hashes are recorded in JSON. The client revision, if used, has separate provenance; historical results retain their original client pins.

| Profile | Campaign | Receipt SHA-256 |
| --- | --- | --- |
| Worker count | `worker-scaling-warmed-diagnostic-20261110-20261110t141847z` | `52c512f27b06dfc88664de3e87d1be3085d9e8f497710b8d186d84638972973c` |
| Fast join 32 | `worker-scaling-fastjoin32-diagnostic-20261110-20261110t143034z` | `4f12887f8f0238b150a59178f0d4ca5c1a94fd62a6ede14fe0759e964fe0a287` |

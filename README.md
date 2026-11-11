# Qdrant 1.20.0 with Veortex: shared-CPU SQ8 results

## Downloads — exact README benchmark binaries (11 November 2026 revision)

| Binary | Benchmark shown below | Download | Recorded runtime profile |
|---|---|---|---|
| **Shared-CPU matrix — `074f45…`** | Complete native/AVX/Auto matrix; later worker-load diagnostic | [Release and checksums](https://github.com/nicabreon/qdrant-veortex-releases/releases/tag/v1.20.0-veortex.shared-cpu.20261111) | [Matrix](configs/shared-cpu-matrix.env.example) / [three-worker load](configs/shared-cpu-worker-load.env.example) |
| Experimental C512 — `ba68b4…` | 1,931.96 HTTP RPS without filter/payload; 1,684.40 with active filter/payload | [Separate experimental release](https://github.com/nicabreon/qdrant-veortex-releases/releases/tag/v1.20.0-veortex.c512-experimental.20261111) | [C512](configs/c512-experimental.env.example) |

These archives contain the exact measured executables, without recompiling or stripping, plus manifests, deployment notes and third-party notices. Each node shares three CPUs across scan, TopK/rerank, payload and service threads; use the matching profile. Existing V45/V45.1 releases and historical results remain available. The standalone scheduler experiment is a separate program and is not included in these Qdrant server binaries. See [manual deployment](DEPLOYMENT.md).

## Revision — 11 November 2026: cooperative gallery cluster diagnostic

A candidate gallery-split adapter was exercised through the production request path on three nodes with three shared CPUs each, at B1/C64–384. All eight cells passed routing, three-scan-worker, and per-cell 1,024-query F32 gates; cleanup restored the originals and preserved lower data. Candidate throughput was 569–1,300 HTTP requests/s and lower than each historical query-split comparison (728–1,785 requests/s); the runs used different ELFs and manifests, so this is a diagnostic rather than an isolated A/B. The adapter was not promoted. See the [full report](benchmarks/cooperative-gallery-ring-20261111.md), [CSV](benchmarks/cooperative-gallery-ring-20261111.csv), and [curated JSON](benchmarks/cooperative-gallery-ring-20261111.json).


## Revision — 11 November 2026: fixed total of 96 queries

The earlier 4,683 scan query/s result used 96 queries **per worker**, or **288 total** for three workers. It measured aggregate capacity with increased load. A [new fixed-total comparison](benchmarks/fixed-total96-worker-scaling-20261111.md) keeps the **same 96 query identities** in both arms:

| Work assignment | Total queries | Median scan ms | Scan query/s |
|---|---:|---:|---:|
| 1 worker × 96 queries | 96 | 64.902 | 1,479.15 |
| 3 workers × 32 queries | 96 | 46.555 | 2,062.10 |

That is **1.39×** for the fixed workload. Each query searches the full 1M × 512D SQ8 gallery. Seven samples per arm are retained, including a 79.776 ms three-worker sample. This is a local scorer-only diagnostic; it excludes HTTP, TopK, reranking and RPC. The earlier capacity and cooperative-gallery experiments remain below with their original scopes and evidence.

## Revision — 11 November 2026: worker load and cooperative-scan diagnostics

The additional [one-versus-three-worker matrix](benchmarks/worker-scaling-batch-concurrency-20261111.md) covers B1/C64, C128, C256, C384 and B64/B128 at C4/C8, on the same full 3M × 512D SQ8 fixture and three shared CPUs per node. It uses baseline ELF `074f45…`, Auto, fixed 640/640 admission, and 30-second configured windows plus drain. The earlier complete native/AVX/Auto matrix and experimental C512 observations remain separately documented below.

| Category | B1/C384 HTTP requests/s | B64/C8 query members/s | B128/C4 query members/s |
|---|---:|---:|---:|
| No filter / no payload | **1,784.63** | **2,560.36** | **2,231.49** |
| Active filter (~90%) / payload | **1,674.67** | **2,211.60** | **1,917.48** |

These are three-worker results; the linked report includes all one-worker comparisons, p50/p95/p99, counts, CPU diagnostics, and provenance. Of 32 attempted cells, **30 are accepted** (one has an explicit harness-timing adjudication) and two filtered B128/C8 cells retain HTTP-429 capacity failures outside the accepted table. All 32 separate 1,024-query accuracy checks passed. The three-worker rejection counters identify the fixed 2 GiB queued-query byte budget. No engine setting was changed to erase a failure, and no native comparison is claimed for the additional load points.

A separate [single-gallery cooperative scan experiment](benchmarks/single-shard-cooperative-scan-20261111.md) demonstrates test-only partitioning of 1M vectors across three workers: **58.943 → 22.148 ms** for the same batch of 96 queries, scan only. Independent query batches scale **1,634 → 4,683 scan queries/s**. These are component results, not 3M cluster HTTP RPS or B1 latency. As of 11 November 2026, a candidate cooperative-gallery adapter has since been exercised in the production request path, but its eight 3M-cluster cells were slower than the historical query-split rows and it was not promoted. The linked component report remains a test-only scorer diagnostic and includes all samples, including the observed slow sample; the separate [cluster diagnostic](benchmarks/cooperative-gallery-ring-20261111.md) reports the candidate-path measurements.

## Revision — 11 November 2026: latest B1 high-concurrency measurements

The latest completed server-binary diagnostic reached **1,931.96 HTTP requests/s at B1/C512** without filter or payload. The complete head-to-head matrix below uses B1/C64 and B1/C128, plus B64/C4 and B128/C4; those are different load points and their numbers are retained.

These additional measurements use the same full 3,000,000 × 512D SQ8 fixture, three nodes with three shared CPUs each, and three ring workers per node. Each request returns ordered Top10; the same saved 1,024-query FP32 reference is checked per category. The 30-second dispatch window is followed by drain; RPS uses successful requests divided by actual elapsed time.

| Category | Load | HTTP requests/s | p95 (ms) | p99 (ms) | Successful / failed |
|---|---|---:|---:|---:|---:|
| No filter / no payload | B1 / C512 | **1,931.96** | 395.38 | 438.49 | 58,305 / 0 |
| Active filter (~90% eligible) / payload | B1 / C512 | **1,684.40** | 458.28 | 517.35 | 50,817 / 0 |

All timed results matched the saved FP32 Top10, with zero fallback/HNSW queries. These are the `VX_PF8=6` control rows from the [same-binary prefetch diagnostic](benchmarks/sq8-prefetch-distance-20261111.md), with `VX_PFH=9` and fused score pruning disabled. They are finite high-concurrency observations, not a maximum-capacity or a matched-native-C512 claim. Payload-only and narrow-filter categories were not rerun in this diagnostic; their complete results remain below.

**Binary identity:** these two rows used source `a8af3ee1ceb3a7fbee4deec705b8dbda32f9585e`, ELF SHA-256 `ba68b4b06cb5dacf3419aafa83a23c23009de546c9868dabf945e3aa06f0e81d`. This experimental server binary is newer than the `074f45…` binary used for the complete matrix, and is now downloadable as a separately labelled experimental release above; it has not replaced the complete-matrix baseline. Distribution revision: 11 November 2026. The source/test-binary-only tiling, alignment, and operand-preload experiments linked later are separate and were not promoted.

This page shows the latest complete 3-node, 3-CPU-per-node flat-SQ8 matrix. Each node had a disjoint three-CPU mask; scan, TopK, FP32 reranking, payload, and service workers shared that mask with no per-thread affinity. These are selected end-to-end load points, not maximum-capacity or scan-only scaling claims.

**Architecture note — 11 November 2026 (WIB):** [Native Qdrant vs Qdrant + Veortex](docs/QDRANT_NATIVE_VS_VEORTEX.md) explains the ring, shared gallery reads, kernels, TopK/rerank/payload pipeline, and the new gallery-split candidate with diagrams and explicit implementation/measurement limits. Existing benchmark results are preserved below.

Qdrant provides the API, shard routing, storage, and cluster management. For eligible flat SQ8 searches, the per-shard Veortex ring lets concurrent queries share gallery reads. Scan/score work feeds separate TopK, FP32 reranking, and payload-support stages; those worker threads remain free to run on the same three CPUs as scan and service work.

The fixture contains 3,000,000 512D cosine vectors in three one-million-point shards, SQ8 quantization, replication factor 1, HNSW disabled, and all three payload indexes. Payload metadata is present on every point in every category, including requests with `with_payload=false`; that flag only changes what is returned. Requests return ordered Top10 results; SQ8 rescoring uses a cap of 12 candidates per segment (oversampling 1.2) before FP32 rescore. This is the measured profile, not a universal candidate setting. Each category's same 1,024 saved queries are used for accuracy checks and timed cells, with no held-out query set; both fresh backends matched ordered FP32 Top10 at score tolerance 1e-6 on these queries, which does not guarantee exact results on other queries. The historical fixture seed is unknown: public generation helpers produce comparable data, not byte-identical gallery and query artifacts. The four categories below show payload selection and approximate filter eligibility explicitly.

Campaign `runtime-limits-fullmatrix-20261110t110031z` finished 2026-11-10 UTC. All **32/32 fresh Veortex cells** passed the row gates. The independent accuracy checks passed **8/8 × 1,024 queries**; across timed fresh rows, **865,216 HTTP requests** returned **2,406,382 exact-query matches**, with no failed requests or queries. The original three nodes were restored healthy; immutable lower metadata was unchanged; overlays were removed before restart.

The host was reported as an Intel Xeon Silver 4510 VM with 16 guest vCPUs and 47.04 GiB RAM. This records guest-visible allocation; physical-core isolation and physical cache topology were not established. The three node masks were `4,5,6`, `7,8,9`, `10,11,12`, each with a three-vCPU quota.

Each cell used 16 validated warmup requests, then a 60-second dispatch window and final drain. HTTP req/s is successful requests divided by actual elapsed time; query/s is successful query members divided by the same elapsed time. Both rates include drain. Latency is full-response p95/p99 in milliseconds.

Fresh candidate source: `0aa62c281b7262368ca6f1ed69de71647be10ac0`; ELF SHA-256: `074f45b364a8e80da3fb9307d637812072fd755f56b91aeb8bdd4bf92b1ba60d`. The same Go client SHA-256 `5477653066b11acf0ce1f53545f6bd98aad9175ed3c4072a89b051298e05cde0` was used across arms. The candidate passed the frozen focused collection and quantization build-test selection. Exact source-module checks cover 22 cases; this is not a full workspace test claim.

## Results

Each cell is **HTTP requests/s / query members/s; full-response p95/p99 ms**. B1 has equal request and query rates; batched B64/B128 do not. Lower latency is better.

### No filter / no payload

| Batch / concurrency | Native Qdrant 1.20 (prior H0 reference) | Veortex AVX-512 VNNI | Veortex Auto |
|---|---:|---:|---:|
| B1 / C64 | 55.43 / 55.43; 1,546.88 / 1,881.56 | 219.51 / 219.51; 308.25 / 315.82 | 815.96 / 815.96; 89.44 / 104.16 |
| B1 / C128 | 55.71 / 55.71; 2,461.91 / 2,854.50 | 431.34 / 431.34; 311.30 / 334.81 | 1,424.35 / 1,424.35; 108.68 / 122.30 |
| B64 / C4 | 4.02 / 257.33; 1,078.83 / 1,261.08 | 9.72 / 621.77; 468.60 / 532.00 | 30.13 / 1,928.10; 164.96 / 181.35 |
| B128 / C4 | 2.03 / 259.37; 2,419.23 / 2,990.62 | 5.29 / 677.63; 870.25 / 911.16 | 16.75 / 2,144.32; 304.56 / 335.57 |

### No filter / payload

| Batch / concurrency | Native Qdrant 1.20 (prior H0 reference) | Veortex AVX-512 VNNI | Veortex Auto |
|---|---:|---:|---:|
| B1 / C64 | 54.08 / 54.08; 1,375.51 / 1,662.05 | 226.43 / 226.43; 300.08 / 311.86 | 753.17 / 753.17; 96.86 / 108.24 |
| B1 / C128 | 54.27 / 54.27; 2,899.84 / 3,734.77 | 439.35 / 439.35; 316.45 / 366.33 | 1,350.94 / 1,350.94; 117.79 / 136.22 |
| B64 / C4 | 4.00 / 255.84; 1,260.06 / 1,418.92 | 9.50 / 607.89; 469.12 / 490.06 | 26.53 / 1,697.95; 186.96 / 211.18 |
| B128 / C4 | 2.00 / 255.44; 2,520.61 / 2,965.36 | 5.17 / 661.12; 873.23 / 1,000.88 | 15.16 / 1,940.89; 333.65 / 359.62 |

### Active only (~90%) / payload

| Batch / concurrency | Native Qdrant 1.20 (prior H0 reference) | Veortex AVX-512 VNNI | Veortex Auto |
|---|---:|---:|---:|
| B1 / C64 | 50.23 / 50.23; 1,386.95 / 1,677.05 | 220.53 / 220.53; 314.75 / 331.97 | 679.47 / 679.47; 113.02 / 126.65 |
| B1 / C128 | 47.99 / 47.99; 2,974.24 / 3,420.46 | 435.96 / 435.96; 313.90 / 326.81 | 1,256.52 / 1,256.52; 129.97 / 149.43 |
| B64 / C4 | 3.98 / 254.82; 1,293.28 / 1,409.85 | 9.16 / 586.23; 532.95 / 588.20 | 25.07 / 1,604.43; 192.18 / 208.10 |
| B128 / C4 | 1.99 / 254.83; 2,404.76 / 2,658.87 | 5.20 / 665.94; 851.02 / 930.17 | 14.43 / 1,847.66; 352.50 / 385.05 |

### Active + position exclusion (~9%) / payload

| Batch / concurrency | Native Qdrant 1.20 (prior H0 reference) | Veortex AVX-512 VNNI | Veortex Auto |
|---|---:|---:|---:|
| B1 / C64 | 119.30 / 119.30; 601.67 / 669.96 | 966.18 / 966.18; 77.36 / 86.69 | 1,171.11 / 1,171.11; 65.48 / 70.62 |
| B1 / C128 | 120.32 / 120.32; 1,261.05 / 1,473.20 | 1,720.58 / 1,720.58; 97.94 / 107.50 | 1,997.98 / 1,997.98; 90.96 / 104.65 |
| B64 / C4 | 14.21 / 909.52; 346.82 / 386.55 | 34.27 / 2,193.04; 137.37 / 146.61 | 38.70 / 2,477.01; 122.52 / 133.21 |
| B128 / C4 | 7.06 / 903.89; 685.52 / 733.47 | 22.65 / 2,899.02; 215.94 / 237.82 | 26.20 / 3,353.80; 184.37 / 202.46 |

![Successful query throughput for the four request shapes. Values above bars are query members per second, rounded to two decimals; the vertical axis is logarithmic. Native values are prior-run references.](assets/latest-shared-cpu-matrix.svg)

*Successful query members/s by backend. Bar labels show query/s to two decimals; the y-axis uses a logarithmic scale. Native is the earlier H0 reference.*

## Interpretation and provenance

Native values are the 16 accepted H0 measurements under the same three-shared-CPU workload contract and query corpus; they were **not rerun in this campaign** and are cross-run references. AVX-512 VNNI and Auto cells are fresh candidate measurements. Native compiler flags were not recovered or matched to the local Veortex build; the official native executable and locally built candidate also use different compiler/linker toolchains. These are finite observations from one shared VM and do not establish statistical significance, long-duration stability, production capacity, or a pure kernel-speedup claim.

This single-collection matrix does not measure multi-collection fairness or write/recovery behavior. The candidate retains a configurable admission policy historically named `max_collections_per_core`, default 3; in shared mode that cap applies to the shared coordinator bucket, rather than to each physical CPU. It does not limit this one-collection workload, but can backpressure a fourth simultaneously active collection.

The measured local candidate used Rust 1.98.0 with the release profile, opt-level 3, fat LTO, one codegen unit, and debug information disabled. The official native binary's effective compiler flags are unknown. See the [build flags and CPU acceleration notes](benchmarks/BUILD_FLAGS_AND_CPU_ACCELERATION.md) for the limits of the build comparison.

Distribution revision — 11 November 2026: the measured candidate (`074f45b364a8e80da3fb9307d637812072fd755f56b91aeb8bdd4bf92b1ba60d`) is now downloadable from the [shared-CPU release](https://github.com/nicabreon/qdrant-veortex-releases/releases/tag/v1.20.0-veortex.shared-cpu.20261111). It is a different binary from the earlier V45.1 archive. The current V45.1 Linux x86_64 release is available at the [V45.1 release page](https://github.com/nicabreon/qdrant-veortex-releases/releases/tag/v1.20.0-veortex.v45.1.20261109); its executable SHA-256 is `90d54aeabbaa17350b94161f6a7926528b13452b0b50296f0bc45fc0e96969e0`. That is an earlier binary, not the ELF used for the matrix above. The native H0 reference is official stock Qdrant 1.20.0, SHA-256 `5081acd073ef29701415dc2d1655d98750be8c08008541febc20cf2935800f2f`.

Detailed accepted/rejected row diagnostics, exact per-node route/CPU/ISA evidence, and the full curation are in the [report](benchmarks/runtime-limits-20261110.md), [JSON](benchmarks/runtime-limits-20261110.json), and [CSV](benchmarks/runtime-limits-20261110.csv). Curated JSON input SHA-256: `4e947f3cdbd4065ac67d795cfa2896e558437aed2e039b232345af09ba6d670b`.

Additional [worker-count and ring-fill diagnostics](benchmarks/worker-capacity-diagnostics-20261110.md) use shorter, two-category B1 cells on the same engine. They are separate from the complete matrix above and do not establish maximum RPS. A separate [matched-DSO CPU profile](benchmarks/cpu-profile-20261110.md) locates sampled user-mode work in the scan ring and supporting stages; profiled timing is excluded from the throughput tables. The additive [11 November runtime-tuning probes](benchmarks/sq8-runtime-tuning-20261111.md) record completed configuration experiments without replacing the baseline. The subsequent [same-binary kernel-policy diagnostics](benchmarks/sq8-kernel-policy-diagnostics-20261111.md) preserve all six passing measurements, including slower options; neither experiment was promoted. The subsequent [fused score-pruning A/B](benchmarks/sq8-fused-score-pruning-20261111.md) records four passing B1/C512 measurements on one new ELF; its mixed result was also not promoted. A [prefetch-distance probe](benchmarks/sq8-prefetch-distance-20261111.md) then measured `VX_PF8=6` against `0` on that same ELF; disabling prefetch was slower in both categories. A [cache-blocked AMX scorer microdiagnostic](benchmarks/sq8-cache-blocked-amx-20261111.md) then compared two tile schedules on one guest CPU; it retained the baseline and provides no new HTTP or cluster-RPS claim. A separate [SQ8 row-alignment probe](benchmarks/sq8-alignment-probe-20261111.md) includes the cost of copying codes and offsets; native layout was retained because copying was slower in every measured case. An [AMX operand-preload schedule probe](benchmarks/sq8-amx-preload-20261111.md) also retained the baseline after small, mixed scorer differences.

The public [reproduction guide](reproduce/README.md), [matrix runner](reproduce/run-batch-matrix.py), and [accuracy checker](reproduce/verify-accuracy.py) document workload preparation and earlier releases. To repeat these exact latest measurements requires the matching candidate ELF and runtime configuration identified above, the current [batch-matrix protocol](reproduce/BATCH_MATRIX_PROTOCOL.md), and the same saved query/truth artifacts; the downloadable V45.1 binary is an earlier build and does not reproduce this candidate. Earlier revisions and results are preserved in the [verbatim README archive](README.archive-20261110.md), which retains links to the V45/V45.1 studies, prior CPU-policy and dynamic-ring runs, the original failed rows, and their reports.

[`LICENSE`](LICENSE) and [`NOTICE`](NOTICE) describe the public helper and dependency scope. See [third-party notices](third_party/THIRD_PARTY_NOTICES.md), the [license audit](third_party/license-audit.json), and [source availability](third_party/SOURCE-AVAILABILITY.md). The repository publishes binary research builds and reproduction helpers, not Qdrant or Veortex engine source.

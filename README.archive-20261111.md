# Qdrant 1.20.0 with Veortex: shared-CPU SQ8 results (11 November 2026 Archive)

> Preserved historical revision from 11 November 2026 (prior binaries `074f45...`, `ba68b4...`, and historical diagnostics). For the latest comparison (`Native Qdrant 1.20.0` vs Veortex `d2223c8a4` `query-split` and `gallery-split`), see [README.md](README.md). Earlier 10 November history remains in [README.archive-20261110.md](README.archive-20261110.md).

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

The additional [one-versus-three-worker matrix](benchmarks/worker-scaling-batch-concurrency-20261111.md) covers B1/C64, C128, C256, C384 and B64/B128 at C4/C8, on the same full 3M × 512D SQ8 fixture and three shared CPUs per node. It uses baseline ELF `074f45…`, Auto, fixed 640/640 admission, and 30-second configured windows plus drain.

| Category | B1/C384 HTTP requests/s | B64/C8 query members/s | B128/C4 query members/s |
|---|---:|---:|---:|
| No filter / no payload | **1,784.63** | **2,560.36** | **2,231.49** |
| Active filter (~90%) / payload | **1,674.67** | **2,211.60** | **1,917.48** |

Detailed historical tables, charts (`assets/latest-shared-cpu-matrix.svg`), provenance (`benchmarks/runtime-limits-20261110.md`), and prior diagnostic probes (`benchmarks/sq8-*.md`) remain preserved in the repository (`benchmarks/` directory) and [README.archive-20261110.md](README.archive-20261110.md).

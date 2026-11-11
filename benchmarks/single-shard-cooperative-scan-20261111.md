# Revision — 11 November 2026: cooperative scan of one gallery

Revision clarification: the independent mode below uses **96 queries per worker**, hence **288 total queries with three workers**. For the same total 96 queries split 32/32/32, see the [new fixed-total test](fixed-total96-worker-scaling-20261111.md), which measured **1.39×**, rather than the 2.87× increased-load capacity result. Original samples and tables below are retained.

This is a scorer-only feasibility diagnostic on **1,000,000 vectors × 512D, SQ8, batch 96**, in one process with the same three-CPU mask for every arm. It is **not** a 3M-vector cluster HTTP benchmark, a B1 latency measurement, or an available production Qdrant mode. Existing production binaries and the complete benchmark tables remain unchanged.

| Work assignment | Workers | Full-gallery queries completed per sample | Median scan ms | Min–max ms | Median scan queries/s | Median worker CPU equivalents |
|---|---:|---:|---:|---:|---:|---:|
| Different query batches, full gallery per worker | 1 | 96 | 58.734 | 53.479–60.689 | 1,634.48 | 1.000 |
| Different query batches, full gallery per worker | 3 | 288 | 61.493 | 60.990–64.755 | 4,683.45 | 2.993 |
| Same query batch, disjoint gallery partitions | 1 | 96 | 58.943 | 56.202–70.165 | 1,628.69 | 1.000 |
| Same query batch, disjoint gallery partitions | 3 | 96 | 22.148 | 20.182–49.715 | 4,334.39 | 2.900 |

The independent mode scales aggregate scan query throughput by **2.87×**. Cooperative partitioning reduces the same 96-query full-gallery scan from **58.943 to 22.148 ms**, or **2.66×**. These results show near-three-worker scorer scaling is feasible for this workload; they do not identify the sole cause of production scheduling or pipeline overhead. No direct DRAM bandwidth was measured.

Each arm has seven retained timing samples, using a 1/3/3/1 worker-count schedule and alternating mode order. The cooperative three-worker arm includes a **49.715 ms** slow sample; these small-sample medians do not establish production p95/p99 or stability. No sample was discarded.

One immutable 516 MB gallery is shared by all threads. Cooperative worker ranges contain **333,328 / 333,328 / 333,344** vectors, with aligned boundaries and no overlap. They collectively complete **96** full-gallery queries; independent workers collectively complete **288**. Scratch is bounded to 384 KiB per worker. All threads inherit CPUs 4–6; no individual thread affinity is set. AMX permission, allocation, one-chunk query-cache warmup, verification, and thread creation are outside the timed scan. Every worker finishes timing before verification is released, preventing verification from interfering with another timed worker.

Correctness checks include an independent signed-I8 × U8 integer-dot/F32-affine oracle at representative cells in every chunk, and fingerprints covering every score in a separate concurrent verification pass against each assigned range’s serial reference. That verification pass begins after every scan timer stops; the timed pass itself does not hash all scores. All checks passed. This is a component scoring contract; no Top10 retrieval, FP32 embedding recall, filtering, TopK, reranking, payload, RPC, updates, or shard transfer is measured here.

Production integration still needs a bounded common scan-worker budget, safe lane admission/completion, query cancellation and segment lifecycle guards, deterministic candidate merging, and F32 reranking. Each range must retain the full candidate quota before the global merge; dividing that quota among workers can lose candidates.

Provenance: private test-only commit `070808ad0f3d77bb4141657deef6bc73e51fa2de`, test binary SHA-256 `e9ecf82505480a7199ef5210775d9572852577a7d567c67b27458c7bea05bbfc`. Rust 1.98.0, release profile, two build jobs on disk, with the prior quantization build profile reused. The test fixture is private; this note is not a complete public reproduction package for this component experiment.

[Raw samples and provenance](single-shard-cooperative-scan-20261111.json) · [Summary CSV](single-shard-cooperative-scan-20261111.csv)

# Payload completion diagnostic — 10 November 2026

The unchanged candidate was tested again at **AVX-512 VNNI, B64/C4, no filter, payload enabled**. It searched 3M × 512D SQ8 vectors across three Docker nodes, each sharing three CPUs without per-thread affinity. Top10 was returned for each query.

| HTTP request/s | Query/s | p95 ms | p99 ms | Requests success/fail | Timed queries matching FP32 |
|---:|---:|---:|---:|---:|---:|
| 9.37 | 599.70 | 476.89 | 573.47 | 565 / 0 | 36,160 / 36,160 |

Every node submitted and completed all **37,184 query members**, including 1,024 warmup members, through the ring with **zero fallback and zero HNSW calls**. The independent 1,024-query accuracy check also passed. Supporting TopK and payload workers were observed on each full three-CPU mask.

| Node | Reported peak pending/processing materializations | Fallback queries |
|---:|---:|---:|
| 0 | 86 jobs | 0 |
| 1 | 123 jobs | 0 |
| 2 | 113 jobs | 0 |

There were 66 successful support-resource samples and zero failed samples. Peak values are **job counts**, not MiB. The peak is a process-lifetime high-water mark, including readiness and accuracy work. Once-per-second polling can miss short current-in-flight bursts, while the peak gauge preserves the largest observed reservation count since process start.

The earlier [partial full-matrix run](shared-cpu-fullmatrix-20261110.md) had **0 / 25 / 0 fallbacks** and did not save this peak gauge. These are separate runs. This passing repeat does **not** prove why those 25 fallbacks occurred or establish that a fix has been made. Additional reason counters are required to distinguish queue pressure from capture/validation failures.

The added once-per-second metrics polling makes this diagnostic evidence, not a maximum-capacity benchmark. Rates include final drain. Original containers were restored healthy, immutable dataset layers were unchanged, and cleanup reported zero errors.

Source: `560259c84af2b292867b9b2970ec731bcd33e07f`. ELF SHA-256: `63e9c5d1ffb9075bcfa3981c04a65c8240c9b18f1ad095456a93e9943ae466c6`. [Curated JSON](payload-fallback-diagnostic-20261110.json) pins the evidence and records stage/CPU/route checks. The downloadable V45.1 archive remains a different build.

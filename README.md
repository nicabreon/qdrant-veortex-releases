# Qdrant 1.20.0 + Veortex: Native vs Query-Split vs Gallery-Split (16 November 2026)

> **Status: Active Campaign (`RUNNING`)** — Official Native Qdrant 1.20.0 (`45/45` B1 cells complete) is recorded below; `veortex_query` is actively measuring, followed by `veortex_gallery` (`135` B1 cells total) and an additional `B>1` (`B2..B128` at `C4`/`C6`, `210` cells) batch campaign. Full tables, comparative analysis, and exact `d2223c8a4` release downloads will be updated here once all measurements finish validation.
>
> Earlier November 2026 studies and prior binary archives are preserved separately in [README.archive-20261111.md](README.archive-20261111.md) and [README.archive-20261110.md](README.archive-20261110.md).

## Latest Comparison Report

- **Primary B1 Matrix (135 cells: C1–C512 × 5 categories × 3 arms):** [benchmarks/native-query-gallery-20261116.md](benchmarks/native-query-gallery-20261116.md) ([JSON](benchmarks/native-query-gallery-20261116.json) | [CSV](benchmarks/native-query-gallery-20261116.csv))
- **Node Profiles:** [Query-split env](configs/query-gallery-query-20261116.env.example) | [Gallery-split env](configs/query-gallery-gallery-20261116.env.example)
- **Architecture & Reproduction:** [Qdrant Native vs Veortex](docs/QDRANT_NATIVE_VS_VEORTEX.md) | [Batch Matrix Protocol](reproduce/BATCH_MATRIX_PROTOCOL.md) | [Manual Deployment](DEPLOYMENT.md)

## Arms & Binary Identities

| Arm | Executable | Source Commit | Search Scheduling & Execution Mode |
|---|---|---|---|
| **Native Qdrant 1.20.0** | `5081acd073ef29701415dc2d1655d98750be8c08008541febc20cf2935800f2f` | `222b2e44ab1c3f17e8246396ead6558e45041df7` | Native flat SQ8 quantized scan + FP32 rescore (`exact=false`, HNSW disabled, `MAX_SEARCH_THREADS=3`, `RAYON_NUM_THREADS=3`) |
| **Veortex `query-split`** | `d2223c8a48f9b65bcb59196d421fa00ded9488002975afc624990568be2be746` | `afbe2437b0ed3ddb533bfaae1c77d6bbc66d68c7` | Default ring mode (`QDRANT_VEORTEX_MAX_RING_WORKERS=3`, `SEPARATE_TOPK=1`): independent requests & batches share gallery reads per worker |
| **Veortex `gallery-split`** | Same `d2223c8a4` ELF | `afbe2437b0ed3ddb533bfaae1c77d6bbc66d68c7` | Cooperative gallery scan (`QDRANT_VEORTEX_SCAN_MODE=gallery`, `WORKERS=3`, `PRIVATE_TOPK=1`): splits visible gallery tiles across workers |

## How Query-Split and Gallery-Split Differ from Native Qdrant 1.20

All three arms run on the exact same 3-node cluster (`3,000,000` × 512D Cosine SQ8 vectors across three 1M shards, HNSW off, Top-10, 12 candidates/segment / oversampling `1.2`, 3 shared vCPUs per node with no per-thread pinning).

1. **Native Qdrant 1.20.0 (`native_120`):**
   - Each independent `B1` HTTP request triggers its own full scan across the shard's segments (native `BatchFilteredSearcher` shares gallery chunk reads across members *within* a single explicit batch request, not across concurrent `B1` requests).
   - Once concurrent demand fills the 3 shared vCPUs per node, additional requests contend on CPU time and re-read gallery SQ8 codes from memory repeatedly. As a result, completed `native_120` B1 throughput saturates early (~`54–57` req/s unfiltered, ~`48–51` req/s at 90% active filter, and ~`114–119` req/s at ~9% narrow filter) while p95/p99 latency climbs proportionally with queue depth (`>10 s` at C512 unfiltered).
2. **Veortex `query-split` (`veortex_query`):**
   - Compatible flat SQ8 queries from concurrent `B1` requests and explicit batches join a per-shard ring (coalescing window `1000 us`, up to `96` active lanes and `3` ring workers per node).
   - Every ring worker scans a gallery tile once against *all* active query lanes simultaneously using cache-tiled SIMD/matrix kernels (`Auto`: Intel AMX or AVX-512 VNNI depending on batch/lane shape), streaming candidate scores through owner-keyed `SEPARATE_TOPK=1` consumers with conservative cutoff pruning and FP32 reranking on the same 3 shared node vCPUs.
   - **Why it beats native at concurrency (`C >= 4`):** Amortizing each DRAM/L3 scan of the 1M-point shard across many concurrent queries dramatically reduces memory bandwidth per query and keeps scoring compute dense (SIMD/AMX) instead of repeating single-query scans. At very low concurrency (`C1`), ring queuing / coalescing window and inter-stage handoff can add small overhead relative to native's direct path.
3. **Veortex `gallery-split` (`veortex_gallery`):**
   - Uses the exact same binary (`d2223c8a4`) with cooperative gallery scanning enabled (`QDRANT_VEORTEX_SCAN_MODE=gallery`, `QDRANT_VEORTEX_SCAN_WORKERS=3`, `QDRANT_VEORTEX_SCAN_PRIVATE_TOPK=1`).
   - Instead of sending different query batches to separate full-gallery workers, cooperative workers split each visible gallery bitmap tile wave across the 3 scan threads (`veortex-scan-0..2`), maintain private per-worker TopK accumulators per tile, and merge into the query owner's TopK before FP32 rescore.
   - **Expected trade-off vs `query-split`:** Helps parallelize a small number of queries (low concurrency / small active lanes) across multiple shared CPUs to reduce single-batch/low-C scan latency, while adding private-TopK merge and worker coordination overhead at high request concurrency compared to `query-split` (final head-to-head measurements across C1–C512 and B2–B128 will quantify both regimes directly).

## Workload, Quality, & Fairness Contract

- **Dataset & Search:** 3M × 512D Cosine SQ8 (`always_ram=true`, `quantile=1`), 3 shards (`1M` points/node, RF=1), HNSW disabled (`m=0`, `payload_m=0`), `exact=false`, Top-10 (`rescore=true`, `oversampling=1.2`, 12 candidates/segment). Metadata is present on all 3M points across all five categories (`unfiltered_no_payload`, `unfiltered_payload`, `active_only_no_payload`, `active_only` [90%], `active_position_exclude` [~9%]).
- **Accuracy & Payload Gates:** Before timing any arm, 1,024 saved queries per category are verified against an independent FP32 oracle (`1e-6` score tolerance, ordered IDs, exact payload presence/absence); every timed response is also checked per query/member.
- **Measurement Basis:** 16 warmups + 30s closed-loop dispatch + full drain per cell using the shared Go HTTP/1.1 client. **RPS = successful completed requests / actual elapsed seconds including drain** (`Query QPS = successful requests × batch size / elapsed`). Percentiles are never averaged across cells.
- **Provenance & Limits:** Equal 3-vCPU Docker quotas (`4,5,6`, `7,8,9`, `10,11,12`, `NanoCpus=3e9`) do not imply matched compiler flags (native is official upstream Qdrant 1.20.0; Veortex is a local Rust 1.98 LTO release build) or bare-metal isolation (shared KVM Xeon Silver 4510 VM). Results cover finite saved-query cohorts on flat SQ8 only, not HNSW or write-heavy workloads.

## Current Snapshot (`50/135` B1 Accepted Cells Recorded; `veortex_query` Active)

Recorded accepted results are published live in [benchmarks/native-query-gallery-20261116.md](benchmarks/native-query-gallery-20261116.md). Summary of completed `native_120` (`45/45` cells) and initial `veortex_query` (`5/45` cells so far) measurements (`30s` + drain, `0` failed requests):

- **`native_120` unfiltered (no payload / payload):** `~54.0–57.0` req/s at C4–C512 (C1: `19.64–19.72` req/s; C512 p99: `11,130.64 ms` / `13,944.50 ms`)
- **`native_120` active filter ~90% (no payload / payload):** `~48.2–51.1` req/s at C4–C512 (C1: `17.35–17.44` req/s; C512 p99: `12,805.77 ms` / `12,572.95 ms`)
- **`native_120` active + position + exclusion ~9% (payload):** `~113.5–118.5` req/s at C4–C512 (C1: `33.36` req/s; C512 p99: `5,094.40 ms`)
- **`veortex_query` (in progress — first 5 cells recorded in `unfiltered_no_payload`):** C1 `17.15` req/s (p99 `85.35 ms`), C4 `65.07` req/s (p99 `90.24 ms`), C16 `259.97` req/s (p99 `82.99 ms`), C32 `482.81` req/s (p99 `96.49 ms`), C64 `787.14` req/s (p99 `113.77 ms`, vs Native C64 `55.46` req/s / p99 `1,573.56 ms`).
- **Remaining:** `veortex_query` C128–C512 + filtered/payload categories, `veortex_gallery` (`45` cells), and the follow-up `B2..B128` at `C4`/`C6` (`210` cells). Full head-to-head comparison tables and mechanism analysis will be finalized upon completion.

## License & Provenance

Binary research distribution only (Qdrant/Veortex engine source is not included). See [LICENSE](LICENSE), [NOTICE](NOTICE), [third_party/THIRD_PARTY_NOTICES.md](third_party/THIRD_PARTY_NOTICES.md), [third_party/license-audit.json](third_party/license-audit.json), and [third_party/SOURCE-AVAILABILITY.md](third_party/SOURCE-AVAILABILITY.md).

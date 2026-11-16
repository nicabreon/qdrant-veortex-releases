# Native Qdrant 1.20 versus Veortex query/gallery modes — 16 November 2026

Status revision: **fresh campaign in progress**. Accepted measurements are published incrementally below; missing cells remain pending. Existing README studies remain historical and are not substituted for new measurements.

## Planned comparison

| Arm | Executable SHA-256 | Execution mode |
|---|---|---|
| Official native Qdrant 1.20.0 | `5081acd073ef29701415dc2d1655d98750be8c08008541febc20cf2935800f2f` | Native flat SQ8 + FP32 rescore |
| Qdrant + Veortex | `d2223c8a48f9b65bcb59196d421fa00ded9488002975afc624990568be2be746` | Query-split |
| Qdrant + Veortex | Same executable as query-split | Gallery-split with private worker TopK |

The Veortex executable was built from `afbe2437b0ed3ddb533bfaae1c77d6bbc66d68c7`; this publication does not rebuild or strip it. Query-split assigns independent query groups to workers scanning the local gallery. Gallery-split divides a query group's local gallery scan among cooperating workers and merges candidates; the total gallery searched remains the same.

## Workload and resource contract

- 3,000,000 gallery vectors, 512 dimensions, Cosine, scalar INT8/SQ8, three one-million-point shards, replication factor 1, HNSW disabled.
- Three Docker nodes, each allowed three shared guest CPUs, with disjoint node CPU sets `4,5,6`, `7,8,9`, and `10,11,12`. Quota is three CPUs/node. Every search, TopK, rescore, payload and I/O thread shares that allowance; no per-thread affinity shim or 1+2 CPU partition.
- B1, ordered Top-10 per request; SQ8 rescoring uses oversampling 1.2, a measured cap of 12 candidates per segment. `exact=false` requests use the quantized flat path; the independent accuracy reference is FP32.
- Concurrency **C1, C4, C16, C32, C64, C128, C256, C384, C512**.
- Five categories: no filter/no payload; payload only; active filter/no payload; active filter/payload; active + position + subject exclusion/payload. All points retain metadata in every category. Active filter matches 90%; compound filter matches 269,999 of 3,000,000 points (approximately 9%).
- 1,024 saved FP32 oracle queries/category checked before timing, including ordered IDs, score tolerance `1e-6`, and payload contract. Timed responses are also checked against their corresponding saved query truth.
- Same Go HTTP/1.1 client, 16 warmup requests, then 30-second closed-loop dispatch and full drain for each cell. **RPS = successful completed requests / actual elapsed seconds including drain**, not offered rate. B1 query/s and HTTP request/s are equal.
- Planned primary matrix: **135 cells**, three arms × five categories × nine concurrency values. Report p50/p95/p99 full-response latency, counts, errors, elapsed time and CPU/routing checks. Rejected cells will be identified separately; their failures will not be relabeled as passing.

Mode configurations: [query-split](../configs/query-gallery-query-20261116.env.example), [gallery-split](../configs/query-gallery-gallery-20261116.env.example). Apply an environment file to a node together with its own API/network/storage settings; the file is not a complete three-node deployment. The existing [reproduction protocol](../reproduce/BATCH_MATRIX_PROTOCOL.md) and [manual deployment guide](../DEPLOYMENT.md) describe the surrounding setup.

## Limits of comparison

Equal CPU allowances and search contracts do not establish equal compiler provenance: native is the official downloaded executable, Veortex is a local Rust 1.98 release build; compiler/linker flags are not matched. Auto may choose AVX-512 VNNI or AMX depending on query shape; a low-concurrency cell need not use AMX. The host is a shared KVM VM exposing Intel Xeon Silver 4510 features, not an isolated bare-metal machine. No causality claim about shared physical host contention is made.

The historical gallery seed is unknown; the saved queries/oracles and input hashes identify the measured fixture, but public generation scripts cannot recreate the exact original gallery. A finite correctness cohort is not a guarantee of universal FP32 equivalence. This SQ8 flat study does not establish performance for HNSW, TQ2/TQ4, all operators, or write-heavy workloads. Only reviewed accepted cells appear in the tables below; the exact downloadable binary package will be added after campaign review.

## Measured results (fresh campaign)

Campaign status: **RUNNING**; **10/135 accepted cells** currently recorded. Unmeasured cells are marked pending. [Curated JSON](native-query-gallery-20261116.json) / [CSV](native-query-gallery-20261116.csv). Each cell is **HTTP RPS; p95 / p99 ms**. This is B1, so HTTP RPS equals query/s.

### No filter / no payload

| Concurrency | Native 1.20 | Veortex query-split | Veortex gallery-split |
|---|---:|---:|---:|
| C1 | 19.64; 57.11 / 78.69 | pending | pending |
| C4 | 56.13; 95.30 / 105.64 | pending | pending |
| C16 | 56.97; 326.79 / 395.98 | pending | pending |
| C32 | 55.99; 658.49 / 787.06 | pending | pending |
| C64 | 55.46; 1,281.58 / 1,573.56 | pending | pending |
| C128 | 56.57; 2,776.07 / 3,614.32 | pending | pending |
| C256 | 56.18; 6,708.59 / 9,214.56 | pending | pending |
| C384 | 55.81; 10,067.30 / 10,352.12 | pending | pending |
| C512 | 54.71; 10,626.71 / 11,130.64 | pending | pending |

### Payload only

| Concurrency | Native 1.20 | Veortex query-split | Veortex gallery-split |
|---|---:|---:|---:|
| C1 | 19.72; 52.76 / 69.69 | pending | pending |
| C4 | pending | pending | pending |
| C16 | pending | pending | pending |
| C32 | pending | pending | pending |
| C64 | pending | pending | pending |
| C128 | pending | pending | pending |
| C256 | pending | pending | pending |
| C384 | pending | pending | pending |
| C512 | pending | pending | pending |

### Active filter / no payload (90%)

| Concurrency | Native 1.20 | Veortex query-split | Veortex gallery-split |
|---|---:|---:|---:|
| C1 | pending | pending | pending |
| C4 | pending | pending | pending |
| C16 | pending | pending | pending |
| C32 | pending | pending | pending |
| C64 | pending | pending | pending |
| C128 | pending | pending | pending |
| C256 | pending | pending | pending |
| C384 | pending | pending | pending |
| C512 | pending | pending | pending |

### Active filter + payload (90%)

| Concurrency | Native 1.20 | Veortex query-split | Veortex gallery-split |
|---|---:|---:|---:|
| C1 | pending | pending | pending |
| C4 | pending | pending | pending |
| C16 | pending | pending | pending |
| C32 | pending | pending | pending |
| C64 | pending | pending | pending |
| C128 | pending | pending | pending |
| C256 | pending | pending | pending |
| C384 | pending | pending | pending |
| C512 | pending | pending | pending |

### Active + position + exclusion / payload (~9%)

| Concurrency | Native 1.20 | Veortex query-split | Veortex gallery-split |
|---|---:|---:|---:|
| C1 | pending | pending | pending |
| C4 | pending | pending | pending |
| C16 | pending | pending | pending |
| C32 | pending | pending | pending |
| C64 | pending | pending | pending |
| C128 | pending | pending | pending |
| C256 | pending | pending | pending |
| C384 | pending | pending | pending |
| C512 | pending | pending | pending |

Recorded rejected cells: **0**. Accepted timed requests: **15,966**; failed requests in accepted cells: **0**. The JSON/CSV retain any rejected cells separately through their acceptance flag. Passing accuracy refers to the measured cohort, not a universal FP32 guarantee.

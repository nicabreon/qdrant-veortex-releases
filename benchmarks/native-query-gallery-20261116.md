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

Campaign status: **RUNNING**; **94/135 accepted cells** currently recorded. Unmeasured cells are marked pending. [Curated JSON](native-query-gallery-20261116.json) / [CSV](native-query-gallery-20261116.csv). Each cell is **HTTP RPS; p95 / p99 ms**. This is B1, so HTTP RPS equals query/s.

### No filter / no payload

| Concurrency | Native 1.20 | Veortex query-split | Veortex gallery-split |
|---|---:|---:|---:|
| C1 | 19.64; 57.11 / 78.69 | 17.15; 67.03 / 85.35 | 24.07; 43.66 / 44.80 |
| C4 | 56.13; 95.30 / 105.64 | 65.07; 77.06 / 90.24 | 85.71; 50.10 / 51.52 |
| C16 | 56.97; 326.79 / 395.98 | 259.97; 71.60 / 82.99 | 313.27; 55.46 / 58.58 |
| C32 | 55.99; 658.49 / 787.06 | 482.81; 81.03 / 96.49 | 509.19; 68.26 / 72.71 |
| C64 | 55.46; 1,281.58 / 1,573.56 | 787.14; 97.50 / 113.77 | pending |
| C128 | 56.57; 2,776.07 / 3,614.32 | 1,338.89; 115.48 / 135.33 | pending |
| C256 | 56.18; 6,708.59 / 9,214.56 | 1,595.73; 210.76 / 228.40 | pending |
| C384 | 55.81; 10,067.30 / 10,352.12 | 1,806.38; 318.36 / 373.51 | pending |
| C512 | 54.71; 10,626.71 / 11,130.64 | 2,052.28; 343.91 / 395.04 | pending |

### Payload only

| Concurrency | Native 1.20 | Veortex query-split | Veortex gallery-split |
|---|---:|---:|---:|
| C1 | 19.72; 52.76 / 69.69 | 18.32; 59.70 / 72.53 | pending |
| C4 | 56.76; 90.80 / 98.24 | 68.35; 66.66 / 88.75 | pending |
| C16 | 56.04; 358.59 / 447.15 | 268.51; 66.31 / 83.19 | pending |
| C32 | 56.54; 719.77 / 845.85 | 505.51; 71.63 / 82.59 | pending |
| C64 | 54.87; 1,680.11 / 1,924.26 | 803.52; 89.01 / 97.49 | pending |
| C128 | 55.35; 2,704.77 / 3,415.22 | 1,363.20; 117.06 / 134.52 | pending |
| C256 | 54.47; 5,675.34 / 5,922.77 | 1,522.92; 226.26 / 242.24 | pending |
| C384 | 54.56; 10,364.60 / 12,829.21 | 1,678.00; 318.13 / 354.34 | pending |
| C512 | 54.01; 9,828.86 / 13,944.50 | 1,828.83; 420.93 / 468.93 | pending |

### Active filter / no payload (90%)

| Concurrency | Native 1.20 | Veortex query-split | Veortex gallery-split |
|---|---:|---:|---:|
| C1 | 17.35; 61.34 / 75.86 | 15.21; 73.50 / 95.16 | pending |
| C4 | 51.09; 104.05 / 113.93 | 58.75; 76.70 / 95.02 | pending |
| C16 | 50.39; 367.23 / 437.00 | 223.38; 87.58 / 96.35 | pending |
| C32 | 50.00; 781.77 / 929.66 | 425.28; 86.69 / 107.64 | pending |
| C64 | 50.51; 1,511.06 / 1,709.36 | 708.84; 104.44 / 120.33 | pending |
| C128 | 49.97; 3,279.95 / 3,865.49 | 1,301.36; 122.20 / 133.48 | pending |
| C256 | 49.01; 5,967.79 / 7,264.02 | 1,583.19; 208.45 / 221.40 | pending |
| C384 | 48.96; 8,004.87 / 8,274.30 | 1,756.71; 322.15 / 380.63 | pending |
| C512 | 48.78; 12,477.39 / 12,805.77 | 1,926.19; 414.00 / 506.74 | pending |

### Active filter + payload (90%)

| Concurrency | Native 1.20 | Veortex query-split | Veortex gallery-split |
|---|---:|---:|---:|
| C1 | 17.44; 62.03 / 84.58 | 15.22; 75.36 / 94.25 | pending |
| C4 | 50.61; 103.54 / 110.17 | 57.57; 82.47 / 98.25 | pending |
| C16 | 50.67; 372.04 / 455.01 | 225.94; 83.08 / 96.74 | pending |
| C32 | 49.78; 703.05 / 942.42 | 429.32; 82.75 / 103.00 | pending |
| C64 | 49.02; 1,585.11 / 1,795.18 | 725.16; 102.10 / 115.90 | pending |
| C128 | 48.77; 2,911.12 / 3,933.37 | 1,332.06; 120.96 / 134.63 | pending |
| C256 | 48.80; 5,322.44 / 5,382.02 | 1,518.04; 227.04 / 242.47 | pending |
| C384 | 48.32; 8,404.05 / 9,661.33 | 1,700.81; 324.33 / 354.10 | pending |
| C512 | 48.16; 11,105.92 / 12,572.95 | 1,799.65; 422.24 / 473.47 | pending |

### Active + position + exclusion / payload (~9%)

| Concurrency | Native 1.20 | Veortex query-split | Veortex gallery-split |
|---|---:|---:|---:|
| C1 | 33.36; 37.40 / 61.72 | 25.25; 45.44 / 48.99 | pending |
| C4 | 113.54; 46.53 / 51.09 | 93.09; 50.15 / 54.64 | pending |
| C16 | 117.63; 172.60 / 202.31 | 354.20; 52.65 / 54.84 | pending |
| C32 | 118.52; 305.00 / 364.99 | 669.03; 55.92 / 60.43 | pending |
| C64 | 117.36; 606.57 / 727.62 | 1,252.81; 62.67 / 67.85 | pending |
| C128 | 117.85; 1,266.15 / 1,377.60 | 2,685.42; 82.87 / 126.05 | pending |
| C256 | 115.75; 2,423.12 / 2,613.01 | 2,879.67; 170.19 / 226.08 | pending |
| C384 | 115.46; 4,428.52 / 5,817.61 | 3,074.21; 219.26 / 276.73 | pending |
| C512 | 114.69; 4,595.74 / 5,094.40 | 3,126.79; 259.83 / 335.94 | pending |

Recorded rejected cells: **0**. Accepted timed requests: **1,513,970**; failed requests in accepted cells: **0**. The JSON/CSV retain any rejected cells separately through their acceptance flag. Passing accuracy refers to the measured cohort, not a universal FP32 guarantee.

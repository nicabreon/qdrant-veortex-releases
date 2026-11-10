# Veortex runtime-limits shared-three-CPU SQ8 matrix

Revision date: 10 November 2026. Native values are explicitly earlier-run H0 references; this campaign measured only Veortex AVX-512 VNNI and Auto.

**Curation state:** PROVISIONAL — RESTORATION PENDING. Campaign `runtime-limits-fullmatrix-20261110t110031z` status `TIMING`. Fresh measurements: 32/32 accepted; 0 rejected; 0 expected cells not recorded. Historical native reference cells: 16 (not new tests).

Candidate source `0aa62c281b7262368ca6f1ed69de71647be10ac0`, ELF `074f45b364a8e80da3fb9307d637812072fd755f56b91aeb8bdd4bf92b1ba60d`, common Go client `5477653066b11acf0ce1f53545f6bd98aad9175ed3c4072a89b051298e05cde0`. The candidate passed the frozen focused collection and quantization build-test selection. Exact source-module checks cover 22 cases; this is not a full workspace test claim. The user explicitly selected `SEPARATE_TOPK=1`, retaining separate TopK and deferred payload-materialization worker stages under the shared process CPU mask. This is not a same-ELF A/B result; the earlier `63e9…` A/B ELF is a different binary.

The full-matrix nodes omitted the deprecated COMPUTE_CPUS/SUPPORT_CPUS environment keys and used shared placement, so this run does not capture a startup deprecation warning. Migration-warning evidence, if collected, is a separate smoke-test artifact.

The fixture is 3 million 512D cosine vectors, SQ8 flat search, three one-million-point shards, three payload indexes, and HNSW disabled. Each node had a three-vCPU quota, a disjoint full three-CPU mask (4–6, 7–9, 10–12), and no per-thread pinning. Veortex used shared postprocessing placement, three ring workers, a 2 GiB queue budget, and three search/Rayon threads. Both fresh Veortex backends ran the same selected pipeline mode and ELF.

Each category uses 1,024 distinct saved Top10 queries, checked against the pinned FP32 oracle before timing. Independent checks currently passed: 8/8; a complete timing matrix requires every category on both fresh backends. Every timed cell has 16 warmup requests, a 60-second dispatch, and a final drain. HTTP req/s = successful HTTP requests / elapsed; query/s = successful query members / elapsed. Both include final drain. p50/p95/p99 are full-response validated latency percentiles. Errors include failed requests/queries, HTTP 429, transport, protocol, and correctness failures.

## Accepted measurements and historical native references

The tables contain only accepted rows. Measurement acceptance means correctness, route, CPU-mask/work, ISA, and error gates passed; it is not a throughput target. Valid lower-throughput measurements remain included. `Native (prior H0)` is a previous three-CPU run, not measured alongside or rerun in this campaign. Rate/latency cell: HTTP req/s / query/s / p50 / p95 / p99 ms / elapsed s.

### No filter / no payload

| B / C | Engine and scope | HTTP req/s / query/s / p50 / p95 / p99 / elapsed | Requests success/fail | Queries success/fail | Exact truth matches | 429 / transport / protocol / correctness errors |
|---:|---|---:|---:|---:|---:|---:|
| B1 / C64 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 55.43 / 55.43 / 1137.39 / 1546.88 / 1881.56 / 61.11 | 3387 / 0 | 3387 / 0 | 3387 | 0 / 0 / 0 / 0 |
| B1 / C64 | Veortex AVX-512 VNNI (AMX disabled) | 219.51 / 219.51 / 291.97 / 308.25 / 315.82 / 60.20 | 13215 / 0 | 13215 / 0 | 13215 | 0 / 0 / 0 / 0 |
| B1 / C64 | Veortex Auto (AMX allowed) | 815.96 / 815.96 / 77.67 / 89.44 / 104.16 / 60.06 | 49004 / 0 | 49004 / 0 | 49004 | 0 / 0 / 0 / 0 |
| B1 / C128 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 55.71 / 55.71 / 2280.24 / 2461.91 / 2854.50 / 62.17 | 3464 / 0 | 3464 / 0 | 3464 | 0 / 0 / 0 / 0 |
| B1 / C128 | Veortex AVX-512 VNNI (AMX disabled) | 431.34 / 431.34 / 297.79 / 311.30 / 334.81 / 60.20 | 25968 / 0 | 25968 / 0 | 25968 | 0 / 0 / 0 / 0 |
| B1 / C128 | Veortex Auto (AMX allowed) | 1424.35 / 1424.35 / 87.50 / 108.68 / 122.30 / 60.08 | 85577 / 0 | 85577 / 0 | 85577 | 0 / 0 / 0 / 0 |
| B64 / C4 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 4.02 / 257.33 / 986.82 / 1078.83 / 1261.08 / 60.93 | 245 / 0 | 15680 / 0 | 15680 | 0 / 0 / 0 / 0 |
| B64 / C4 | Veortex AVX-512 VNNI (AMX disabled) | 9.72 / 621.77 / 409.08 / 468.60 / 532.00 / 60.22 | 585 / 0 | 37440 / 0 | 37440 | 0 / 0 / 0 / 0 |
| B64 / C4 | Veortex Auto (AMX allowed) | 30.13 / 1928.10 / 131.61 / 164.96 / 181.35 / 60.05 | 1809 / 0 | 115776 / 0 | 115776 | 0 / 0 / 0 / 0 |
| B128 / C4 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 2.03 / 259.37 / 1965.13 / 2419.23 / 2990.62 / 61.69 | 125 / 0 | 16000 / 0 | 16000 | 0 / 0 / 0 / 0 |
| B128 / C4 | Veortex AVX-512 VNNI (AMX disabled) | 5.29 / 677.63 / 753.40 / 870.25 / 911.16 / 60.45 | 320 / 0 | 40960 / 0 | 40960 | 0 / 0 / 0 / 0 |
| B128 / C4 | Veortex Auto (AMX allowed) | 16.75 / 2144.32 / 241.71 / 304.56 / 335.57 / 60.23 | 1009 / 0 | 129152 / 0 | 129152 | 0 / 0 / 0 / 0 |

### No filter / payload

| B / C | Engine and scope | HTTP req/s / query/s / p50 / p95 / p99 / elapsed | Requests success/fail | Queries success/fail | Exact truth matches | 429 / transport / protocol / correctness errors |
|---:|---|---:|---:|---:|---:|---:|
| B1 / C64 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 54.08 / 54.08 / 1168.60 / 1375.51 / 1662.05 / 61.07 | 3303 / 0 | 3303 / 0 | 3303 | 0 / 0 / 0 / 0 |
| B1 / C64 | Veortex AVX-512 VNNI (AMX disabled) | 226.43 / 226.43 / 281.09 / 300.08 / 311.86 / 60.18 | 13627 / 0 | 13627 / 0 | 13627 | 0 / 0 / 0 / 0 |
| B1 / C64 | Veortex Auto (AMX allowed) | 753.17 / 753.17 / 83.85 / 96.86 / 108.24 / 60.07 | 45240 / 0 | 45240 / 0 | 45240 | 0 / 0 / 0 / 0 |
| B1 / C128 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 54.27 / 54.27 / 2329.92 / 2899.84 / 3734.77 / 62.19 | 3375 / 0 | 3375 / 0 | 3375 | 0 / 0 / 0 / 0 |
| B1 / C128 | Veortex AVX-512 VNNI (AMX disabled) | 439.35 / 439.35 / 290.42 / 316.45 / 366.33 / 60.20 | 26447 / 0 | 26447 / 0 | 26447 | 0 / 0 / 0 / 0 |
| B1 / C128 | Veortex Auto (AMX allowed) | 1350.94 / 1350.94 / 91.94 / 117.79 / 136.22 / 60.07 | 81151 / 0 | 81151 / 0 | 81151 | 0 / 0 / 0 / 0 |
| B64 / C4 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 4.00 / 255.84 / 982.57 / 1260.06 / 1418.92 / 60.79 | 243 / 0 | 15552 / 0 | 15552 | 0 / 0 / 0 / 0 |
| B64 / C4 | Veortex AVX-512 VNNI (AMX disabled) | 9.50 / 607.89 / 418.23 / 469.12 / 490.06 / 60.33 | 573 / 0 | 36672 / 0 | 36672 | 0 / 0 / 0 / 0 |
| B64 / C4 | Veortex Auto (AMX allowed) | 26.53 / 1697.95 / 147.84 / 186.96 / 211.18 / 60.12 | 1595 / 0 | 102080 / 0 | 102080 | 0 / 0 / 0 / 0 |
| B128 / C4 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 2.00 / 255.44 / 1989.36 / 2520.61 / 2965.36 / 61.63 | 123 / 0 | 15744 / 0 | 15744 | 0 / 0 / 0 / 0 |
| B128 / C4 | Veortex AVX-512 VNNI (AMX disabled) | 5.17 / 661.12 / 770.87 / 873.23 / 1000.88 / 60.41 | 312 / 0 | 39936 / 0 | 39936 | 0 / 0 / 0 / 0 |
| B128 / C4 | Veortex Auto (AMX allowed) | 15.16 / 1940.89 / 265.28 / 333.65 / 359.62 / 60.21 | 913 / 0 | 116864 / 0 | 116864 | 0 / 0 / 0 / 0 |

### Active only (~90%) / payload

| B / C | Engine and scope | HTTP req/s / query/s / p50 / p95 / p99 / elapsed | Requests success/fail | Queries success/fail | Exact truth matches | 429 / transport / protocol / correctness errors |
|---:|---|---:|---:|---:|---:|---:|
| B1 / C64 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 50.23 / 50.23 / 1268.74 / 1386.95 / 1677.05 / 61.20 | 3074 / 0 | 3074 / 0 | 3074 | 0 / 0 / 0 / 0 |
| B1 / C64 | Veortex AVX-512 VNNI (AMX disabled) | 220.53 / 220.53 / 288.02 / 314.75 / 331.97 / 60.07 | 13248 / 0 | 13248 / 0 | 13248 | 0 / 0 / 0 / 0 |
| B1 / C64 | Veortex Auto (AMX allowed) | 679.47 / 679.47 / 93.06 / 113.02 / 126.65 / 60.05 | 40803 / 0 | 40803 / 0 | 40803 | 0 / 0 / 0 / 0 |
| B1 / C128 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 47.99 / 47.99 / 2666.88 / 2974.24 / 3420.46 / 62.56 | 3002 / 0 | 3002 / 0 | 3002 | 0 / 0 / 0 / 0 |
| B1 / C128 | Veortex AVX-512 VNNI (AMX disabled) | 435.96 / 435.96 / 292.57 / 313.90 / 326.81 / 60.21 | 26249 / 0 | 26249 / 0 | 26249 | 0 / 0 / 0 / 0 |
| B1 / C128 | Veortex Auto (AMX allowed) | 1256.52 / 1256.52 / 98.13 / 129.97 / 149.43 / 60.07 | 75477 / 0 | 75477 / 0 | 75477 | 0 / 0 / 0 / 0 |
| B64 / C4 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 3.98 / 254.82 / 995.40 / 1293.28 / 1409.85 / 61.03 | 243 / 0 | 15552 / 0 | 15552 | 0 / 0 / 0 / 0 |
| B64 / C4 | Veortex AVX-512 VNNI (AMX disabled) | 9.16 / 586.23 / 429.73 / 532.95 / 588.20 / 60.37 | 553 / 0 | 35392 / 0 | 35392 | 0 / 0 / 0 / 0 |
| B64 / C4 | Veortex Auto (AMX allowed) | 25.07 / 1604.43 / 157.52 / 192.18 / 208.10 / 60.11 | 1507 / 0 | 96448 / 0 | 96448 | 0 / 0 / 0 / 0 |
| B128 / C4 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 1.99 / 254.83 / 2004.97 / 2404.76 / 2658.87 / 61.78 | 123 / 0 | 15744 / 0 | 15744 | 0 / 0 / 0 / 0 |
| B128 / C4 | Veortex AVX-512 VNNI (AMX disabled) | 5.20 / 665.94 / 767.69 / 851.02 / 930.17 / 60.55 | 315 / 0 | 40320 / 0 | 40320 | 0 / 0 / 0 / 0 |
| B128 / C4 | Veortex Auto (AMX allowed) | 14.43 / 1847.66 / 275.87 / 352.50 / 385.05 / 60.20 | 869 / 0 | 111232 / 0 | 111232 | 0 / 0 / 0 / 0 |

### Active + position exclusion (~9%) / payload

| B / C | Engine and scope | HTTP req/s / query/s / p50 / p95 / p99 / elapsed | Requests success/fail | Queries success/fail | Exact truth matches | 429 / transport / protocol / correctness errors |
|---:|---|---:|---:|---:|---:|---:|
| B1 / C64 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 119.30 / 119.30 / 534.13 / 601.67 / 669.96 / 60.47 | 7214 / 0 | 7214 / 0 | 7214 | 0 / 0 / 0 / 0 |
| B1 / C64 | Veortex AVX-512 VNNI (AMX disabled) | 966.18 / 966.18 / 65.98 / 77.36 / 86.69 / 60.01 | 57984 / 0 | 57984 / 0 | 57984 | 0 / 0 / 0 / 0 |
| B1 / C64 | Veortex Auto (AMX allowed) | 1171.11 / 1171.11 / 54.61 / 65.48 / 70.62 / 60.00 | 70272 / 0 | 70272 / 0 | 70272 | 0 / 0 / 0 / 0 |
| B1 / C128 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 120.32 / 120.32 / 1057.46 / 1261.05 / 1473.20 / 60.98 | 7337 / 0 | 7337 / 0 | 7337 | 0 / 0 / 0 / 0 |
| B1 / C128 | Veortex AVX-512 VNNI (AMX disabled) | 1720.58 / 1720.58 / 74.97 / 97.94 / 107.50 / 60.05 | 103329 / 0 | 103329 / 0 | 103329 | 0 / 0 / 0 / 0 |
| B1 / C128 | Veortex Auto (AMX allowed) | 1997.98 / 1997.98 / 63.85 / 90.96 / 104.65 / 60.03 | 119943 / 0 | 119943 / 0 | 119943 | 0 / 0 / 0 / 0 |
| B64 / C4 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 14.21 / 909.52 / 281.15 / 346.82 / 386.55 / 60.23 | 856 / 0 | 54784 / 0 | 54784 | 0 / 0 / 0 / 0 |
| B64 / C4 | Veortex AVX-512 VNNI (AMX disabled) | 34.27 / 2193.04 / 115.87 / 137.37 / 146.61 / 60.12 | 2060 / 0 | 131840 / 0 | 131840 | 0 / 0 / 0 / 0 |
| B64 / C4 | Veortex Auto (AMX allowed) | 38.70 / 2477.01 / 102.80 / 122.52 / 133.21 / 60.07 | 2325 / 0 | 148800 / 0 | 148800 | 0 / 0 / 0 / 0 |
| B128 / C4 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 7.06 / 903.89 / 565.16 / 685.52 / 733.47 / 60.47 | 427 / 0 | 54656 / 0 | 54656 | 0 / 0 / 0 / 0 |
| B128 / C4 | Veortex AVX-512 VNNI (AMX disabled) | 22.65 / 2899.02 / 175.45 / 215.94 / 237.82 / 60.14 | 1362 / 0 | 174336 / 0 | 174336 | 0 / 0 / 0 / 0 |
| B128 / C4 | Veortex Auto (AMX allowed) | 26.20 / 3353.80 / 151.10 / 184.37 / 202.46 / 60.11 | 1575 / 0 | 201600 / 0 | 201600 | 0 / 0 / 0 / 0 |

## Rejected fresh rows

No fresh timing row was rejected.

Independent accuracy: 8/8 fresh runs passed. Each recorded 1,024-query check is bound to its saved report bytes, exact category manifest and F32 oracle; the score tolerance is 1e-6 from the pinned checker. Failed query indices remain in JSON diagnostics. Per-node ring gates require each node's submitted/completed delta to equal warmup query members plus successful timed query members, with zero total fallback and HNSW calls. All eleven per-node fallback-reason counters are separately recorded and validated; their values are diagnostics and are not treated as disjoint HTTP failures. AVX rows prove VNNI-positive/AMX-zero on each node; Auto rows prove AMX work on each node. CPU evidence requires active work and each sampled thread's full three-CPU mask.

Per-node stage work and queue-wait counter deltas, plus their three-node means, are retained as diagnostics in JSON and CSV. Stage and wait totals can overlap; they are not additive measures of critical-path latency and do not identify a root cause by themselves.

Original-container restoration healthy: False; immutable lower metadata unchanged: False; overlays removed before restart: False; cleanup errors: 0.

The historical native comparison is cross-run, not a concurrent native arm. Builds use unmatched compiler flags; each cell was measured once in a fixed sequence on a shared VM. These are selected load points, not maximum capacity, confidence intervals, or long-duration stability claims. Curated outputs omit raw query bodies, client reports, credentials, and runtime environment values.

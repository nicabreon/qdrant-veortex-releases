# Native Qdrant 1.20 vs Veortex: shared three-CPU SQ8 comparison

Revision date: 10 November 2026 (WIB). This report adds the fresh matched-allocation campaign; older documents and results remain unchanged.

Campaign `shared3cpu-20261110t021202z` finished 2026-11-10T03:11:51.410458+00:00; receipt SHA-256 `988be53eed5dc07e605937a786aa5b5fc12de3cc96500dda46b1b627892b423c`.

**Coverage:** 48/48 rows accepted; 0 recorded rows rejected. All 48 cells are present; no missing cell is estimated.

Three Docker nodes each shared a disjoint three-CPU mask, with no per-thread pinning. The historical fixture has 3 million 512D FP32 cosine vectors, SQ8 flat search, three one-million-point shards, replication factor 1, and HNSW disabled. Metadata exists in all four categories. Every query returns Top10; each category has 1,024 fixed test queries and up to 12 rerank candidates per segment. The fixture was documented as Gaussian, but its original gallery generation seed is unknown; the campaign reuses the stored fixture and pinned independent FP32 oracle.

Each cell used 16 warm-up requests followed by a 60-second dispatch window and final drain. HTTP RPS = successful_requests / elapsed; query QPS = successful_queries / elapsed. Both denominators include final drain. Latency percentiles cover validated measured responses. Native supports VNNI, but its ISA path was not instrumented; Veortex AVX512 rows prove AMX-zero/VNNI-positive per node, and Auto rows prove positive AMX calls per node.

B128 is not a 128-slot continuous ring: compatible B1 and B2..64 requests enter the ring, whose fast-join capacity is 64 per worker. B128 follows the direct batched path and is split into chunks of 96+32. Batch-size comparisons therefore include this routing difference. Three available CPUs are a resource budget, not a claim that every load shape saturates all three.

The common Go client passed 21 local fixture checks; these checks validate client behavior, not engine accuracy. Independent engine accuracy passed 12 runs of 1,024 queries each, with ordered Top10 IDs and scores within 1e-6. Compiler flags are unmatched. This is a fresh end-to-end comparison under the matched three-CPU allocation, not an isolated kernel benchmark. No engine source change or build was made for this campaign.

Arm order was fixed: native, then forced AVX512 VNNI, then Auto. Each cell was measured once on the shared VM; temporal host variation and unmatched builds remain confounders. These selected load points do not establish maximum capacity, confidence intervals, or long-duration stability.

All recorded rows, including rejected rows and curated CPU/ISA evidence, are in JSON and CSV. CPU worker counts are reported as observed; three active workers are not required for every concurrency shape. Full private logs, configs, credentials, and raw reports are not published.

## No filter / no payload

| B | C | Backend | HTTP req/s | Query/s | p50 / p95 / p99 ms | Success / failed | Elapsed s |
|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | 64 | Qdrant native 1.20 | 55.43 | 55.43 | 1137.39 / 1546.88 / 1881.56 | 3387 / 0 | 61.11 |
| 1 | 64 | Veortex AVX512 VNNI (AMX disabled) | 235.36 | 235.36 | 271.43 / 282.58 / 290.03 | 14144 / 0 | 60.10 |
| 1 | 64 | Veortex Auto (AMX allowed) | 633.04 | 633.04 | 98.52 / 115.34 / 129.80 | 38021 / 0 | 60.06 |
| 1 | 128 | Qdrant native 1.20 | 55.71 | 55.71 | 2280.24 / 2461.91 / 2854.50 | 3464 / 0 | 62.17 |
| 1 | 128 | Veortex AVX512 VNNI (AMX disabled) | 453.32 | 453.32 | 282.94 / 293.98 / 301.96 | 27299 / 0 | 60.22 |
| 1 | 128 | Veortex Auto (AMX allowed) | 1179.48 | 1179.48 | 108.01 / 120.30 / 134.03 | 70855 / 0 | 60.07 |
| 64 | 4 | Qdrant native 1.20 | 4.02 | 257.33 | 986.82 / 1078.83 / 1261.08 | 245 / 0 | 60.93 |
| 64 | 4 | Veortex AVX512 VNNI (AMX disabled) | 10.82 | 692.62 | 368.34 / 389.76 / 431.42 | 652 / 0 | 60.25 |
| 64 | 4 | Veortex Auto (AMX allowed) | 27.03 | 1730.13 | 148.03 / 159.16 / 170.70 | 1625 / 0 | 60.11 |
| 128 | 4 | Qdrant native 1.20 | 2.03 | 259.37 | 1965.13 / 2419.23 / 2990.62 | 125 / 0 | 61.69 |
| 128 | 4 | Veortex AVX512 VNNI (AMX disabled) | 4.42 | 566.16 | 902.37 / 983.81 / 1164.58 | 269 / 0 | 60.82 |
| 128 | 4 | Veortex Auto (AMX allowed) | 8.70 | 1113.35 | 452.01 / 567.25 / 616.24 | 525 / 0 | 60.36 |
## No filter / payload

| B | C | Backend | HTTP req/s | Query/s | p50 / p95 / p99 ms | Success / failed | Elapsed s |
|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | 64 | Qdrant native 1.20 | 54.08 | 54.08 | 1168.60 / 1375.51 / 1662.05 | 3303 / 0 | 61.07 |
| 1 | 64 | Veortex AVX512 VNNI (AMX disabled) | 230.54 | 230.54 | 276.34 / 284.94 / 321.45 | 13888 / 0 | 60.24 |
| 1 | 64 | Veortex Auto (AMX allowed) | 618.87 | 618.87 | 101.16 / 117.16 / 123.45 | 37167 / 0 | 60.06 |
| 1 | 128 | Qdrant native 1.20 | 54.27 | 54.27 | 2329.92 / 2899.84 / 3734.77 | 3375 / 0 | 62.19 |
| 1 | 128 | Veortex AVX512 VNNI (AMX disabled) | 458.51 | 458.51 | 280.70 / 296.13 / 302.48 | 27611 / 0 | 60.22 |
| 1 | 128 | Veortex Auto (AMX allowed) | 1175.70 | 1175.70 | 108.27 / 121.10 / 132.50 | 70633 / 0 | 60.08 |
| 64 | 4 | Qdrant native 1.20 | 4.00 | 255.84 | 982.57 / 1260.06 / 1418.92 | 243 / 0 | 60.79 |
| 64 | 4 | Veortex AVX512 VNNI (AMX disabled) | 10.43 | 667.52 | 383.11 / 407.83 / 441.04 | 628 / 0 | 60.21 |
| 64 | 4 | Veortex Auto (AMX allowed) | 24.81 | 1587.62 | 159.46 / 181.91 / 216.86 | 1491 / 0 | 60.11 |
| 128 | 4 | Qdrant native 1.20 | 2.00 | 255.44 | 1989.36 / 2520.61 / 2965.36 | 123 / 0 | 61.63 |
| 128 | 4 | Veortex AVX512 VNNI (AMX disabled) | 4.40 | 563.65 | 905.41 / 1073.60 / 1137.30 | 268 / 0 | 60.86 |
| 128 | 4 | Veortex Auto (AMX allowed) | 8.15 | 1042.93 | 478.02 / 627.64 / 713.04 | 492 / 0 | 60.38 |
## Active only (~90%) / payload

| B | C | Backend | HTTP req/s | Query/s | p50 / p95 / p99 ms | Success / failed | Elapsed s |
|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | 64 | Qdrant native 1.20 | 50.23 | 50.23 | 1268.74 / 1386.95 / 1677.05 | 3074 / 0 | 61.20 |
| 1 | 64 | Veortex AVX512 VNNI (AMX disabled) | 233.39 | 233.39 | 272.94 / 285.58 / 292.03 | 14016 / 0 | 60.05 |
| 1 | 64 | Veortex Auto (AMX allowed) | 405.69 | 405.69 | 157.45 / 167.81 / 176.07 | 24379 / 0 | 60.09 |
| 1 | 128 | Qdrant native 1.20 | 47.99 | 47.99 | 2666.88 / 2974.24 / 3420.46 | 3002 / 0 | 62.56 |
| 1 | 128 | Veortex AVX512 VNNI (AMX disabled) | 451.37 | 451.37 | 282.46 / 295.64 / 329.96 | 27194 / 0 | 60.25 |
| 1 | 128 | Veortex Auto (AMX allowed) | 772.31 | 772.31 | 165.16 / 181.55 / 200.56 | 46436 / 0 | 60.13 |
| 64 | 4 | Qdrant native 1.20 | 3.98 | 254.82 | 995.40 / 1293.28 / 1409.85 | 243 / 0 | 61.03 |
| 64 | 4 | Veortex AVX512 VNNI (AMX disabled) | 10.45 | 668.87 | 382.50 / 414.90 / 430.88 | 630 / 0 | 60.28 |
| 64 | 4 | Veortex Auto (AMX allowed) | 17.53 | 1121.61 | 227.12 / 252.65 / 302.22 | 1055 / 0 | 60.20 |
| 128 | 4 | Qdrant native 1.20 | 1.99 | 254.83 | 2004.97 / 2404.76 / 2658.87 | 123 / 0 | 61.78 |
| 128 | 4 | Veortex AVX512 VNNI (AMX disabled) | 4.26 | 544.98 | 936.56 / 1155.72 / 1227.69 | 259 / 0 | 60.83 |
| 128 | 4 | Veortex Auto (AMX allowed) | 6.32 | 809.53 | 630.67 / 746.46 / 781.68 | 383 / 0 | 60.56 |
## Active + position exclusion (~9%) / payload

| B | C | Backend | HTTP req/s | Query/s | p50 / p95 / p99 ms | Success / failed | Elapsed s |
|---:|---:|---|---:|---:|---:|---:|---:|
| 1 | 64 | Qdrant native 1.20 | 119.30 | 119.30 | 534.13 / 601.67 / 669.96 | 7214 / 0 | 60.47 |
| 1 | 64 | Veortex AVX512 VNNI (AMX disabled) | 994.97 | 994.97 | 63.89 / 77.62 / 89.46 | 59712 / 0 | 60.01 |
| 1 | 64 | Veortex Auto (AMX allowed) | 1469.91 | 1469.91 | 47.80 / 62.47 / 67.80 | 88252 / 0 | 60.04 |
| 1 | 128 | Qdrant native 1.20 | 120.32 | 120.32 | 1057.46 / 1261.05 / 1473.20 | 7337 / 0 | 60.98 |
| 1 | 128 | Veortex AVX512 VNNI (AMX disabled) | 2235.34 | 2235.34 | 55.54 / 82.92 / 95.34 | 134299 / 0 | 60.08 |
| 1 | 128 | Veortex Auto (AMX allowed) | 2230.99 | 2230.99 | 57.88 / 78.26 / 86.84 | 133933 / 0 | 60.03 |
| 64 | 4 | Qdrant native 1.20 | 14.21 | 909.52 | 281.15 / 346.82 / 386.55 | 856 / 0 | 60.23 |
| 64 | 4 | Veortex AVX512 VNNI (AMX disabled) | 41.59 | 2661.53 | 95.45 / 109.68 / 120.75 | 2498 / 0 | 60.07 |
| 64 | 4 | Veortex Auto (AMX allowed) | 48.27 | 3089.46 | 82.17 / 95.59 / 105.54 | 2897 / 0 | 60.01 |
| 128 | 4 | Qdrant native 1.20 | 7.06 | 903.89 | 565.16 / 685.52 / 733.47 | 427 / 0 | 60.47 |
| 128 | 4 | Veortex AVX512 VNNI (AMX disabled) | 20.85 | 2668.72 | 189.06 / 239.58 / 268.81 | 1254 / 0 | 60.15 |
| 128 | 4 | Veortex Auto (AMX allowed) | 23.90 | 3059.49 | 166.68 / 207.96 / 227.75 | 1437 / 0 | 60.12 |

## Observed CPU use: no filter / no payload

These are whole-process CPU equivalents per node, including compute and support work, averaged over the runtime observer interval (warm-up plus measurement/drain). A value of 2.0 means two CPUs' runtime per elapsed second; it is not an instruction-level compute measurement. All three CPUs were available to every thread. The per-node values for every category are retained in JSON.

| B | C | Backend | Node 0 CPU eq. | Node 1 CPU eq. | Node 2 CPU eq. |
|---:|---:|---|---:|---:|---:|
| 1 | 64 | Qdrant native 1.20 | 2.93 | 2.93 | 2.72 |
| 1 | 64 | Veortex AVX512 VNNI (AMX disabled) | 1.09 | 1.01 | 1.03 |
| 1 | 64 | Veortex Auto (AMX allowed) | 1.23 | 1.09 | 1.07 |
| 1 | 128 | Qdrant native 1.20 | 2.93 | 2.90 | 2.77 |
| 1 | 128 | Veortex AVX512 VNNI (AMX disabled) | 2.21 | 2.05 | 2.05 |
| 1 | 128 | Veortex Auto (AMX allowed) | 2.40 | 2.10 | 2.09 |
| 64 | 4 | Qdrant native 1.20 | 2.87 | 2.85 | 2.78 |
| 64 | 4 | Veortex AVX512 VNNI (AMX disabled) | 2.81 | 2.80 | 2.79 |
| 64 | 4 | Veortex Auto (AMX allowed) | 2.89 | 2.89 | 2.84 |
| 128 | 4 | Qdrant native 1.20 | 2.91 | 2.91 | 2.81 |
| 128 | 4 | Veortex AVX512 VNNI (AMX disabled) | 2.78 | 2.66 | 2.72 |
| 128 | 4 | Veortex Auto (AMX allowed) | 2.79 | 2.81 | 2.73 |

## Rejected rows

No recorded row was rejected.

[JSON](./shared3-native-veortex-20261110.json) · [CSV](./shared3-native-veortex-20261110.csv)

# Recorded V45 results — 2 November 2026

These are selected historical results from the frozen binary distributed by this repository. No retest is implied. All rows use B1 HTTP requests returning Top10, a reused 1,024-query corpus, 3M × 512D vectors, three Docker nodes on one VM, and three vCPUs per node (one scan CPU plus two support CPUs). C160 closed-loop; 60-second dispatch, actual elapsed includes drain. Metadata exists in every category. No HNSW.

| Mode | Category | HTTP RPS | p95 ms | p99 ms | Successful | Failed |
|---|---|---:|---:|---:|---:|---:|
| sq8 | unfiltered_no_payload | 1027.64 | 205.86 | 228.57 | 61,819 | 0 |
| sq8 | unfiltered_payload | 1016.15 | 209.33 | 226.07 | 61,086 | 0 |
| sq8 | active_only | 1007.56 | 200.44 | 219.90 | 60,579 | 0 |
| sq8 | active_position_exclude | 2773.20 | 89.84 | 110.78 | 166,488 | 0 |
| sq8 | unfiltered_no_payload | 1009.42 | 204.10 | 220.44 | 60,677 | 0 |
| tq2 | unfiltered_no_payload | 809.15 | 263.34 | 287.74 | 48,640 | 0 |
| tq2 | unfiltered_payload | 854.69 | 243.90 | 276.82 | 51,377 | 0 |
| tq2 | active_only | 795.30 | 242.76 | 281.60 | 47,816 | 0 |
| tq2 | active_position_exclude | 1280.18 | 194.69 | 206.22 | 76,892 | 0 |
| tq2 | unfiltered_no_payload | 836.02 | 256.56 | 278.87 | 50,254 | 0 |
| tq4 | unfiltered_no_payload | 816.28 | 245.68 | 258.67 | 49,131 | 0 |
| tq4 | unfiltered_payload | 797.58 | 250.46 | 263.29 | 47,968 | 0 |
| tq4 | active_only | 778.18 | 257.19 | 291.34 | 46,776 | 0 |
| tq4 | active_position_exclude | 2292.10 | 102.27 | 123.34 | 137,657 | 0 |
| tq4 | unfiltered_no_payload | 831.78 | 237.94 | 257.32 | 50,027 | 0 |

Each category passed 1,024 initial ordered Top10 checks against cached exact-FP32 results. All timed successful responses matched that same corpus; this is empirical coverage, not a universal 100% recall guarantee. The last unfiltered row is a repeat.

Candidate counts per populated segment: SQ8 12, TQ2 1,767, TQ4 40. These are sufficient on these conversions; current minima are not established. TQ2/TQ4 have not reached SQ8 throughput in this cohort.

Narrow-filter rows inspect a smaller eligible subset and should not be presented as unfiltered 3M full-scan throughput. Search covers all three shards; all containers share a single VM. C160 results do not establish maximum throughput, single-request latency, or long-duration stability.

The historical gallery/query generator seed is not preserved with this evidence. The fresh seeded generator in `reproduce/` reproduces the protocol, not the historical dataset bytes or performance numbers. Use the same original snapshot and queries for a direct historical rerun.

See the adjacent JSON and CSV for exact values, source/ELF/query digests, scope limits, and per-profile receipt digests. Native upstream 1.20 measurements, when available, are reported separately with their own binary and runtime controls.

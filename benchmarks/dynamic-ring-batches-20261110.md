# Veortex dynamic-ring batch comparison

Revision date: 10 November 2026 (WIB). This focused report compares the dynamic-ring candidate with the prior shared-three-CPU measurements; earlier benchmark reports remain unchanged.

Campaign `dynamic-ring-20261110t050818z` finished 2026-11-10T05:29:42.872053+00:00; receipt SHA-256 `7e6117461b2d4810e6ae415b1755e8627103be853c08629403cf13ffedeff165`.

**Coverage:** 16/16 timing rows accepted. Eight independent accuracy runs each passed 1,024/1,024 queries with ordered Top10 IDs and FP32 scores within 1e-6. Original containers were restored healthy, overlays were removed first, and immutable lower metadata was unchanged.

Both comparisons used three shared CPUs per node, no per-thread pinning, the same validated Go client, the same 3M × 512D SQ8 fixture, and the same category/B/C cell. HTTP RPS is successful HTTP requests / elapsed including final drain; query/s is successful queries / elapsed, so batch size changes their relationship. Latencies cover the whole validated HTTP response. The engine changed from the prior a1 binary to candidate source commit `1bd74d911`; this is an end-to-end batch-path comparison, not isolated kernel timing.

Rows are matched by backend, category, batch size, and concurrency against the already-published prior shared-three-CPU report. The prior campaign documented B1 and compatible B2–64 as continuous-ring traffic, while B128 used a direct 96+32 path. This report requires per-node submitted/completed ring-query deltas to equal measured plus warmup queries, with zero fallback and zero HNSW calls.

| Category | Backend | B/C | Prior → candidate HTTP RPS (change) | Prior → candidate query/s | Prior → candidate p95 / p99 ms |
|---|---|---:|---:|---:|---:|
| No filter / no payload | Veortex AVX512 VNNI | 64/4 | 10.82 → 10.63 (-1.8%) | 692.62 → 680.00 | 389.76/431.42 → 394.57/406.50 |
| No filter / no payload | Veortex AVX512 VNNI | 128/4 | 4.42 → 5.70 (+28.9%) | 566.16 → 729.62 | 983.81/1164.58 → 792.20/829.06 |
| No filter / payload | Veortex AVX512 VNNI | 64/4 | 10.43 → 10.47 (+0.4%) | 667.52 → 669.94 | 407.83/441.04 → 406.09/416.52 |
| No filter / payload | Veortex AVX512 VNNI | 128/4 | 4.40 → 5.59 (+26.9%) | 563.65 → 715.03 | 1073.60/1137.30 → 805.45/867.66 |
| Active only (~90%) / payload | Veortex AVX512 VNNI | 64/4 | 10.45 → 10.43 (-0.2%) | 668.87 → 667.78 | 414.90/430.88 → 410.32/495.51 |
| Active only (~90%) / payload | Veortex AVX512 VNNI | 128/4 | 4.26 → 5.58 (+31.0%) | 544.98 → 713.89 | 1155.72/1227.69 → 819.31/848.79 |
| Active + position exclusion (~9%) / payload | Veortex AVX512 VNNI | 64/4 | 41.59 → 40.82 (-1.8%) | 2661.53 → 2612.66 | 109.68/120.75 → 110.11/118.84 |
| Active + position exclusion (~9%) / payload | Veortex AVX512 VNNI | 128/4 | 20.85 → 26.64 (+27.8%) | 2668.72 → 3410.03 | 239.58/268.81 → 184.94/200.58 |
| No filter / no payload | Veortex Auto | 64/4 | 27.03 → 26.26 (-2.9%) | 1730.13 → 1680.82 | 159.16/170.70 → 177.01/186.25 |
| No filter / no payload | Veortex Auto | 128/4 | 8.70 → 15.71 (+80.7%) | 1113.35 → 2011.34 | 567.25/616.24 → 296.36/320.28 |
| No filter / payload | Veortex Auto | 64/4 | 24.81 → 25.11 (+1.2%) | 1587.62 → 1606.80 | 181.91/216.86 → 172.26/179.05 |
| No filter / payload | Veortex Auto | 128/4 | 8.15 → 14.51 (+78.1%) | 1042.93 → 1857.73 | 627.64/713.04 → 314.71/334.88 |
| Active only (~90%) / payload | Veortex Auto | 64/4 | 17.53 → 17.68 (+0.9%) | 1121.61 → 1131.82 | 252.65/302.22 → 246.26/255.76 |
| Active only (~90%) / payload | Veortex Auto | 128/4 | 6.32 → 10.24 (+61.9%) | 809.53 → 1310.41 | 746.46/781.68 → 437.70/467.69 |
| Active + position exclusion (~9%) / payload | Veortex Auto | 64/4 | 48.27 → 47.60 (-1.4%) | 3089.46 → 3046.10 | 95.59/105.54 → 96.09/104.87 |
| Active + position exclusion (~9%) / payload | Veortex Auto | 128/4 | 23.90 → 31.68 (+32.5%) | 3059.49 → 4054.58 | 207.96/227.75 → 152.13/166.58 |

## Historical native reference — Qdrant native 1.20 — prior-run reference only (not rerun)

These eight Native Qdrant 1.20 rows are copied from the prior H0 campaign for context. Native was not measured again in the dynamic-ring campaign.

| Category | B/C | HTTP RPS | Query/s | p95 / p99 ms |
|---|---:|---:|---:|---:|
| No filter / no payload | 64/4 | 4.02 | 257.33 | 1078.83 / 1261.08 |
| No filter / no payload | 128/4 | 2.03 | 259.37 | 2419.23 / 2990.62 |
| No filter / payload | 64/4 | 4.00 | 255.84 | 1260.06 / 1418.92 |
| No filter / payload | 128/4 | 2.00 | 255.44 | 2520.61 / 2965.36 |
| Active only (~90%) / payload | 64/4 | 3.98 | 254.82 | 1293.28 / 1409.85 |
| Active only (~90%) / payload | 128/4 | 1.99 | 254.83 | 2404.76 / 2658.87 |
| Active + position exclusion (~9%) / payload | 64/4 | 14.21 | 909.52 | 346.82 / 386.55 |
| Active + position exclusion (~9%) / payload | 128/4 | 7.06 | 903.89 | 685.52 / 733.47 |

## Method and scope

Current rows used the candidate dynamic-ring engine with three ring workers, separate TopK disabled, a 2 GiB queued-query budget, and three shared CPUs per node. Runtime thread masks and per-node CPU work were observed during every row. The AVX512 VNNI tier required AMX calls to remain zero and VNNI calls positive on all nodes; Auto required positive AMX calls on all nodes.

The prior measurements are reused from the published shared-three-CPU report and were not rerun. This leaves different engine binaries and run times as comparison factors; the result supports only the matched end-to-end workload observations shown here. It does not establish that the new route is faster for all batch sizes or filters.

All 16 current rows have zero request/query errors, HTTP 429s, transport failures/timeouts, protocol errors, and correctness failures; every successful query matched exact client-side Top10 truth. Ring proof is per node and includes warmups. The historical fixture has unknown original gallery-generation seed, but both campaigns use the same stored fixture and independent FP32 oracle.

The shared-CPU observer is version 2. It retains original process utilization and interval tick values, and separately verifies positive same-TID/starttime/stable-name scheduler-runtime deltas within the row window, or strictly in-window newborn-thread runtime. The read cadence remains 200 ms and no extra proc reads were added. The observer and pure evidence validator are SHA-pinned in this report; 24 offline cases verified valid evidence and rejected wrong masks, stale lifetime runtime, identity changes, and invalid interval arithmetic.

The [archived initial sampling attempt](./dynamic-ring-batches-initial-sampling-20261110.md) retained six accepted rows and one rejected CPU-attribution row. That rejected row passed correctness and ring/ISA checks; the shared wrapper had discarded sub-jiffy scheduler-runtime evidence. All 16 final rows were measured afresh with the same corrected observer and unchanged candidate ELF. No failed row is promoted into this final results table.

Across these selected cells, B128 query throughput increased by 26.9–80.7% versus the matched earlier paths. B64 changes ranged from -2.9% to +1.2%; the one-pass measurements do not establish statistical significance for those smaller changes. B1 filter regressions, multicore scaling efficiency, additional shard layouts, and TQ2/TQ4 performance remain separate work.

This candidate ELF is not included in the currently published V45.1 binary release. Its full SHA is recorded below; the earlier release and its historical routing limitations remain unchanged. Native compiler flags remain unmatched, and the reused native rows are context rather than a fresh native run.

Source commit `1bd74d911fa8c61f962d5b22fbd4ac2951102a80`; engine SHA-256 `a493502c9538e10e66637993432e1d619c13004368c78c423f9041ff6be3d607`; common client SHA-256 `5477653066b11acf0ce1f53545f6bd98aad9175ed3c4072a89b051298e05cde0`.

[JSON](./dynamic-ring-batches-20261110.json) · [CSV](./dynamic-ring-batches-20261110.csv)

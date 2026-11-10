# One pinned search CPU + two support CPUs vs three shared CPUs

This is an overall CPU policy comparison across historical accepted runs and the completed three-shared-CPU campaign. Each entry pairs the same batch size, concurrency, engine mode, and category. Throughput ratios are new/old; latency ratios are also new/old, so a value below 1.00× means lower latency.

## Primary comparisons

### Native Qdrant 1.20 — Native, B1/C128

| Category | HTTP RPS old → new (×) | Queries/s old → new (×) | p95 ms old → new (×) | p99 ms old → new (×) | Old process CPU | New process CPU, cores/node |
|---|---:|---:|---:|---:|---|---:|
| Unfiltered, no payload | 22.17 → 55.71 (2.51×) | 22.17 → 55.71 (2.51×) | 7,585.02 → 2,461.91 (0.32×) | 8,035.43 → 2,854.50 (0.36×) | unavailable (observer was role/affinity only) | 2.93, 2.90, 2.77 |
| Unfiltered, payload | 20.16 → 54.27 (2.69×) | 20.16 → 54.27 (2.69×) | 9,682.57 → 2,899.84 (0.30×) | 10,156.64 → 3,734.77 (0.37×) | unavailable (observer was role/affinity only) | 2.93, 2.92, 2.93 |
| Active only | 18.02 → 47.99 (2.66×) | 18.02 → 47.99 (2.66×) | 9,800.18 → 2,974.24 (0.30×) | 10,874.81 → 3,420.46 (0.31×) | unavailable (observer was role/affinity only) | 2.90, 2.88, 2.93 |
| Active + position exclude | 40.72 → 120.32 (2.96×) | 40.72 → 120.32 (2.96×) | 4,761.38 → 1,261.05 (0.26×) | 5,066.22 → 1,473.20 (0.29×) | unavailable (observer was role/affinity only) | 2.93, 2.91, 2.90 |

### Native Qdrant 1.20 — Native, B64/C4

| Category | HTTP RPS old → new (×) | Queries/s old → new (×) | p95 ms old → new (×) | p99 ms old → new (×) | Old process CPU | New process CPU, cores/node |
|---|---:|---:|---:|---:|---|---:|
| Unfiltered, no payload | 1.78 → 4.02 (2.25×) | 114.18 → 257.33 (2.25×) | 2,836.55 → 1,078.83 (0.38×) | 2,853.36 → 1,261.08 (0.44×) | unavailable (observer was role/affinity only) | 2.87, 2.85, 2.78 |
| Unfiltered, payload | 1.80 → 4.00 (2.22×) | 115.17 → 255.84 (2.22×) | 2,822.78 → 1,260.06 (0.45×) | 3,210.61 → 1,418.92 (0.44×) | unavailable (observer was role/affinity only) | 2.84, 2.85, 2.80 |
| Active only | 1.88 → 3.98 (2.12×) | 120.25 → 254.82 (2.12×) | 2,685.54 → 1,293.28 (0.48×) | 2,737.10 → 1,409.85 (0.52×) | unavailable (observer was role/affinity only) | 2.86, 2.80, 2.76 |
| Active + position exclude | 8.07 → 14.21 (1.76×) | 516.40 → 909.52 (1.76×) | 631.78 → 346.82 (0.55×) | 653.65 → 386.55 (0.59×) | unavailable (observer was role/affinity only) | 2.88, 2.82, 2.85 |

### Our Veortex V45.1 — Auto, B1/C128

| Category | HTTP RPS old → new (×) | Queries/s old → new (×) | p95 ms old → new (×) | p99 ms old → new (×) | Old process CPU | New process CPU, cores/node |
|---|---:|---:|---:|---:|---|---:|
| Unfiltered, no payload | 898.94 → 1,179.48 (1.31×) | 898.94 → 1,179.48 (1.31×) | 198.41 → 120.30 (0.61×) | 211.32 → 134.03 (0.63×) | unavailable (observer was role/affinity only) | 2.40, 2.10, 2.09 |
| Unfiltered, payload | 904.11 → 1,175.70 (1.30×) | 904.11 → 1,175.70 (1.30×) | 172.72 → 121.10 (0.70×) | 185.62 → 132.50 (0.71×) | unavailable (observer was role/affinity only) | 2.56, 2.15, 2.14 |
| Active only | 892.19 → 772.31 (0.87×) | 892.19 → 772.31 (0.87×) | 184.75 → 181.55 (0.98×) | 192.74 → 200.56 (1.04×) | unavailable (observer was role/affinity only) | 2.47, 2.12, 2.12 |
| Active + position exclude | 3,139.32 → 2,230.99 (0.71×) | 3,139.32 → 2,230.99 (0.71×) | 56.35 → 78.26 (1.39×) | 69.97 → 86.84 (1.24×) | unavailable (observer was role/affinity only) | 2.47, 1.89, 1.90 |

### Our Veortex V45.1 — Auto, B64/C4

| Category | HTTP RPS old → new (×) | Queries/s old → new (×) | p95 ms old → new (×) | p99 ms old → new (×) | Old process CPU | New process CPU, cores/node |
|---|---:|---:|---:|---:|---|---:|
| Unfiltered, no payload | 15.59 → 27.03 (1.73×) | 997.60 → 1,730.13 (1.73×) | 307.46 → 159.16 (0.52×) | 320.49 → 170.70 (0.53×) | unavailable (observer was role/affinity only) | 2.89, 2.89, 2.84 |
| Unfiltered, payload | 13.98 → 24.81 (1.77×) | 894.44 → 1,587.62 (1.77×) | 342.98 → 181.91 (0.53×) | 354.04 → 216.86 (0.61×) | unavailable (observer was role/affinity only) | 2.86, 2.82, 2.78 |
| Active only | 15.18 → 17.53 (1.15×) | 971.73 → 1,121.61 (1.15×) | 317.63 → 252.65 (0.80×) | 330.22 → 302.22 (0.92×) | unavailable (observer was role/affinity only) | 2.73, 2.67, 2.74 |
| Active + position exclude | 45.25 → 48.27 (1.07×) | 2,895.74 → 3,089.46 (1.07×) | 110.04 → 95.59 (0.87×) | 121.89 → 105.54 (0.87×) | unavailable (observer was role/affinity only) | 2.48, 2.09, 2.18 |

### Our Veortex V45.1 — AVX-512 VNNI, B1/C128

| Category | HTTP RPS old → new (×) | Queries/s old → new (×) | p95 ms old → new (×) | p99 ms old → new (×) | Old process CPU | New process CPU, cores/node |
|---|---:|---:|---:|---:|---|---:|
| Unfiltered, no payload | 245.18 → 453.32 (1.85×) | 245.18 → 453.32 (1.85×) | 716.73 → 293.98 (0.41×) | 733.49 → 301.96 (0.41×) | unavailable (observer was role/affinity only) | 2.21, 2.05, 2.05 |
| Unfiltered, payload | 239.57 → 458.51 (1.91×) | 239.57 → 458.51 (1.91×) | 739.55 → 296.13 (0.40×) | 753.97 → 302.48 (0.40×) | unavailable (observer was role/affinity only) | 2.29, 2.07, 2.07 |
| Active only | 241.55 → 451.37 (1.87×) | 241.55 → 451.37 (1.87×) | 657.93 → 295.64 (0.45×) | 728.67 → 329.96 (0.45×) | unavailable (observer was role/affinity only) | 2.25, 2.05, 2.04 |
| Active + position exclude | 1,933.46 → 2,235.34 (1.16×) | 1,933.46 → 2,235.34 (1.16×) | 74.78 → 82.92 (1.11×) | 89.30 → 95.34 (1.07×) | unavailable (observer was role/affinity only) | 2.68, 2.09, 2.12 |

## Supplemental native B1/C64 comparison

The native binary matches exactly across the old and new arms. Veortex B1/C64 rows are excluded because the available historical matrix used a different Veortex build.

| Category | HTTP RPS old → new (×) | Queries/s old → new (×) | p95 ms old → new (×) | p99 ms old → new (×) | New process CPU, cores/node |
|---|---:|---:|---:|---:|---:|
| Unfiltered, no payload | 21.40 → 55.43 (2.59×) | 21.40 → 55.43 (2.59×) | 4,630.85 → 1,546.88 (0.33×) | 4,963.25 → 1,881.56 (0.38×) | 2.93, 2.93, 2.72 |
| Unfiltered, payload | 21.65 → 54.08 (2.50×) | 21.65 → 54.08 (2.50×) | 4,108.77 → 1,375.51 (0.33×) | 4,456.41 → 1,662.05 (0.37×) | 2.89, 2.91, 2.92 |
| Active only | 18.52 → 50.23 (2.71×) | 18.52 → 50.23 (2.71×) | 5,092.75 → 1,386.95 (0.27×) | 5,795.79 → 1,677.05 (0.29×) | 2.93, 2.91, 2.84 |
| Active + position exclude | 42.40 → 119.30 (2.81×) | 42.40 → 119.30 (2.81×) | 2,282.89 → 601.67 (0.26×) | 2,541.11 → 669.96 (0.26×) | 2.94, 2.86, 2.89 |

## Observed throughput changes

Across the 20 primary matched rows, HTTP RPS increased in 18, decreased in 2, and was unchanged in 0. Results vary by engine mode and category; they do not support a universal claim that three shared CPUs are faster.

| Arm | B/C | Categories with higher RPS | Categories with lower RPS |
|---|---:|---|---|
| Native Qdrant 1.20 — Native | B1/C128 | Unfiltered, no payload, Unfiltered, payload, Active only, Active + position exclude | none |
| Native Qdrant 1.20 — Native | B64/C4 | Unfiltered, no payload, Unfiltered, payload, Active only, Active + position exclude | none |
| Our Veortex V45.1 — Auto | B1/C128 | Unfiltered, no payload, Unfiltered, payload | Active only, Active + position exclude |
| Our Veortex V45.1 — Auto | B64/C4 | Unfiltered, no payload, Unfiltered, payload, Active only, Active + position exclude | none |
| Our Veortex V45.1 — AVX-512 VNNI | B1/C128 | Unfiltered, no payload, Unfiltered, payload, Active only, Active + position exclude | none |

Largest observed gain: Native Qdrant 1.20 Native B1/C128 Active + position exclude at 2.96× RPS.

Largest observed drop: Our Veortex V45.1 Auto B1/C128 Active + position exclude at 0.71× RPS.

### Open optimization item: Active only, Veortex Auto B1/C128

HTTP RPS is 892.19 → 772.31 (-13.44%). The historical and current rows use the same Veortex V45.1 binary. The root cause is not established: CPU role placement, separate TopK, and scheduling changed while the total three-CPU budget stayed the same.

Current whole-process CPU equivalents for this row are 2.471, 2.125, 2.121 cores on nodes 0–2. The configured three-worker limit does not establish saturation.

Next, isolate admission wait, ring wait, scan time, TopK/FP32 reranking, payload completion, and cross-node join under the same B1/C128 workload. Preserve the gains in other categories while investigating this regression.

### Open optimization item: Active + position exclude, Veortex Auto B1/C128

HTTP RPS is 3,139.32 → 2,230.99 (-28.93%). The historical and current rows use the same Veortex V45.1 binary. The root cause is not established: CPU role placement, separate TopK, and scheduling changed while the total three-CPU budget stayed the same.

Current whole-process CPU equivalents for this row are 2.472, 1.890, 1.902 cores on nodes 0–2. The configured three-worker limit does not establish saturation.

Next, isolate admission wait, ring wait, scan time, TopK/FP32 reranking, payload completion, and cross-node join under the same B1/C128 workload. Preserve the gains in other categories while investigating this regression.

## Conditions and limits

Both arms had a three-vCPU budget per node; the old total was three, not one. The old native arm pinned full search to one search CPU with two support CPUs. Old Veortex pinned scanning to one CPU; TopK, FP32 reranking, and payload work could also use the two support CPUs. The old phase permissions were asymmetric across engines. The new arm shares all three CPUs across every server phase: native uses `MAX_SEARCH_THREADS=3`; Veortex uses three ring workers and three Rayon threads, disables separate TopK, and sets no per-thread affinity. Current phase permissions use the full three-CPU mask symmetrically.

This comparison also changes Veortex TopK scheduling and its queued-query budget (640 MiB old, 2 GiB new); the Veortex queue setting does not apply to native Qdrant. The historical client binary was `9dab9e7f…`; the current campaign client is `54776530…`. Its Go main change is limited to the B128 allowlist and help text. The pinned query corpus SHA-256 begins `90c486` in both runs; manifests can differ because their comparison labels differ. Measurements ran at different times in fixed orders, without randomized ABBA repetitions. The native binary is unchanged (`5081…`); Veortex V45.1 is unchanged (`90d54…`) where selected. Native compiler flags are not matched to Veortex. Older 40–50× cross-engine throughput claims are not a compute-equivalent baseline because old CPU permissions differed by phase; these matched three-CPU RPS ratios supersede them for full-budget claims.

A 2.8–2.9× scan-only throughput gain is an optimization target that requires three busy scan workers and sufficient shared CPU/memory capacity. This campaign did not isolate 1-vs-3-worker scan throughput. Historical observers prove activity and affinity for named roles but do not measure whole-process CPU. The current evidence records end-to-end performance and whole-process CPU equivalents by node. The table leaves old CPU use unavailable instead of estimating it from partial role counters.

Every included row passed the exporter’s gates: accepted measurement, zero timed errors, exact ordered Top10 matches for all returned queries against FP32 truth, and 1,024/1,024 initial category checks. This is coverage of the fixed query corpus, not a universal recall claim.

New B128/C4 measurements have no historical same-workload counterpart in the approved sources and are therefore not assigned before/after ratios. Veortex B1/C64 is also omitted because the old matrix used a different Veortex binary.

Historical sources: `h2h-sq8-batch-20261109.json`, `h2h-sq8-admission-remediation-20261109.json`, and `sq8-avx512-vs-amx-20261110.json`. Current source: completed `shared3-native-veortex-20261110.json`.

# Native Qdrant 1.20 vs Veortex query/gallery — TQ4 B=1 Matrix (16 November 2026)

Campaign: `tq4-h2h-20261116t230240z` | Status: **`RUNNING`** (`59/135` accepted B1 cells) | Exported: `2026-11-16T23:43:35.828687+00:00`

- **Profile:** `TQ4` (`rescore=True`, `oversampling=4.0`, `QDRANT_VEORTEX_TQ_QUERY_BYTES=1`, `truth_mode=f32_exact`, 3 shared vCPUs/node, zero pinning)
- **Curated artifacts:** [JSON](tq4-query-gallery-20261116.json) | [CSV](tq4-query-gallery-20261116.csv)
- Each cell shows **`HTTP req/s; p95 / p99 ms`** (`pending` = not yet measured; zero interpolation).

## Accuracy & Oracle Gates (1,024 Queries / Category)

| Arm | Category | Round | Parity Passed | Exact FP32 Recall@10 |
|---|---|---|---:|---:|
| `native_120` | No filter / no payload | b1 | 1024/1024 (fail=0) | 1.000000 |
| `native_120` | Payload only | b1 | 1024/1024 (fail=0) | 1.000000 |
| `native_120` | Active filter / no payload (90%) | b1 | 1024/1024 (fail=0) | 1.000000 |
| `native_120` | Active filter + payload (90%) | b1 | 1024/1024 (fail=0) | 1.000000 |
| `native_120` | Active + position + exclusion / payload (~9%) | b1 | 1024/1024 (fail=0) | 1.000000 |
| `veortex_query` | No filter / no payload | b1 | 1024/1024 (fail=0) | 1.000000 |
| `veortex_query` | Payload only | b1 | 1024/1024 (fail=0) | 1.000000 |
| `veortex_query` | Active filter / no payload (90%) | b1 | 1024/1024 (fail=0) | 1.000000 |
| `veortex_query` | Active filter + payload (90%) | b1 | 1024/1024 (fail=0) | 1.000000 |
| `veortex_query` | Active + position + exclusion / payload (~9%) | b1 | 1024/1024 (fail=0) | 1.000000 |

### No filter / no payload

| Concurrency | Native 1.20 (`native_120`) | Veortex `query-split` | Veortex `gallery-split` |
|---|---:|---:|---:|
| C1 | 27.03; 40.41 / 41.58 | 15.90; 68.29 / 81.69 | pending |
| C4 | 81.92; 63.01 / 68.91 | 61.05; 71.82 / 93.60 | pending |
| C16 | 82.84; 243.26 / 288.20 | 234.15; 75.17 / 87.24 | pending |
| C32 | 81.85; 436.88 / 536.47 | 400.40; 89.81 / 99.61 | pending |
| C64 | 83.29; 834.89 / 1,009.45 | 658.62; 108.60 / 120.96 | pending |
| C128 | 82.31; 1,716.22 / 2,976.66 | 1,160.13; 127.71 / 141.63 | pending |
| C256 | 82.38; 3,602.55 / 4,495.60 | 1,318.52; 243.20 / 263.18 | pending |
| C384 | 82.19; 5,535.70 / 6,403.67 | 1,556.28; 352.45 / 390.37 | pending |
| C512 | 82.51; 6,819.68 / 7,419.83 | 1,629.85; 443.29 / 481.56 | pending |

### Payload only

| Concurrency | Native 1.20 (`native_120`) | Veortex `query-split` | Veortex `gallery-split` |
|---|---:|---:|---:|
| C1 | 26.66; 40.34 / 51.03 | 16.23; 64.88 / 78.67 | pending |
| C4 | 81.30; 64.68 / 68.58 | 60.53; 72.73 / 87.17 | pending |
| C16 | 82.26; 233.18 / 279.93 | 224.50; 80.77 / 90.02 | pending |
| C32 | 81.50; 436.68 / 566.93 | 398.63; 88.63 / 101.62 | pending |
| C64 | 82.25; 848.10 / 971.82 | 649.34; 112.02 / 121.42 | pending |
| C128 | 82.60; 1,720.49 / 2,247.44 | pending | pending |
| C256 | 81.58; 3,637.22 / 4,802.36 | pending | pending |
| C384 | 79.56; 4,959.04 / 5,282.80 | pending | pending |
| C512 | 80.17; 6,862.27 / 7,380.16 | pending | pending |

### Active filter / no payload (90%)

| Concurrency | Native 1.20 (`native_120`) | Veortex `query-split` | Veortex `gallery-split` |
|---|---:|---:|---:|
| C1 | 21.06; 51.47 / 54.59 | pending | pending |
| C4 | 65.79; 78.73 / 83.41 | pending | pending |
| C16 | 66.55; 280.26 / 323.92 | pending | pending |
| C32 | 66.17; 528.68 / 662.59 | pending | pending |
| C64 | 65.14; 1,116.65 / 1,274.91 | pending | pending |
| C128 | 66.08; 2,408.89 / 2,611.46 | pending | pending |
| C256 | 66.59; 3,933.64 / 5,193.87 | pending | pending |
| C384 | 65.98; 7,258.10 / 7,732.13 | pending | pending |
| C512 | 65.09; 11,375.67 / 13,682.31 | pending | pending |

### Active filter + payload (90%)

| Concurrency | Native 1.20 (`native_120`) | Veortex `query-split` | Veortex `gallery-split` |
|---|---:|---:|---:|
| C1 | 20.62; 52.98 / 55.63 | pending | pending |
| C4 | 65.39; 77.89 / 85.05 | pending | pending |
| C16 | 66.00; 298.55 / 372.91 | pending | pending |
| C32 | 65.93; 535.85 / 657.82 | pending | pending |
| C64 | 66.33; 1,045.60 / 1,221.74 | pending | pending |
| C128 | 66.18; 2,125.28 / 2,172.25 | pending | pending |
| C256 | 64.82; 4,188.22 / 4,889.42 | pending | pending |
| C384 | 65.56; 7,186.46 / 8,224.39 | pending | pending |
| C512 | 65.53; 7,934.12 / 8,037.38 | pending | pending |

### Active + position + exclusion / payload (~9%)

| Concurrency | Native 1.20 (`native_120`) | Veortex `query-split` | Veortex `gallery-split` |
|---|---:|---:|---:|
| C1 | 36.71; 32.13 / 35.87 | pending | pending |
| C4 | 127.44; 42.09 / 45.99 | pending | pending |
| C16 | 131.95; 156.79 / 181.76 | pending | pending |
| C32 | 132.18; 270.55 / 305.38 | pending | pending |
| C64 | 131.92; 569.52 / 661.18 | pending | pending |
| C128 | 131.81; 1,061.14 / 1,338.71 | pending | pending |
| C256 | 131.86; 2,290.81 / 2,919.58 | pending | pending |
| C384 | 131.71; 3,505.20 / 5,036.80 | pending | pending |
| C512 | 131.30; 4,326.72 / 5,432.26 | pending | pending |

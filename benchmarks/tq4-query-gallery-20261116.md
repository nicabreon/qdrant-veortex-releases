# Native Qdrant 1.20 vs Veortex query/gallery — TQ4 B=1 Matrix (16 November 2026)

Campaign: `tq4-h2h-20261116t230240z` | Status: **`RUNNING`** (`26/135` accepted B1 cells) | Exported: `2026-11-16T23:24:57.603670+00:00`

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

### No filter / no payload

| Concurrency | Native 1.20 (`native_120`) | Veortex `query-split` | Veortex `gallery-split` |
|---|---:|---:|---:|
| C1 | 27.03; 40.41 / 41.58 | pending | pending |
| C4 | 81.92; 63.01 / 68.91 | pending | pending |
| C16 | 82.84; 243.26 / 288.20 | pending | pending |
| C32 | 81.85; 436.88 / 536.47 | pending | pending |
| C64 | 83.29; 834.89 / 1,009.45 | pending | pending |
| C128 | 82.31; 1,716.22 / 2,976.66 | pending | pending |
| C256 | 82.38; 3,602.55 / 4,495.60 | pending | pending |
| C384 | 82.19; 5,535.70 / 6,403.67 | pending | pending |
| C512 | 82.51; 6,819.68 / 7,419.83 | pending | pending |

### Payload only

| Concurrency | Native 1.20 (`native_120`) | Veortex `query-split` | Veortex `gallery-split` |
|---|---:|---:|---:|
| C1 | 26.66; 40.34 / 51.03 | pending | pending |
| C4 | 81.30; 64.68 / 68.58 | pending | pending |
| C16 | 82.26; 233.18 / 279.93 | pending | pending |
| C32 | 81.50; 436.68 / 566.93 | pending | pending |
| C64 | 82.25; 848.10 / 971.82 | pending | pending |
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
| C512 | pending | pending | pending |

### Active filter + payload (90%)

| Concurrency | Native 1.20 (`native_120`) | Veortex `query-split` | Veortex `gallery-split` |
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

| Concurrency | Native 1.20 (`native_120`) | Veortex `query-split` | Veortex `gallery-split` |
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

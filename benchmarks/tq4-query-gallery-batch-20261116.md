# Native Qdrant 1.20 vs Veortex query/gallery — TQ4 B > 1 Explicit Batch Matrix (16 November 2026)

Campaign: `tq4-h2h-20261116t230240z` | Status: **`RUNNING`** (`31/210` accepted B>1 cells; capacity rejections: `0`) | Exported: `2026-11-17T00:45:23.274919+00:00`

- **Profile:** `TQ4` (`rescore=True`, `oversampling=4.0`, `QDRANT_VEORTEX_TQ_QUERY_BYTES=1`, `truth_mode=f32_exact`, 3 shared vCPUs/node, zero pinning)
- **Curated artifacts:** [JSON](tq4-query-gallery-batch-20261116.json) | [CSV](tq4-query-gallery-batch-20261116.csv)
- Each cell shows **`HTTP req/s / query members/s (q/s); p95 / p99 ms`** (`pending` = not yet measured; zero interpolation).

### No filter / no payload

| Batch / Concurrency | Native 1.20 (`native_120`) | Veortex `query-split` | Veortex `gallery-split` |
|---|---:|---:|---:|
| B2 / C4 | 66.48 HTTP / **132.97** q/s; 76.47 / 83.31 | pending | pending |
| B2 / C6 | 66.08 HTTP / **132.17** q/s; 100.32 / 120.02 | pending | pending |
| B4 / C4 | 42.59 HTTP / **170.38** q/s; 121.62 / 129.59 | pending | pending |
| B4 / C6 | 42.39 HTTP / **169.55** q/s; 156.94 / 193.10 | pending | pending |
| B8 / C4 | 27.47 HTTP / **219.74** q/s; 193.80 / 208.39 | pending | pending |
| B8 / C6 | 27.70 HTTP / **221.63** q/s; 252.76 / 297.38 | pending | pending |
| B16 / C4 | 16.10 HTTP / **257.63** q/s; 330.32 / 346.81 | pending | pending |
| B16 / C6 | 16.29 HTTP / **260.66** q/s; 407.40 / 482.87 | pending | pending |
| B32 / C4 | 8.06 HTTP / **257.97** q/s; 598.04 / 674.55 | pending | pending |
| B32 / C6 | 8.08 HTTP / **258.46** q/s; 925.79 / 1,066.47 | pending | pending |
| B64 / C4 | 4.04 HTTP / **258.41** q/s; 1,093.37 / 1,290.87 | pending | pending |
| B64 / C6 | 4.10 HTTP / **262.41** q/s; 1,866.11 / 2,008.17 | pending | pending |
| B128 / C4 | 2.05 HTTP / **261.89** q/s; 2,462.37 / 2,910.94 | pending | pending |
| B128 / C6 | 2.04 HTTP / **261.76** q/s; 3,718.49 / 4,318.29 | pending | pending |

### Payload only

| Batch / Concurrency | Native 1.20 (`native_120`) | Veortex `query-split` | Veortex `gallery-split` |
|---|---:|---:|---:|
| B2 / C4 | 64.67 HTTP / **129.35** q/s; 81.41 / 86.94 | pending | pending |
| B2 / C6 | 65.36 HTTP / **130.73** q/s; 108.10 / 127.93 | pending | pending |
| B4 / C4 | 42.49 HTTP / **169.97** q/s; 120.95 / 134.02 | pending | pending |
| B4 / C6 | 42.61 HTTP / **170.43** q/s; 167.53 / 199.11 | pending | pending |
| B8 / C4 | 27.20 HTTP / **217.63** q/s; 184.47 / 194.75 | pending | pending |
| B8 / C6 | 27.31 HTTP / **218.52** q/s; 242.78 / 317.61 | pending | pending |
| B16 / C4 | 15.95 HTTP / **255.20** q/s; 333.52 / 367.86 | pending | pending |
| B16 / C6 | 15.92 HTTP / **254.72** q/s; 423.73 / 526.90 | pending | pending |
| B32 / C4 | 8.02 HTTP / **256.71** q/s; 598.06 / 665.83 | pending | pending |
| B32 / C6 | 8.05 HTTP / **257.51** q/s; 915.04 / 1,104.79 | pending | pending |
| B64 / C4 | 4.02 HTTP / **256.96** q/s; 1,279.08 / 1,323.73 | pending | pending |
| B64 / C6 | 4.01 HTTP / **256.49** q/s; 1,851.71 / 2,107.66 | pending | pending |
| B128 / C4 | 2.00 HTTP / **255.68** q/s; 2,304.74 / 3,232.49 | pending | pending |
| B128 / C6 | 1.99 HTTP / **255.23** q/s; 3,514.12 / 3,833.78 | pending | pending |

### Active filter / no payload (90%)

| Batch / Concurrency | Native 1.20 (`native_120`) | Veortex `query-split` | Veortex `gallery-split` |
|---|---:|---:|---:|
| B2 / C4 | 54.29 HTTP / **108.58** q/s; 96.39 / 103.45 | pending | pending |
| B2 / C6 | 52.68 HTTP / **105.37** q/s; 127.69 / 150.46 | pending | pending |
| B4 / C4 | 37.47 HTTP / **149.87** q/s; 142.26 / 150.63 | pending | pending |
| B4 / C6 | pending | pending | pending |
| B8 / C4 | pending | pending | pending |
| B8 / C6 | pending | pending | pending |
| B16 / C4 | pending | pending | pending |
| B16 / C6 | pending | pending | pending |
| B32 / C4 | pending | pending | pending |
| B32 / C6 | pending | pending | pending |
| B64 / C4 | pending | pending | pending |
| B64 / C6 | pending | pending | pending |
| B128 / C4 | pending | pending | pending |
| B128 / C6 | pending | pending | pending |

### Active filter + payload (90%)

| Batch / Concurrency | Native 1.20 (`native_120`) | Veortex `query-split` | Veortex `gallery-split` |
|---|---:|---:|---:|
| B2 / C4 | pending | pending | pending |
| B2 / C6 | pending | pending | pending |
| B4 / C4 | pending | pending | pending |
| B4 / C6 | pending | pending | pending |
| B8 / C4 | pending | pending | pending |
| B8 / C6 | pending | pending | pending |
| B16 / C4 | pending | pending | pending |
| B16 / C6 | pending | pending | pending |
| B32 / C4 | pending | pending | pending |
| B32 / C6 | pending | pending | pending |
| B64 / C4 | pending | pending | pending |
| B64 / C6 | pending | pending | pending |
| B128 / C4 | pending | pending | pending |
| B128 / C6 | pending | pending | pending |

### Active + position + exclusion / payload (~9%)

| Batch / Concurrency | Native 1.20 (`native_120`) | Veortex `query-split` | Veortex `gallery-split` |
|---|---:|---:|---:|
| B2 / C4 | pending | pending | pending |
| B2 / C6 | pending | pending | pending |
| B4 / C4 | pending | pending | pending |
| B4 / C6 | pending | pending | pending |
| B8 / C4 | pending | pending | pending |
| B8 / C6 | pending | pending | pending |
| B16 / C4 | pending | pending | pending |
| B16 / C6 | pending | pending | pending |
| B32 / C4 | pending | pending | pending |
| B32 / C6 | pending | pending | pending |
| B64 / C4 | pending | pending | pending |
| B64 / C6 | pending | pending | pending |
| B128 / C4 | pending | pending | pending |
| B128 / C6 | pending | pending | pending |

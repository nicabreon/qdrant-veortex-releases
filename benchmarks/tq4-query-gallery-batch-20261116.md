# Native Qdrant 1.20 vs Veortex query/gallery — TQ4 B > 1 Explicit Batch Matrix (16 November 2026)

Campaign: `tq4-h2h-20261116t230240z` | Status: **`RUNNING`** (`82/210` accepted B>1 cells; capacity rejections: `0`) | Exported: `2026-11-17T01:16:10.146539+00:00`

- **Profile:** `TQ4` (`rescore=True`, `oversampling=4.0`, `QDRANT_VEORTEX_TQ_QUERY_BYTES=1`, `truth_mode=f32_exact`, 3 shared vCPUs/node, zero pinning)
- **Curated artifacts:** [JSON](tq4-query-gallery-batch-20261116.json) | [CSV](tq4-query-gallery-batch-20261116.csv)
- Each cell shows **`HTTP req/s / query members/s (q/s); p95 / p99 ms`** (`pending` = not yet measured; zero interpolation).

### No filter / no payload

| Batch / Concurrency | Native 1.20 (`native_120`) | Veortex `query-split` | Veortex `gallery-split` |
|---|---:|---:|---:|
| B2 / C4 | 66.48 HTTP / **132.97** q/s; 76.47 / 83.31 | 58.48 HTTP / **116.97** q/s; 74.35 / 90.26 | pending |
| B2 / C6 | 66.08 HTTP / **132.17** q/s; 100.32 / 120.02 | 86.60 HTTP / **173.19** q/s; 77.65 / 95.13 | pending |
| B4 / C4 | 42.59 HTTP / **170.38** q/s; 121.62 / 129.59 | 56.41 HTTP / **225.65** q/s; 79.52 / 96.73 | pending |
| B4 / C6 | 42.39 HTTP / **169.55** q/s; 156.94 / 193.10 | 77.36 HTTP / **309.43** q/s; 85.23 / 104.82 | pending |
| B8 / C4 | 27.47 HTTP / **219.74** q/s; 193.80 / 208.39 | 50.37 HTTP / **402.92** q/s; 86.06 / 101.21 | pending |
| B8 / C6 | 27.70 HTTP / **221.63** q/s; 252.76 / 297.38 | 70.23 HTTP / **561.82** q/s; 92.13 / 100.82 | pending |
| B16 / C4 | 16.10 HTTP / **257.63** q/s; 330.32 / 346.81 | 41.82 HTTP / **669.18** q/s; 110.42 / 126.53 | pending |
| B16 / C6 | 16.29 HTTP / **260.66** q/s; 407.40 / 482.87 | 55.32 HTTP / **885.07** q/s; 135.41 / 157.63 | pending |
| B32 / C4 | 8.06 HTTP / **257.97** q/s; 598.04 / 674.55 | 33.67 HTTP / **1,077.47** q/s; 144.61 / 169.70 | pending |
| B32 / C6 | 8.08 HTTP / **258.46** q/s; 925.79 / 1,066.47 | 43.67 HTTP / **1,397.32** q/s; 172.21 / 190.58 | pending |
| B64 / C4 | 4.04 HTTP / **258.41** q/s; 1,093.37 / 1,290.87 | 24.10 HTTP / **1,542.17** q/s; 202.71 / 213.11 | pending |
| B64 / C6 | 4.10 HTTP / **262.41** q/s; 1,866.11 / 2,008.17 | 31.91 HTTP / **2,041.95** q/s; 231.85 / 283.82 | pending |
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
| B4 / C6 | 37.70 HTTP / **150.79** q/s; 177.02 / 219.73 | pending | pending |
| B8 / C4 | 25.22 HTTP / **201.79** q/s; 201.34 / 212.65 | pending | pending |
| B8 / C6 | 25.39 HTTP / **203.11** q/s; 260.04 / 303.18 | pending | pending |
| B16 / C4 | 15.27 HTTP / **244.40** q/s; 338.53 / 379.75 | pending | pending |
| B16 / C6 | 15.47 HTTP / **247.49** q/s; 441.33 / 535.84 | pending | pending |
| B32 / C4 | 7.73 HTTP / **247.26** q/s; 600.53 / 694.58 | pending | pending |
| B32 / C6 | 7.73 HTTP / **247.46** q/s; 956.02 / 1,115.41 | pending | pending |
| B64 / C4 | 3.86 HTTP / **246.94** q/s; 1,319.59 / 1,380.01 | pending | pending |
| B64 / C6 | 3.87 HTTP / **247.64** q/s; 1,922.78 / 2,241.36 | pending | pending |
| B128 / C4 | 1.93 HTTP / **247.05** q/s; 2,513.29 / 2,688.55 | pending | pending |
| B128 / C6 | 1.93 HTTP / **247.35** q/s; 4,102.27 / 4,700.70 | pending | pending |

### Active filter + payload (90%)

| Batch / Concurrency | Native 1.20 (`native_120`) | Veortex `query-split` | Veortex `gallery-split` |
|---|---:|---:|---:|
| B2 / C4 | 52.89 HTTP / **105.78** q/s; 100.33 / 107.82 | pending | pending |
| B2 / C6 | 53.40 HTTP / **106.79** q/s; 125.75 / 152.17 | pending | pending |
| B4 / C4 | 37.10 HTTP / **148.40** q/s; 138.76 / 149.13 | pending | pending |
| B4 / C6 | 37.36 HTTP / **149.42** q/s; 179.02 / 210.54 | pending | pending |
| B8 / C4 | 24.95 HTTP / **199.58** q/s; 200.85 / 213.33 | pending | pending |
| B8 / C6 | 25.19 HTTP / **201.50** q/s; 282.58 / 314.60 | pending | pending |
| B16 / C4 | 15.14 HTTP / **242.27** q/s; 341.29 / 357.38 | pending | pending |
| B16 / C6 | 15.22 HTTP / **243.53** q/s; 454.58 / 558.47 | pending | pending |
| B32 / C4 | 7.63 HTTP / **244.17** q/s; 624.59 / 718.94 | pending | pending |
| B32 / C6 | 7.64 HTTP / **244.57** q/s; 936.33 / 1,156.03 | pending | pending |
| B64 / C4 | 3.82 HTTP / **244.26** q/s; 1,287.47 / 1,433.62 | pending | pending |
| B64 / C6 | 3.84 HTTP / **245.48** q/s; 1,925.48 / 2,157.82 | pending | pending |
| B128 / C4 | 1.91 HTTP / **244.57** q/s; 2,505.89 / 3,184.29 | pending | pending |
| B128 / C6 | 1.91 HTTP / **244.25** q/s; 4,109.77 / 4,246.73 | pending | pending |

### Active + position + exclusion / payload (~9%)

| Batch / Concurrency | Native 1.20 (`native_120`) | Veortex `query-split` | Veortex `gallery-split` |
|---|---:|---:|---:|
| B2 / C4 | 110.21 HTTP / **220.42** q/s; 49.88 / 53.68 | pending | pending |
| B2 / C6 | 111.28 HTTP / **222.57** q/s; 69.48 / 76.99 | pending | pending |
| B4 / C4 | 90.43 HTTP / **361.72** q/s; 61.28 / 66.47 | pending | pending |
| B4 / C6 | 90.28 HTTP / **361.10** q/s; 85.59 / 97.71 | pending | pending |
| B8 / C4 | 70.00 HTTP / **560.03** q/s; 73.35 / 79.38 | pending | pending |
| B8 / C6 | 75.15 HTTP / **601.23** q/s; 89.37 / 106.60 | pending | pending |
| B16 / C4 | 51.26 HTTP / **820.22** q/s; 97.79 / 104.97 | pending | pending |
| B16 / C6 | 52.09 HTTP / **833.45** q/s; 141.40 / 161.42 | pending | pending |
| B32 / C4 | 26.28 HTTP / **841.07** q/s; 190.28 / 211.85 | pending | pending |
| B32 / C6 | 26.53 HTTP / **848.92** q/s; 269.65 / 302.81 | pending | pending |
| B64 / C4 | 13.29 HTTP / **850.83** q/s; 399.11 / 460.55 | pending | pending |
| B64 / C6 | 13.92 HTTP / **890.81** q/s; 563.63 / 640.69 | pending | pending |
| B128 / C4 | 6.82 HTTP / **872.41** q/s; 727.14 / 828.00 | pending | pending |
| B128 / C6 | 6.85 HTTP / **876.20** q/s; 1,040.08 / 1,261.51 | pending | pending |

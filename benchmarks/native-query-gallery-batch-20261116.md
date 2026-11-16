# Native Qdrant 1.20 versus Veortex query/gallery modes — B > 1 Explicit Batch Matrix (16 November 2026)

Status revision: **RUNNING** (`156/210` accepted cells recorded; `native_120`: `70/70`, `veortex_query`: `70/70`, `veortex_gallery`: `16/70`; accuracy gates: `15/15` passed of 15 planned; capacity rejections: `0`). Snapshot exported `2026-11-16T07:46:37.323829+00:00`.

> This campaign supplements the completed [135-cell B=1 matrix](native-query-gallery-20261116.md) under the same 3 shared vCPUs/node contract (`NanoCpus=3e9`, `MAX_SEARCH_THREADS=3`, `RAYON_NUM_THREADS=3`, zero per-thread pinning). Unmeasured cells are explicitly marked `Pending` and never fabricated or interpolated.

## Protocol & Reporting Notes

- **Endpoint:** `/collections/bench_collection/points/search/batch` with batch sizes **`B2, B4, B8, B16, B32, B64, B128`** at concurrency **`C4`** and **`C6`** (`210` planned cells across 3 arms × 5 categories × 14 `B/C` pairs).
- **Metrics reported separately:** Every cell reports **`HTTP req/s` / `query members/s` (`q/s`); `p95 / p99 ms`**, where `query members/s = successful_queries / actual_elapsed_s` (every member of every batch checked against saved query truth and payload contract).
- **Curated exports:** [JSON](native-query-gallery-batch-20261116.json) | [CSV](native-query-gallery-batch-20261116.csv)

### No filter / no payload

| Batch / Concurrency | Native 1.20 (`native_120`) | Veortex `query-split` (`veortex_query`) | Veortex `gallery-split` (`veortex_gallery`) |
|---|---:|---:|---:|
| B2 / C4 | 47.79 HTTP / **95.58** q/s; 113.26 / 130.51 | 69.65 HTTP / **139.30** q/s; 64.82 / 80.10 | 81.52 HTTP / **163.04** q/s; 53.10 / 56.13 |
| B2 / C6 | 47.88 HTTP / **95.76** q/s; 139.62 / 165.32 | 102.02 HTTP / **204.04** q/s; 66.89 / 87.36 | 118.19 HTTP / **236.37** q/s; 54.23 / 56.86 |
| B4 / C4 | 39.13 HTTP / **156.50** q/s; 129.69 / 143.01 | 65.86 HTTP / **263.44** q/s; 69.54 / 84.54 | 78.23 HTTP / **312.91** q/s; 54.80 / 56.96 |
| B4 / C6 | 39.50 HTTP / **158.00** q/s; 173.16 / 197.53 | 91.25 HTTP / **364.99** q/s; 73.68 / 92.89 | 107.52 HTTP / **430.06** q/s; 60.62 / 62.57 |
| B8 / C4 | 26.22 HTTP / **209.73** q/s; 195.78 / 212.57 | 61.56 HTTP / **492.47** q/s; 72.53 / 92.48 | 67.61 HTTP / **540.84** q/s; 63.50 / 67.18 |
| B8 / C6 | 26.71 HTTP / **213.66** q/s; 248.18 / 289.53 | 83.75 HTTP / **670.01** q/s; 84.79 / 102.99 | 89.14 HTTP / **713.15** q/s; 73.08 / 77.66 |
| B16 / C4 | 16.26 HTTP / **260.11** q/s; 316.55 / 340.97 | 52.62 HTTP / **841.90** q/s; 85.27 / 103.26 | 52.06 HTTP / **832.90** q/s; 82.11 / 84.98 |
| B16 / C6 | 16.35 HTTP / **261.67** q/s; 410.33 / 511.87 | 70.53 HTTP / **1,128.49** q/s; 112.50 / 133.92 | 62.62 HTTP / **1,001.94** q/s; 107.50 / 119.16 |
| B32 / C4 | 8.16 HTTP / **260.98** q/s; 595.03 / 663.47 | 42.10 HTTP / **1,347.22** q/s; 119.55 / 127.65 | 38.98 HTTP / **1,247.38** q/s; 113.14 / 124.59 |
| B32 / C6 | 8.13 HTTP / **260.14** q/s; 909.49 / 1,042.79 | 56.27 HTTP / **1,800.55** q/s; 134.77 / 154.15 | 45.73 HTTP / **1,463.46** q/s; 144.80 / 158.50 |
| B64 / C4 | 4.03 HTTP / **258.20** q/s; 1,099.01 / 1,169.68 | 31.67 HTTP / **2,027.13** q/s; 157.24 / 175.76 | 26.50 HTTP / **1,695.70** q/s; 186.42 / 212.18 |
| B64 / C6 | 4.06 HTTP / **259.85** q/s; 1,535.72 / 1,616.97 | 38.81 HTTP / **2,484.13** q/s; 214.70 / 252.16 | 29.85 HTTP / **1,910.63** q/s; 235.59 / 257.26 |
| B128 / C4 | 2.05 HTTP / **261.93** q/s; 2,206.97 / 2,959.11 | 18.68 HTTP / **2,390.53** q/s; 277.93 / 309.87 | 15.27 HTTP / **1,955.19** q/s; 295.60 / 310.34 |
| B128 / C6 | 2.04 HTTP / **261.70** q/s; 3,071.40 / 3,880.57 | 21.74 HTTP / **2,782.94** q/s; 344.12 / 393.89 | 15.68 HTTP / **2,007.18** q/s; 441.32 / 465.03 |

### Payload only

| Batch / Concurrency | Native 1.20 (`native_120`) | Veortex `query-split` (`veortex_query`) | Veortex `gallery-split` (`veortex_gallery`) |
|---|---:|---:|---:|
| B2 / C4 | 47.93 HTTP / **95.86** q/s; 113.51 / 122.37 | 69.34 HTTP / **138.69** q/s; 61.89 / 71.29 | 83.83 HTTP / **167.65** q/s; 50.88 / 52.68 |
| B2 / C6 | 47.92 HTTP / **95.85** q/s; 142.35 / 165.70 | 102.65 HTTP / **205.30** q/s; 63.65 / 78.88 | 121.32 HTTP / **242.65** q/s; 53.09 / 57.45 |
| B4 / C4 | 38.55 HTTP / **154.19** q/s; 139.46 / 154.41 | 67.40 HTTP / **269.59** q/s; 66.83 / 86.83 | Pending |
| B4 / C6 | 38.10 HTTP / **152.41** q/s; 182.51 / 223.43 | 95.45 HTTP / **381.80** q/s; 69.38 / 83.11 | Pending |
| B8 / C4 | 25.86 HTTP / **206.86** q/s; 205.15 / 221.22 | 61.76 HTTP / **494.04** q/s; 72.93 / 90.37 | Pending |
| B8 / C6 | 26.12 HTTP / **208.97** q/s; 261.78 / 317.17 | 84.07 HTTP / **672.52** q/s; 81.75 / 95.46 | Pending |
| B16 / C4 | 15.56 HTTP / **248.99** q/s; 325.65 / 385.58 | 50.35 HTTP / **805.64** q/s; 89.29 / 108.99 | Pending |
| B16 / C6 | 15.64 HTTP / **250.28** q/s; 468.63 / 542.47 | 64.99 HTTP / **1,039.84** q/s; 113.17 / 127.85 | Pending |
| B32 / C4 | 7.88 HTTP / **252.27** q/s; 640.74 / 669.79 | 38.52 HTTP / **1,232.56** q/s; 125.97 / 141.13 | Pending |
| B32 / C6 | 8.00 HTTP / **255.95** q/s; 936.20 / 1,064.97 | 50.85 HTTP / **1,627.33** q/s; 146.11 / 158.21 | Pending |
| B64 / C4 | 4.03 HTTP / **258.18** q/s; 1,214.64 / 1,286.48 | 28.10 HTTP / **1,798.58** q/s; 178.96 / 197.82 | Pending |
| B64 / C6 | 3.96 HTTP / **253.67** q/s; 1,740.68 / 2,213.27 | 32.21 HTTP / **2,061.38** q/s; 239.60 / 285.12 | Pending |
| B128 / C4 | 2.00 HTTP / **255.86** q/s; 2,248.26 / 2,394.57 | 16.42 HTTP / **2,101.12** q/s; 313.40 / 329.04 | Pending |
| B128 / C6 | 1.99 HTTP / **254.23** q/s; 3,223.93 / 3,868.66 | 18.19 HTTP / **2,327.97** q/s; 401.30 / 431.84 | Pending |

### Active filter / no payload (90%)

| Batch / Concurrency | Native 1.20 (`native_120`) | Veortex `query-split` (`veortex_query`) | Veortex `gallery-split` (`veortex_gallery`) |
|---|---:|---:|---:|
| B2 / C4 | 43.35 HTTP / **86.71** q/s; 128.33 / 138.94 | 58.99 HTTP / **117.99** q/s; 74.84 / 91.17 | Pending |
| B2 / C6 | 42.69 HTTP / **85.38** q/s; 168.53 / 199.27 | 87.63 HTTP / **175.27** q/s; 75.24 / 90.22 | Pending |
| B4 / C4 | 35.97 HTTP / **143.87** q/s; 142.03 / 157.49 | 57.83 HTTP / **231.34** q/s; 77.70 / 98.52 | Pending |
| B4 / C6 | 36.19 HTTP / **144.78** q/s; 184.72 / 229.74 | 79.97 HTTP / **319.88** q/s; 84.82 / 104.09 | Pending |
| B8 / C4 | 25.07 HTTP / **200.53** q/s; 205.93 / 224.18 | 52.82 HTTP / **422.55** q/s; 89.29 / 104.50 | Pending |
| B8 / C6 | 25.27 HTTP / **202.18** q/s; 277.19 / 331.25 | 71.28 HTTP / **570.26** q/s; 93.74 / 117.11 | Pending |
| B16 / C4 | 16.02 HTTP / **256.38** q/s; 329.10 / 351.65 | 43.75 HTTP / **699.96** q/s; 102.63 / 124.58 | Pending |
| B16 / C6 | 16.21 HTTP / **259.44** q/s; 412.65 / 498.20 | 63.69 HTTP / **1,019.06** q/s; 119.60 / 136.47 | Pending |
| B32 / C4 | 7.94 HTTP / **254.03** q/s; 620.71 / 679.50 | 37.59 HTTP / **1,202.77** q/s; 126.50 / 138.03 | Pending |
| B32 / C6 | 7.93 HTTP / **253.87** q/s; 890.53 / 1,055.66 | 50.55 HTTP / **1,617.67** q/s; 141.90 / 154.82 | Pending |
| B64 / C4 | 3.91 HTTP / **249.96** q/s; 1,224.01 / 1,342.79 | 29.53 HTTP / **1,889.73** q/s; 167.80 / 188.40 | Pending |
| B64 / C6 | 3.96 HTTP / **253.24** q/s; 1,806.84 / 2,069.55 | 35.95 HTTP / **2,300.84** q/s; 234.20 / 280.56 | Pending |
| B128 / C4 | 1.96 HTTP / **251.26** q/s; 2,605.82 / 3,560.11 | 17.29 HTTP / **2,212.51** q/s; 292.14 / 311.83 | Pending |
| B128 / C6 | 2.00 HTTP / **255.44** q/s; 3,593.01 / 5,051.83 | 20.25 HTTP / **2,592.42** q/s; 378.74 / 416.99 | Pending |

### Active filter + payload (90%)

| Batch / Concurrency | Native 1.20 (`native_120`) | Veortex `query-split` (`veortex_query`) | Veortex `gallery-split` (`veortex_gallery`) |
|---|---:|---:|---:|
| B2 / C4 | 42.16 HTTP / **84.33** q/s; 123.37 / 134.07 | 57.62 HTTP / **115.23** q/s; 78.94 / 89.96 | Pending |
| B2 / C6 | 41.70 HTTP / **83.40** q/s; 160.09 / 196.18 | 84.46 HTTP / **168.92** q/s; 83.61 / 98.16 | Pending |
| B4 / C4 | 34.43 HTTP / **137.70** q/s; 153.81 / 164.12 | 55.39 HTTP / **221.56** q/s; 88.59 / 101.79 | Pending |
| B4 / C6 | 34.09 HTTP / **136.36** q/s; 193.76 / 237.12 | 78.18 HTTP / **312.73** q/s; 93.56 / 107.95 | Pending |
| B8 / C4 | 24.05 HTTP / **192.38** q/s; 215.46 / 225.27 | 51.06 HTTP / **408.51** q/s; 95.78 / 107.27 | Pending |
| B8 / C6 | 24.34 HTTP / **194.74** q/s; 266.69 / 312.06 | 69.14 HTTP / **553.09** q/s; 103.73 / 114.95 | Pending |
| B16 / C4 | 15.21 HTTP / **243.44** q/s; 313.97 / 343.96 | 40.51 HTTP / **648.08** q/s; 123.67 / 139.72 | Pending |
| B16 / C6 | 15.41 HTTP / **246.53** q/s; 434.82 / 542.07 | 57.33 HTTP / **917.22** q/s; 128.49 / 142.59 | Pending |
| B32 / C4 | 7.67 HTTP / **245.29** q/s; 652.33 / 743.36 | 32.23 HTTP / **1,031.27** q/s; 144.63 / 160.65 | Pending |
| B32 / C6 | 7.71 HTTP / **246.63** q/s; 899.14 / 1,050.47 | 45.45 HTTP / **1,454.26** q/s; 154.99 / 165.98 | Pending |
| B64 / C4 | 3.85 HTTP / **246.29** q/s; 1,330.78 / 1,501.76 | 25.79 HTTP / **1,650.44** q/s; 182.91 / 197.87 | Pending |
| B64 / C6 | 3.85 HTTP / **246.52** q/s; 1,863.00 / 2,049.76 | 29.84 HTTP / **1,909.64** q/s; 262.24 / 286.59 | Pending |
| B128 / C4 | 1.93 HTTP / **246.85** q/s; 2,506.13 / 3,077.62 | 15.18 HTTP / **1,942.53** q/s; 337.26 / 356.36 | Pending |
| B128 / C6 | 1.96 HTTP / **250.53** q/s; 3,152.35 / 3,613.90 | 16.95 HTTP / **2,169.69** q/s; 448.82 / 482.38 | Pending |

### Active + position + exclusion / payload (~9%)

| Batch / Concurrency | Native 1.20 (`native_120`) | Veortex `query-split` (`veortex_query`) | Veortex `gallery-split` (`veortex_gallery`) |
|---|---:|---:|---:|
| B2 / C4 | 103.82 HTTP / **207.64** q/s; 53.60 / 56.91 | 89.82 HTTP / **179.65** q/s; 50.52 / 53.25 | Pending |
| B2 / C6 | 105.42 HTTP / **210.85** q/s; 62.23 / 73.41 | 133.36 HTTP / **266.73** q/s; 50.98 / 52.93 | Pending |
| B4 / C4 | 90.80 HTTP / **363.20** q/s; 58.31 / 61.88 | 86.37 HTTP / **345.48** q/s; 52.46 / 54.74 | Pending |
| B4 / C6 | 93.68 HTTP / **374.72** q/s; 73.90 / 89.30 | 125.66 HTTP / **502.64** q/s; 53.90 / 55.85 | Pending |
| B8 / C4 | 74.80 HTTP / **598.38** q/s; 69.73 / 73.90 | 81.23 HTTP / **649.84** q/s; 55.18 / 57.13 | Pending |
| B8 / C6 | 78.57 HTTP / **628.55** q/s; 90.94 / 107.39 | 119.30 HTTP / **954.37** q/s; 56.90 / 59.81 | Pending |
| B16 / C4 | 53.97 HTTP / **863.48** q/s; 92.21 / 97.14 | 72.33 HTTP / **1,157.36** q/s; 63.11 / 66.26 | Pending |
| B16 / C6 | 55.59 HTTP / **889.48** q/s; 133.11 / 149.51 | 96.34 HTTP / **1,541.51** q/s; 73.80 / 78.63 | Pending |
| B32 / C4 | 27.92 HTTP / **893.48** q/s; 167.32 / 198.43 | 55.14 HTTP / **1,764.40** q/s; 83.67 / 88.62 | Pending |
| B32 / C6 | 28.48 HTTP / **911.24** q/s; 258.22 / 293.17 | 74.58 HTTP / **2,386.71** q/s; 98.93 / 111.24 | Pending |
| B64 / C4 | 13.74 HTTP / **879.24** q/s; 367.24 / 437.85 | 42.20 HTTP / **2,700.83** q/s; 111.27 / 117.78 | Pending |
| B64 / C6 | 13.77 HTTP / **881.58** q/s; 513.20 / 592.45 | 54.52 HTTP / **3,489.40** q/s; 139.07 / 151.42 | Pending |
| B128 / C4 | 6.93 HTTP / **887.29** q/s; 694.17 / 738.71 | 27.96 HTTP / **3,578.39** q/s; 171.21 / 186.44 | Pending |
| B128 / C6 | 6.93 HTTP / **886.78** q/s; 1,003.23 / 1,055.07 | 34.20 HTTP / **4,377.67** q/s; 224.57 / 242.33 | Pending |

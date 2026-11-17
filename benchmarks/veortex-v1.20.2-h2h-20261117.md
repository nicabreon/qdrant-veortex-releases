# Qdrant 1.20.2 Base Integration H2H Benchmark (`v1.20.2` Subset: `75/75` Accepted)

- **Run ID:** `v1202-h2h-20261117t055443z` (`COMPLETED` — `2026-11-17T05:54:43.392782+00:00` to `2026-11-17T06:48:11.721665+00:00`)
- **Source Branch / Commit:** `feat/veortex-v1.20.2` @ `3668acaac8ac48df22094ec3701e8d906041c202` (upstream Qdrant `v1.20.2` `23065a0bf6857c3e5da45f6c8939cc746cc0580e` merged beneath Veortex)
- **Verified Binaries:**
  - `native_1202`: official `qdrant/qdrant:v1.20.2` (`396528f39af0f57702917480cfd483cb8c3b3f97b62e146c381ffc82b4134802`, `MAX_SEARCH_THREADS=3`, `RAYON_NUM_THREADS=3`)
  - `veortex_query` & `veortex_gallery`: Veortex `1.20.2` (`ea950d9ebed60c867eb621c733d1a8f2cfe33d9103a550cc802f753e3e07a2cc`), same 3 shared guest vCPUs/node (`NanoCpus=3e9`, zero pinning)
- **Gates:** `15/15 × 1,024` exact FP32 Top-10 + payload oracle (`0` failed, `0` errors), `45/45` B1 accepted, `30/30` Batch accepted (`0` HTTP 429), all overlay/git restoration checks passed (`receipt.json` SHA-256 `014a0504e0e25a848925df66497bfdd545c0f4c63d2bb3fff9d8ada515e570f1`)

## B1 Representative Cells (`C1, C16, C512` — HTTP req/s; p95 / p99 ms; `[delta vs v1.20.0]`)

| Category | Load | Native 1.20.2 (`native_1202`) | Veortex `query-split` (`veortex_query`) | Veortex `gallery-split` (`veortex_gallery`) |
|---|---:|---:|---:|---:|
| **No filter / no payload** | C1 | 18.49; 63.64 / 78.24 (`-5.87%`) | 17.06; 77.91 / 90.15 (`-0.50%`) | **23.46**; 47.26 / 51.61 (`-2.54%`) |
| **No filter / no payload** | C16 | 51.16; 423.35 / 491.83 (`-10.20%`) | 260.63; 84.57 / 104.72 (`+0.26%`) | **294.65**; 61.31 / 65.45 (`-5.94%`) |
| **No filter / no payload** | C512 | 49.61; 11,261.01 / 12,421.08 (`-9.33%`) | **2,037.50**; 399.75 / 486.17 (`-0.72%`) | 1,345.08; 458.26 / 515.73 (`-15.61%`) |
| **Payload only** | C1 | 18.47; 63.48 / 77.22 (`-6.32%`) | 17.07; 77.59 / 96.16 (`-6.78%`) | **23.47**; 47.36 / 51.22 (`-3.21%`) |
| **Payload only** | C16 | 52.95; 365.45 / 454.15 (`-5.52%`) | 242.20; 92.63 / 128.72 (`-9.80%`) | **299.54**; 60.19 / 67.68 (`-0.07%`) |
| **Payload only** | C512 | 52.17; 12,684.99 / 13,528.18 (`-3.41%`) | **1,700.58**; 461.05 / 562.21 (`-7.01%`) | 1,489.73; 424.65 / 448.24 (`-3.31%`) |
| **Active ~90% / no payload** | C1 | 16.53; 72.34 / 88.54 (`-4.70%`) | 14.85; 83.36 / 94.46 (`-2.35%`) | **18.79**; 59.47 / 64.55 (`-0.37%`) |
| **Active ~90% / no payload** | C16 | 47.12; 404.60 / 492.35 (`-6.47%`) | 221.39; 89.50 / 105.54 (`-0.89%`) | **246.93**; 71.91 / 78.17 (`-0.56%`) |
| **Active ~90% / no payload** | C512 | 48.47; 15,058.78 / 16,792.84 (`-0.63%`) | **1,968.88**; 426.90 / 502.41 (`+2.22%`) | 1,521.47; 408.70 / 428.32 (`-7.49%`) |
| **Active ~90% + payload** | C1 | 16.54; 69.94 / 87.90 (`-5.17%`) | 13.53; 99.88 / 114.86 (`-11.10%`) | **18.81**; 58.47 / 62.98 (`-0.51%`) |
| **Active ~90% + payload** | C16 | 49.44; 372.94 / 487.09 (`-2.43%`) | 200.17; 110.43 / 130.14 (`-11.41%`) | **246.99**; 71.44 / 76.81 (`-1.46%`) |
| **Active ~90% + payload** | C512 | 47.72; 22,970.30 / 23,504.96 (`-0.90%`) | **1,597.32**; 480.58 / 617.80 (`-11.24%`) | 1,495.08; 423.26 / 444.95 (`-3.55%`) |
| **Active + pos + excl (~9%)** | C1 | **69.75**; 17.52 / 20.60 (`+109.06%`) | 44.75; 26.90 / 37.82 (`+77.26%`) | 30.86; 36.42 / 39.97 (`+65.38%`) |
| **Active + pos + excl (~9%)** | C16 | 245.35; 83.69 / 102.93 (`+108.58%`) | **637.93**; 29.94 / 39.31 (`+80.10%`) | 441.59; 41.59 / 46.74 (`+59.12%`) |
| **Active + pos + excl (~9%)** | C512 | 243.18; 2,193.00 / 2,237.82 (`+112.03%`) | **2,900.02**; 247.99 / 285.34 (`-7.25%`) | 2,576.20; 275.32 / 324.10 (`+1.43%`) |

## B > 1 Batch Representative Cells (`B8/C6, B128/C6` — HTTP req/s / query q/s; p95 / p99 ms; `[delta vs v1.20.0]`)

| Category | Batch / C | Native 1.20.2 (`native_1202`) | Veortex `query-split` (`veortex_query`) | Veortex `gallery-split` (`veortex_gallery`) |
|---|---|---:|---:|---:|
| **No filter / no payload** | B8 / C6 | 25.80 HTTP / 206.36 q/s; 258.43 / 310.66 (`-3.42%`) | 80.40 HTTP / 643.20 q/s; 93.04 / 124.85 (`-4.00%`) | 90.54 HTTP / **724.30** q/s; 72.10 / 75.89 (`+1.56%`) |
| **No filter / no payload** | B128 / C6 | 1.92 HTTP / 245.76 q/s; 3,956.20 / 4,739.05 (`-6.09%`) | 20.08 HTTP / **2,570.62** q/s; 361.68 / 419.89 (`-7.63%`) | 15.56 HTTP / 1,991.12 q/s; 454.10 / 502.74 (`-0.80%`) |
| **Payload only** | B8 / C6 | 25.32 HTTP / 202.54 q/s; 281.03 / 331.37 (`-3.08%`) | 76.63 HTTP / 613.05 q/s; 102.65 / 123.80 (`-8.84%`) | 81.55 HTTP / **652.42** q/s; 79.81 / 85.74 (`-2.16%`) |
| **Payload only** | B128 / C6 | 1.89 HTTP / 242.50 q/s; 3,611.94 / 4,145.87 (`-4.61%`) | 16.50 HTTP / **2,112.56** q/s; 453.24 / 505.65 (`-9.25%`) | 14.03 HTTP / 1,796.03 q/s; 505.91 / 520.25 (`-3.14%`) |
| **Active ~90% / no payload** | B8 / C6 | 24.75 HTTP / 198.02 q/s; 270.79 / 330.55 (`-2.06%`) | 70.02 HTTP / 560.16 q/s; 102.89 / 113.25 (`-1.77%`) | 77.25 HTTP / **618.03** q/s; 83.89 / 89.44 (`+2.70%`) |
| **Active ~90% / no payload** | B128 / C6 | 1.96 HTTP / 251.13 q/s; 3,558.80 / 4,466.11 (`-1.69%`) | 19.20 HTTP / **2,457.44** q/s; 408.46 / 463.24 (`-5.21%`) | 15.23 HTTP / 1,949.19 q/s; 465.73 / 487.92 (`+0.23%`) |
| **Active ~90% + payload** | B8 / C6 | 24.37 HTTP / 194.97 q/s; 289.66 / 351.30 (`+0.12%`) | 68.39 HTTP / 547.13 q/s; 101.23 / 122.08 (`-1.08%`) | 74.06 HTTP / **592.47** q/s; 86.93 / 93.55 (`+0.30%`) |
| **Active ~90% + payload** | B128 / C6 | 1.93 HTTP / 246.46 q/s; 3,380.46 / 4,003.71 (`-1.63%`) | 16.84 HTTP / **2,156.10** q/s; 444.47 / 488.19 (`-0.63%`) | 13.97 HTTP / 1,788.78 q/s; 498.16 / 534.10 (`+1.75%`) |
| **Active + pos + excl (~9%)** | B8 / C6 | 123.52 HTTP / 988.14 q/s; 61.20 / 68.74 (`+57.21%`) | 188.71 HTTP / **1,509.70** q/s; 37.14 / 41.09 (`+58.19%`) | 132.46 HTTP / 1,059.66 q/s; 50.10 / 53.67 (`+47.33%`) |
| **Active + pos + excl (~9%)** | B128 / C6 | 9.77 HTTP / 1,250.89 q/s; 806.97 / 1,057.87 (`+41.06%`) | 35.98 HTTP / **4,605.16** q/s; 215.81 / 240.84 (`+5.20%`) | 34.23 HTTP / 4,381.13 q/s; 224.02 / 247.72 (`+7.05%`) |

## Honest Delta Summary vs Frozen `v1.20.0` High-Water Marks

1. **Selective `~9%` Filter (`Active + pos + excl`) Gain Across Upstream `v1.20.2`:**
   - Upstream `native_1202` roughly doubled vs `native_120` on `B1` (`C1`: `69.75` vs `33.36`, `C16`: `245.35` vs `117.63`, `C512`: `243.18` vs `114.69`) and gained `+41%–57%` on `B8/B128` Batch.
   - `veortex_query` jumped `+77.3%` at `C1` (`44.75`), `+80.1%` at `C16` (`637.93`, **2.6×** `native_1202`), `+58.2%` at `B8/C6` (`1,509.70 q/s`), and hit a new overall peak at `B128/C6` (**`4,605.16 q/s`**, `+5.20%` over `v1.20.0`'s `4,377.67 q/s`, **3.68×** `native_1202`). `B1 C512` was `-7.25%` (`2,900.02` vs `3,126.79`).
2. **Broad / Dense Workloads (`Unfiltered` & `Active ~90%`):**
   - Veortex `v1.20.2` maintains up to **41.1×** higher B1 `C512` throughput (`2,037.50` vs `49.61` req/s unfiltered) and **10.5×** higher `B128/C6` batch throughput (`2,570.62` vs `245.76` q/s) over `native_1202`, with `veortex_gallery` leading `C1–C16` and `B8/C6`.
   - Relative to `v1.20.0` high-water marks, upstream `native_1202` itself dropped `-0.6%` to `-10.2%` across dense B1/Batch cells; `veortex_query` is nearly flat on `unfiltered_no_payload` (`-0.7%` to `+0.3%`) and `active_only_no_payload` (`-2.4%` to `+2.2%` B1), while `90%`/payload paths show a `-7%` to `-11.4%` regression (`veortex_gallery unfiltered_no_payload C512`: `-15.61%`, while `veortex_gallery` Batch stays `-3.1%` to `+2.7%`).

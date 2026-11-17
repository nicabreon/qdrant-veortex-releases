# Native Qdrant 1.20 vs Veortex query/gallery — TQ2 B > 1 Explicit Batch Matrix (16 November 2026)

Campaign: `tq2-h2h-20261116t225334z` | Status: **`PROBE_COMPLETED`** (`0/210` accepted B>1 cells; capacity rejections: `0`) | Exported: `2026-11-17T01:26:23.006524+00:00`

- **Profile:** `TQ2` (`rescore=True`, `oversampling=2.0`, `QDRANT_VEORTEX_TQ_QUERY_BYTES=0`, `truth_mode=native_parity`, 3 shared vCPUs/node, zero pinning)
- **Curated artifacts:** [JSON](tq2-query-gallery-batch-20261116.json) | [CSV](tq2-query-gallery-batch-20261116.csv)
- Each cell shows **`HTTP req/s / query members/s (q/s); p95 / p99 ms`** (`pending` = not yet measured; zero interpolation).

### No filter / no payload

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

### Payload only

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

### Active filter / no payload (90%)

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

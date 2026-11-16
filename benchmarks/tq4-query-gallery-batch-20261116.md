# Native Qdrant 1.20 vs Veortex query/gallery — TQ4 B > 1 Explicit Batch Matrix (16 November 2026)

Campaign: `tq4-h2h-20261116t230240z` | Status: **`RUNNING`** (`0/210` accepted B>1 cells; capacity rejections: `0`) | Exported: `2026-11-16T23:43:35.828687+00:00`

- **Profile:** `TQ4` (`rescore=True`, `oversampling=4.0`, `QDRANT_VEORTEX_TQ_QUERY_BYTES=1`, `truth_mode=f32_exact`, 3 shared vCPUs/node, zero pinning)
- **Curated artifacts:** [JSON](tq4-query-gallery-batch-20261116.json) | [CSV](tq4-query-gallery-batch-20261116.csv)
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

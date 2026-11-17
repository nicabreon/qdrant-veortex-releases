# Native Qdrant 1.20 vs Veortex query/gallery — TQ2 B=1 Matrix (16 November 2026)

Campaign: `tq2-h2h-20261117t032416z` | Status: **`RUNNING`** (`0/135` accepted B1 cells) | Exported: `2026-11-17T03:34:44.042893+00:00`

- **Profile:** `TQ2` (`rescore=True`, `oversampling=176.7`, `QDRANT_VEORTEX_TQ_QUERY_BYTES=1`, `truth_mode=f32_exact`, 3 shared vCPUs/node, zero pinning)
- **Curated artifacts:** [JSON](tq2-query-gallery-20261116.json) | [CSV](tq2-query-gallery-20261116.csv)
- Each cell shows **`HTTP req/s; p95 / p99 ms`** (`pending` = not yet measured; zero interpolation).

### No filter / no payload

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

### Payload only

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

### Active filter / no payload (90%)

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

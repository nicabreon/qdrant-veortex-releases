# Veortex dynamic-ring batch results — live progress

**Preliminary live data. Final acceptance and the old/new comparison are deferred until all gates pass.**

Campaign `dynamic-ring-20261110t044606z`: 3/16 timing rows recorded; 3 currently accepted; receipt status `TIMING`.

This focused campaign compares Veortex AVX512 VNNI and Auto at B64/C4 and B128/C4 across four payload/filter categories. It uses the same three-node, three-shared-CPU, 3M × 512D SQ8 fixture and common client as the prior shared-CPU report.

| Backend | Category | B/C | HTTP RPS | Query/s | p95 / p99 ms | CPU / ring proof |
|---|---|---:|---:|---:|---:|---|
| avx512vnni | No filter / no payload | 64/4 | 10.58 | 677.43 | 404.46 / 439.17 | PASSED / True |
| avx512vnni | No filter / no payload | 128/4 | 5.63 | 720.88 | 818.98 / 955.49 | PASSED / True |
| avx512vnni | No filter / payload | 64/4 | 10.31 | 659.76 | 417.04 / 553.00 | PASSED / True |

Rejected rows: 0. Rejected measurements remain in JSON/CSV with reasons and are excluded from the results table.
Missing cells are not estimated. A row-level accepted flag remains provisional until the final exporter verifies source, mask, ISA, admission, Top10/F32, zero-error, and restoration evidence.

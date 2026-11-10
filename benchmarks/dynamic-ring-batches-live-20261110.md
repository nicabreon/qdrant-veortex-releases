# Veortex dynamic-ring batch results — live progress

**Preliminary live data. Final acceptance and the old/new comparison are deferred until all gates pass.**

Campaign `dynamic-ring-20261110t050818z`: 13/16 timing rows recorded; 13 currently accepted; receipt status `TIMING`.

This focused campaign compares Veortex AVX512 VNNI and Auto at B64/C4 and B128/C4 across four payload/filter categories. It uses the same three-node, three-shared-CPU, 3M × 512D SQ8 fixture and common client as the prior shared-CPU report.

| Backend | Category | B/C | HTTP RPS | Query/s | p95 / p99 ms | CPU / ring proof |
|---|---|---:|---:|---:|---:|---|
| avx512vnni | No filter / no payload | 64/4 | 10.63 | 680.00 | 394.57 / 406.50 | PASSED / True |
| avx512vnni | No filter / no payload | 128/4 | 5.70 | 729.62 | 792.20 / 829.06 | PASSED / True |
| avx512vnni | No filter / payload | 64/4 | 10.47 | 669.94 | 406.09 / 416.52 | PASSED / True |
| avx512vnni | No filter / payload | 128/4 | 5.59 | 715.03 | 805.45 / 867.66 | PASSED / True |
| avx512vnni | Active only (~90%) / payload | 64/4 | 10.43 | 667.78 | 410.32 / 495.51 | PASSED / True |
| avx512vnni | Active only (~90%) / payload | 128/4 | 5.58 | 713.89 | 819.31 / 848.79 | PASSED / True |
| avx512vnni | Active + position exclusion (~9%) / payload | 64/4 | 40.82 | 2612.66 | 110.11 / 118.84 | PASSED / True |
| avx512vnni | Active + position exclusion (~9%) / payload | 128/4 | 26.64 | 3410.03 | 184.94 / 200.58 | PASSED / True |
| auto | No filter / no payload | 64/4 | 26.26 | 1680.82 | 177.01 / 186.25 | PASSED / True |
| auto | No filter / no payload | 128/4 | 15.71 | 2011.34 | 296.36 / 320.28 | PASSED / True |
| auto | No filter / payload | 64/4 | 25.11 | 1606.80 | 172.26 / 179.05 | PASSED / True |
| auto | No filter / payload | 128/4 | 14.51 | 1857.73 | 314.71 / 334.88 | PASSED / True |
| auto | Active only (~90%) / payload | 64/4 | 17.68 | 1131.82 | 246.26 / 255.76 | PASSED / True |

Rejected rows: 0. Rejected measurements remain in JSON/CSV with reasons and are excluded from the results table.
Missing cells are not estimated. A row-level accepted flag remains provisional until the final exporter verifies source, mask, ISA, admission, Top10/F32, zero-error, and restoration evidence.

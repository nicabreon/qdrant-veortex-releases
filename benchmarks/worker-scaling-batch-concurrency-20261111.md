# Matched SQ8 worker-scaling diagnostic

This report compares configured ring-worker limits 1 and 3 on the same 3-node, 3M-point, 512D SQ8 profile. It contains 30 accepted timing rows (29 raw-accepted plus one explicitly adjudicated), including regressions, and 2 separately retained HTTP-429 capacity attempts.

## Performance points

HTTP RPS counts successful HTTP requests per measured elapsed time; query QPS also multiplies by batch size. Latencies use full-response validated client latency. Each point has 16 warmups, a 30-second configured dispatch window, and request drain before final counters.

| Workers | Category | Batch | Concurrency | HTTP RPS | Query QPS | p50 ms | p95 ms | p99 ms | Requests ok/failed | Queries ok/failed | Exact truth | Payload contract |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | No filter / no payload | 1 | 64 | 734.81 | 734.81 | 86.19 | 100.22 | 117.41 | 22080/0 | 22080/0 | 22080/22080 | 22080/22080 |
| 1 | No filter / no payload | 1 | 128 | 860.33 | 860.33 | 142.18 | 186.73 | 201.19 | 25915/0 | 25915/0 | 25915/25915 | 25915/25915 |
| 1 | No filter / no payload | 1 | 256 | 903.84 | 903.84 | 302.57 | 348.39 | 362.79 | 27329/0 | 27329/0 | 27329/27329 | 27329/27329 |
| 1 | No filter / no payload | 1 | 384 | 890.24 | 890.24 | 427.77 | 480.76 | 501.99 | 26977/0 | 26977/0 | 26977/26977 | 26977/26977 |
| 1 | No filter / no payload | 64 | 4 | 15.36 | 983.12 | 280.58 | 322.99 | 366.09 | 464/0 | 29696/0 | 29696/29696 | 29696/29696 |
| 1 | No filter / no payload | 64 | 8 | 15.88 | 1016.32 | 491.33 | 598.96 | 622.74 | 485/0 | 31040/0 | 31040/31040 | 31040/31040 |
| 1 | No filter / no payload | 128 | 4 | 7.90 | 1011.06 | 491.60 | 599.14 | 619.73 | 241/0 | 30848/0 | 30848/30848 | 30848/30848 |
| 1 | No filter / no payload | 128 | 8 | 7.92 | 1013.53 | 1012.86 | 1117.46 | 1180.52 | 244/0 | 31232/0 | 31232/31232 | 31232/31232 |
| 1 | Active-only filter + payload | 1 | 64 | 653.36 | 653.36 | 95.92 | 118.53 | 138.78 | 19648/0 | 19648/0 | 19648/19648 | 19648/19648 |
| 1 | Active-only filter + payload | 1 | 128 | 871.79 | 871.79 | 142.46 | 189.13 | 203.92 | 26240/0 | 26240/0 | 26240/26240 | 26240/26240 |
| 1 | Active-only filter + payload | 1 | 256 | 855.34 | 855.34 | 291.85 | 356.75 | 370.38 | 25888/0 | 25888/0 | 25888/25888 | 25888/25888 |
| 1 | Active-only filter + payload | 1 | 384 | 867.07 | 867.07 | 438.18 | 498.84 | 551.76 | 26305/0 | 26305/0 | 26305/26305 | 26305/26305 |
| 1 | Active-only filter + payload | 64 | 4 | 13.79 | 882.41 | 312.08 | 353.39 | 380.06 | 416/0 | 26624/0 | 26624/26624 | 26624/26624 |
| 1 | Active-only filter + payload | 64 | 8 | 13.84 | 885.97 | 551.94 | 668.92 | 726.17 | 422/0 | 27008/0 | 27008/27008 | 27008/27008 |
| 1 | Active-only filter + payload | 128 | 4 | 6.84 | 876.05 | 562.50 | 680.92 | 700.62 | 208/0 | 26624/0 | 26624/26624 | 26624/26624 |
| 3 | No filter / no payload | 1 | 64 | 745.05 | 745.05 | 83.97 | 101.50 | 122.65 | 22400/0 | 22400/0 | 22400/22400 | 22400/22400 |
| 3 | No filter / no payload | 1 | 128 | 1300.13 | 1300.13 | 95.58 | 119.62 | 137.49 | 39104/0 | 39104/0 | 39104/39104 | 39104/39104 |
| 3 | No filter / no payload | 1 | 256 | 1569.09 | 1569.09 | 161.82 | 214.43 | 227.21 | 47256/0 | 47256/0 | 47256/47256 | 47256/47256 |
| 3 | No filter / no payload | 1 | 384 | 1784.63 | 1784.63 | 204.67 | 328.27 | 383.25 | 53821/0 | 53821/0 | 53821/53821 | 53821/53821 |
| 3 | No filter / no payload | 64 | 4 | 29.62 | 1895.84 | 133.35 | 166.28 | 190.93 | 890/0 | 56960/0 | 56960/56960 | 56960/56960 |
| 3 | No filter / no payload | 64 | 8 | 40.01 | 2560.36 | 198.05 | 241.34 | 270.23 | 1206/0 | 77184/0 | 77184/77184 | 77184/77184 |
| 3 | No filter / no payload | 128 | 4 | 17.43 | 2231.49 | 229.37 | 295.60 | 314.70 | 525/0 | 67200/0 | 67200/67200 | 67200/67200 |
| 3 | No filter / no payload | 128 | 8 | 20.70 | 2649.02 | 382.16 | 450.28 | 539.57 | 627/0 | 80256/0 | 80256/80256 | 80256/80256 |
| 3 | Active-only filter + payload | 1 | 64 | 728.07 | 728.07 | 86.90 | 100.84 | 113.84 | 21889/0 | 21889/0 | 21889/21889 | 21889/21889 |
| 3 | Active-only filter + payload | 1 | 128 | 1300.13 | 1300.13 | 95.22 | 123.25 | 144.82 | 39091/0 | 39091/0 | 39091/39091 | 39091/39091 |
| 3 | Active-only filter + payload | 1 | 256 | 1500.90 | 1500.90 | 167.80 | 232.65 | 252.86 | 45186/0 | 45186/0 | 45186/45186 | 45186/45186 |
| 3 | Active-only filter + payload | 1 | 384 | 1674.67 | 1674.67 | 220.97 | 346.90 | 405.82 | 50532/0 | 50532/0 | 50532/50532 | 50532/50532 |
| 3 | Active-only filter + payload | 64 | 4 | 25.25 | 1615.71 | 155.83 | 192.23 | 207.88 | 760/0 | 48640/0 | 48640/48640 | 48640/48640 |
| 3 | Active-only filter + payload | 64 | 8 | 34.56 | 2211.60 | 227.78 | 288.08 | 320.07 | 1042/0 | 66688/0 | 66688/66688 | 66688/66688 |
| 3 | Active-only filter + payload | 128 | 4 | 14.98 | 1917.48 | 262.49 | 336.50 | 354.47 | 452/0 | 57856/0 | 57856/57856 | 57856/57856 |

## HTTP-429 capacity rejections

Rejected attempts are excluded from the timing table and worker comparisons. Their partial successes are not clean throughput measurements; the evidence below shows only failed request counts, verified successful responses, and bounded ring work.

| Workers | Category | Batch | Concurrency | Successful requests | HTTP 429 | Failed queries | Elapsed s | Processes restarted |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 1 | Active-only filter + payload | 128 | 8 | 204 | 8127 | 1040256 | 30.208 | not applicable |
| 3 | Active-only filter + payload | 128 | 8 | 495 | 243 | 31104 | 30.332 | yes |

Per-attempt route and admission evidence:

- Worker 1, Active-only filter + payload, B128/C8:
  - Node 0: ring completed 28,160; submitted 29,685; partial work stayed within successful/dispatched-query bounds.
  - Node 1: ring completed 28,160; submitted 28,448; partial work stayed within successful/dispatched-query bounds.
  - Node 2: ring completed 28,160; submitted 28,160; partial work stayed within successful/dispatched-query bounds.
  - Admission reason counters were not captured for this retained attempt; its specific subreason is unknown.
- Worker 3, Active-only filter + payload, B128/C8:
  - Node 0: ring completed 65,408; submitted 65,466; partial work stayed within successful/dispatched-query bounds.
  - Node 1: ring completed 65,408; submitted 65,600; partial work stayed within successful/dispatched-query bounds.
  - Node 2: ring completed 65,408; submitted 65,529; partial work stayed within successful/dispatched-query bounds.
  - Node 0 admission reason counter deltas: veortex_ring_admission_rejections_total{reason="active_groups"}: +0, veortex_ring_admission_rejections_total{reason="query_bytes"}: +239, veortex_ring_admission_rejections_total{reason="result_slots"}: +0, veortex_ring_admission_rejections_total{reason="ring_channel"}: +0, veortex_ring_admission_rejections_total{reason="ring_queue"}: +0, veortex_ring_admission_rejections_total{reason="waiters"}: +0.
  - Node 1 admission reason counter deltas: veortex_ring_admission_rejections_total{reason="active_groups"}: +0, veortex_ring_admission_rejections_total{reason="query_bytes"}: +4, veortex_ring_admission_rejections_total{reason="result_slots"}: +0, veortex_ring_admission_rejections_total{reason="ring_channel"}: +0, veortex_ring_admission_rejections_total{reason="ring_queue"}: +0, veortex_ring_admission_rejections_total{reason="waiters"}: +0.
  - Node 2 admission reason counter deltas: veortex_ring_admission_rejections_total{reason="active_groups"}: +0, veortex_ring_admission_rejections_total{reason="query_bytes"}: +1, veortex_ring_admission_rejections_total{reason="result_slots"}: +0, veortex_ring_admission_rejections_total{reason="ring_channel"}: +0, veortex_ring_admission_rejections_total{reason="ring_queue"}: +0, veortex_ring_admission_rejections_total{reason="waiters"}: +0.

Admission rejection counters may count node-local or gRPC events and do not map one-to-one to HTTP 429 responses. Coalescer resource values are point-in-time gauges, not peaks. Any per-query byte explanation for the historical single-worker attempt remains an inference.

## Per-node CPU and scan-stage diagnostics

CPU equivalents cover warmups, dispatch, and drain. Whole-process CPU equivalents are the robust process-level measure. The named query-compute role and stable ring-thread samples are diagnostic: short-lived or renamed threads can be missed, so un-attributed CPU is not a pure support or I/O measurement. Distinct TID counts span the full observation window and may exceed the worker cap because threads exit and are replaced; they are not a simultaneous active-ring gauge. Ring-worker limit 1 versus 3 is a worker-cap change over the same three shared CPUs per node, not a change in CPU allotment.

| Workers | Category | B/C | Node | Whole-process CPU eq | Query-compute CPU eq | Residual CPU eq | Distinct ring TIDs seen (not concurrent) | Scan stage ns |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | No filter / no payload | B1/C64 | 0 | 1.514 | 0.897 | 0.617 | 1 | 21651264494 |
| 1 | No filter / no payload | B1/C64 | 1 | 1.332 | 0.895 | 0.437 | 6 | 22897714435 |
| 1 | No filter / no payload | B1/C64 | 2 | 1.245 | 0.857 | 0.389 | 11 | 23910682119 |
| 1 | No filter / no payload | B1/C128 | 0 | 1.491 | 0.852 | 0.639 | 1 | 19748793874 |
| 1 | No filter / no payload | B1/C128 | 1 | 1.307 | 0.938 | 0.369 | 1 | 22646739342 |
| 1 | No filter / no payload | B1/C128 | 2 | 1.260 | 0.939 | 0.320 | 1 | 23839120978 |
| 1 | No filter / no payload | B1/C256 | 0 | 1.463 | 0.843 | 0.620 | 1 | 20200869843 |
| 1 | No filter / no payload | B1/C256 | 1 | 1.306 | 0.878 | 0.428 | 8 | 22200579379 |
| 1 | No filter / no payload | B1/C256 | 2 | 1.226 | 0.597 | 0.630 | 24 | 23285191397 |
| 1 | No filter / no payload | B1/C384 | 0 | 1.447 | 0.840 | 0.608 | 1 | 20192068081 |
| 1 | No filter / no payload | B1/C384 | 1 | 1.227 | 0.199 | 1.028 | 19 | 21400809018 |
| 1 | No filter / no payload | B1/C384 | 2 | 1.146 | 0.168 | 0.978 | 13 | 21299929989 |
| 1 | No filter / no payload | B64/C4 | 0 | 1.285 | 0.892 | 0.394 | 1 | 21977340822 |
| 1 | No filter / no payload | B64/C4 | 1 | 1.184 | 0.495 | 0.690 | 18 | 21937887799 |
| 1 | No filter / no payload | B64/C4 | 2 | 1.120 | 0.247 | 0.873 | 15 | 22034428980 |
| 1 | No filter / no payload | B64/C8 | 0 | 1.277 | 0.899 | 0.378 | 1 | 22444677437 |
| 1 | No filter / no payload | B64/C8 | 1 | 1.212 | 0.658 | 0.554 | 11 | 22563605117 |
| 1 | No filter / no payload | B64/C8 | 2 | 1.161 | 0.491 | 0.671 | 8 | 22665244849 |
| 1 | No filter / no payload | B128/C4 | 0 | 1.260 | 0.858 | 0.402 | 1 | 23210373852 |
| 1 | No filter / no payload | B128/C4 | 1 | 1.218 | 0.688 | 0.530 | 22 | 22907100222 |
| 1 | No filter / no payload | B128/C4 | 2 | 1.122 | 0.435 | 0.687 | 45 | 23032012086 |
| 1 | No filter / no payload | B128/C8 | 0 | 1.265 | 0.852 | 0.413 | 1 | 23366586031 |
| 1 | No filter / no payload | B128/C8 | 1 | 1.195 | 0.749 | 0.446 | 14 | 23259944823 |
| 1 | No filter / no payload | B128/C8 | 2 | 1.112 | 0.478 | 0.633 | 41 | 23090020070 |
| 1 | Active-only filter + payload | B1/C64 | 0 | 1.351 | 0.291 | 1.060 | 18 | 19254786927 |
| 1 | Active-only filter + payload | B1/C64 | 1 | 1.199 | 0.142 | 1.057 | 8 | 19739577567 |
| 1 | Active-only filter + payload | B1/C64 | 2 | 1.071 | 0.059 | 1.012 | 5 | 18544505879 |
| 1 | Active-only filter + payload | B1/C128 | 0 | 1.574 | 0.839 | 0.736 | 1 | 19524451549 |
| 1 | Active-only filter + payload | B1/C128 | 1 | 1.348 | 0.914 | 0.434 | 2 | 22098986704 |
| 1 | Active-only filter + payload | B1/C128 | 2 | 1.278 | 0.902 | 0.376 | 4 | 23320121226 |
| 1 | Active-only filter + payload | B1/C256 | 0 | 1.498 | 0.819 | 0.679 | 1 | 19125488768 |
| 1 | Active-only filter + payload | B1/C256 | 1 | 1.317 | 0.921 | 0.397 | 1 | 22302686421 |
| 1 | Active-only filter + payload | B1/C256 | 2 | 1.256 | 0.910 | 0.346 | 2 | 23344519487 |
| 1 | Active-only filter + payload | B1/C384 | 0 | 1.500 | 0.821 | 0.680 | 1 | 19647553939 |
| 1 | Active-only filter + payload | B1/C384 | 1 | 1.320 | 0.865 | 0.455 | 6 | 21768017716 |
| 1 | Active-only filter + payload | B1/C384 | 2 | 1.258 | 0.862 | 0.396 | 7 | 23090834165 |
| 1 | Active-only filter + payload | B64/C4 | 0 | 1.312 | 0.830 | 0.482 | 1 | 20321910284 |
| 1 | Active-only filter + payload | B64/C4 | 1 | 1.221 | 0.504 | 0.717 | 22 | 20516340004 |
| 1 | Active-only filter + payload | B64/C4 | 2 | 1.120 | 0.152 | 0.968 | 14 | 19937420423 |
| 1 | Active-only filter + payload | B64/C8 | 0 | 1.306 | 0.821 | 0.486 | 1 | 20498867703 |
| 1 | Active-only filter + payload | B64/C8 | 1 | 1.229 | 0.556 | 0.673 | 21 | 20732388526 |
| 1 | Active-only filter + payload | B64/C8 | 2 | 1.121 | 0.163 | 0.957 | 8 | 20209338714 |
| 1 | Active-only filter + payload | B128/C4 | 0 | 1.280 | 0.783 | 0.497 | 1 | 21258748071 |
| 1 | Active-only filter + payload | B128/C4 | 1 | 1.203 | 0.593 | 0.611 | 35 | 21510520435 |
| 1 | Active-only filter + payload | B128/C4 | 2 | 1.099 | 0.400 | 0.698 | 54 | 21143444263 |
| 3 | No filter / no payload | B1/C64 | 0 | 1.493 | 0.879 | 0.614 | 3 | 21827600831 |
| 3 | No filter / no payload | B1/C64 | 1 | 1.323 | 0.884 | 0.439 | 6 | 22653926317 |
| 3 | No filter / no payload | B1/C64 | 2 | 1.255 | 0.862 | 0.393 | 7 | 23628746674 |
| 3 | No filter / no payload | B1/C128 | 0 | 2.567 | 1.497 | 1.070 | 10 | 40066171405 |
| 3 | No filter / no payload | B1/C128 | 1 | 2.292 | 1.507 | 0.785 | 27 | 44570541258 |
| 3 | No filter / no payload | B1/C128 | 2 | 2.314 | 1.373 | 0.941 | 28 | 44348247758 |
| 3 | No filter / no payload | B1/C256 | 0 | 2.801 | 1.514 | 1.287 | 3 | 47216198176 |
| 3 | No filter / no payload | B1/C256 | 1 | 2.847 | 1.892 | 0.954 | 15 | 57910710635 |
| 3 | No filter / no payload | B1/C256 | 2 | 2.797 | 1.893 | 0.905 | 14 | 56930115742 |
| 3 | No filter / no payload | B1/C384 | 0 | 2.826 | 1.534 | 1.293 | 3 | 48449558653 |
| 3 | No filter / no payload | B1/C384 | 1 | 2.859 | 2.016 | 0.843 | 14 | 60149168155 |
| 3 | No filter / no payload | B1/C384 | 2 | 2.871 | 2.001 | 0.869 | 12 | 60470801317 |
| 3 | No filter / no payload | B64/C4 | 0 | 2.567 | 0.649 | 1.919 | 62 | 53355227407 |
| 3 | No filter / no payload | B64/C4 | 1 | 2.617 | 0.760 | 1.856 | 66 | 54004980326 |
| 3 | No filter / no payload | B64/C4 | 2 | 2.586 | 0.641 | 1.945 | 68 | 53224248411 |
| 3 | No filter / no payload | B64/C8 | 0 | 2.834 | 2.014 | 0.820 | 3 | 55211614510 |
| 3 | No filter / no payload | B64/C8 | 1 | 2.856 | 2.111 | 0.745 | 4 | 54315621412 |
| 3 | No filter / no payload | B64/C8 | 2 | 2.858 | 2.117 | 0.741 | 3 | 54061212228 |
| 3 | No filter / no payload | B128/C4 | 0 | 2.694 | 1.440 | 1.255 | 77 | 59405900345 |
| 3 | No filter / no payload | B128/C4 | 1 | 2.782 | 1.690 | 1.092 | 56 | 59034039157 |
| 3 | No filter / no payload | B128/C4 | 2 | 2.762 | 1.571 | 1.191 | 63 | 58949204890 |
| 3 | No filter / no payload | B128/C8 | 0 | 2.807 | 1.987 | 0.820 | 6 | 56629382056 |
| 3 | No filter / no payload | B128/C8 | 1 | 2.829 | 2.060 | 0.769 | 3 | 54825159760 |
| 3 | No filter / no payload | B128/C8 | 2 | 2.818 | 2.048 | 0.770 | 3 | 54248726232 |
| 3 | Active-only filter + payload | B1/C64 | 0 | 1.517 | 0.866 | 0.651 | 1 | 22033790918 |
| 3 | Active-only filter + payload | B1/C64 | 1 | 1.338 | 0.914 | 0.424 | 1 | 22230196596 |
| 3 | Active-only filter + payload | B1/C64 | 2 | 1.350 | 0.925 | 0.424 | 1 | 22359848991 |
| 3 | Active-only filter + payload | B1/C128 | 0 | 2.516 | 1.312 | 1.204 | 18 | 38926748203 |
| 3 | Active-only filter + payload | B1/C128 | 1 | 2.263 | 1.463 | 0.800 | 13 | 40613313679 |
| 3 | Active-only filter + payload | B1/C128 | 2 | 2.312 | 1.421 | 0.891 | 25 | 41296509831 |
| 3 | Active-only filter + payload | B1/C256 | 0 | 2.782 | 1.460 | 1.323 | 4 | 49025387579 |
| 3 | Active-only filter + payload | B1/C256 | 1 | 2.794 | 1.834 | 0.960 | 19 | 57706015435 |
| 3 | Active-only filter + payload | B1/C256 | 2 | 2.799 | 1.748 | 1.050 | 24 | 55928771205 |
| 3 | Active-only filter + payload | B1/C384 | 0 | 2.807 | 1.429 | 1.378 | 3 | 45560820918 |
| 3 | Active-only filter + payload | B1/C384 | 1 | 2.801 | 1.821 | 0.980 | 28 | 59419825074 |
| 3 | Active-only filter + payload | B1/C384 | 2 | 2.833 | 1.952 | 0.881 | 8 | 57251752002 |
| 3 | Active-only filter + payload | B64/C4 | 0 | 2.388 | 0.214 | 2.174 | 29 | 41670044415 |
| 3 | Active-only filter + payload | B64/C4 | 1 | 2.410 | 0.292 | 2.119 | 44 | 43169247087 |
| 3 | Active-only filter + payload | B64/C4 | 2 | 2.364 | 0.223 | 2.142 | 29 | 41712010823 |
| 3 | Active-only filter + payload | B64/C8 | 0 | 2.755 | 1.776 | 0.979 | 6 | 53490309796 |
| 3 | Active-only filter + payload | B64/C8 | 1 | 2.793 | 1.936 | 0.857 | 11 | 54470501112 |
| 3 | Active-only filter + payload | B64/C8 | 2 | 2.782 | 1.922 | 0.860 | 11 | 54730542733 |
| 3 | Active-only filter + payload | B128/C4 | 0 | 2.570 | 1.347 | 1.223 | 63 | 55542413482 |
| 3 | Active-only filter + payload | B128/C4 | 1 | 2.649 | 1.333 | 1.316 | 79 | 56175306446 |
| 3 | Active-only filter + payload | B128/C4 | 2 | 2.631 | 1.326 | 1.306 | 90 | 55328400555 |

Summed scan-stage ns/query is the sum of per-node cumulative scan timers divided by summed per-node ring-completed query members, including warmup members. This stage timer may overlap across workers and nodes; it is not request latency, CPU time, or DRAM traffic.

## Matched same-concurrency worker comparison

These comparisons pair worker limits at identical category, batch size, and concurrency. Percentage changes are descriptive for this fixed order and shared COW/page-cache run.

| Category | Batch | Concurrency | HTTP RPS w1 | HTTP RPS w3 | Change % | Query QPS w1 | Query QPS w3 | p95 ms w1/w3 | p99 ms w1/w3 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| No filter / no payload | 1 | 64 | 734.81 | 745.05 | +1.39% | 734.81 | 745.05 | 100.22/101.50 | 117.41/122.65 |
| No filter / no payload | 1 | 128 | 860.33 | 1300.13 | +51.12% | 860.33 | 1300.13 | 186.73/119.62 | 201.19/137.49 |
| No filter / no payload | 1 | 256 | 903.84 | 1569.09 | +73.60% | 903.84 | 1569.09 | 348.39/214.43 | 362.79/227.21 |
| No filter / no payload | 1 | 384 | 890.24 | 1784.63 | +100.47% | 890.24 | 1784.63 | 480.76/328.27 | 501.99/383.25 |
| No filter / no payload | 64 | 4 | 15.36 | 29.62 | +92.84% | 983.12 | 1895.84 | 322.99/166.28 | 366.09/190.93 |
| No filter / no payload | 64 | 8 | 15.88 | 40.01 | +151.93% | 1016.32 | 2560.36 | 598.96/241.34 | 622.74/270.23 |
| No filter / no payload | 128 | 4 | 7.90 | 17.43 | +120.71% | 1011.06 | 2231.49 | 599.14/295.60 | 619.73/314.70 |
| No filter / no payload | 128 | 8 | 7.92 | 20.70 | +161.37% | 1013.53 | 2649.02 | 1117.46/450.28 | 1180.52/539.57 |
| Active-only filter + payload | 1 | 64 | 653.36 | 728.07 | +11.43% | 653.36 | 728.07 | 118.53/100.84 | 138.78/113.84 |
| Active-only filter + payload | 1 | 128 | 871.79 | 1300.13 | +49.13% | 871.79 | 1300.13 | 189.13/123.25 | 203.92/144.82 |
| Active-only filter + payload | 1 | 256 | 855.34 | 1500.90 | +75.47% | 855.34 | 1500.90 | 356.75/232.65 | 370.38/252.86 |
| Active-only filter + payload | 1 | 384 | 867.07 | 1674.67 | +93.14% | 867.07 | 1674.67 | 498.84/346.90 | 551.76/405.82 |
| Active-only filter + payload | 64 | 4 | 13.79 | 25.25 | +83.10% | 882.41 | 1615.71 | 353.39/192.23 | 380.06/207.88 |
| Active-only filter + payload | 64 | 8 | 13.84 | 34.56 | +149.62% | 885.97 | 2211.60 | 668.92/288.08 | 726.17/320.07 |
| Active-only filter + payload | 128 | 4 | 6.84 | 14.98 | +118.88% | 876.05 | 1917.48 | 680.92/336.50 | 700.62/354.47 |

Pairs omitted because at least one arm has a capacity rejection:

- Active-only filter + payload, B128/C8: At least one worker arm has no accepted timing row for this cell.

## Normalized B1 comparison: worker 1 C128 vs worker 3 C384

Concurrency per configured worker is 128 in both arms. This is a separate operating-point comparison; total concurrency and latency are not matched.

| Category | HTTP RPS w1 C128 / w3 C384 | Query QPS w1 / w3 | QPS per configured worker w1 / w3 | p50 ms w1 / w3 | p95 ms w1 / w3 | p99 ms w1 / w3 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| No filter / no payload | 860.33 / 1784.63 | 860.33 / 1784.63 | 860.33 / 594.88 | 142.18 / 204.67 | 186.73 / 328.27 | 201.19 / 383.25 |
| Active-only filter + payload | 871.79 / 1674.67 | 871.79 / 1674.67 | 871.79 / 558.22 | 142.46 / 220.97 | 189.13 / 346.90 | 203.92 / 405.82 |

## Scope and reproducibility

The dataset contract is 3,000,000 points × 512 dimensions, SQ8; metadata is present in storage for both prepared categories. Each query returns Top-10; each timing cell has a separate 1,024-query F32 oracle check. Replication factor is 1, HNSW is disabled, and each of three nodes has a shared three-CPU mask with no per-thread pinning.

The same historical query/oracle set is repeated across cells. This report does not claim fresh-holdout recall or generalization. The fixed worker order, COW reuse, and host page-cache state can affect comparisons.

No maximum-capacity or memory-bandwidth-saturation claim is made. No uncore or direct DRAM counter is part of this campaign.

Source commit `0aa62c281b7262368ca6f1ed69de71647be10ac0` (tree `ae19530f171d177f6e517436e655e0e9571b8b50`); engine ELF SHA-256 `074f45b364a8e80da3fb9307d637812072fd755f56b91aeb8bdd4bf92b1ba60d`. Load client binary SHA-256 `3ac5765e0116dd6d4776996bc0e717bb2abecdd1950302b63aa4d00e1400436f`; source SHA-256 `16c957e8539df6c91e01b993e97314d464615845b9be7715bfb2a300f9c48126`.

Frozen run-matrix SHA-256 values: `30555828cc60766bf8bc6e8a2dcfd2ab39feeb72afa0fe7b8166fd4926578696`, `9748cc6b842d9381a661890274b3997df4a448ab3d314dc660665e753ec877bc`; retained capacity-attempt runner `0aee37984395b5245304198f711b6d7732ed5f221d98ab189f330cc18e70223d`.

Campaign receipts (SHA-256): `62fbdccf760aefc6849ebfc401584bb9537addeabe3650fd81a8103f2847e1b1`, `f682001545de76c82616406d344574cd8a4b5a01ee51417ed783e0c475588fc0`, `8a42861313d38a5aa819d7b8fcbce1cdf9ae5594f1ddd2bf9954abde90beb56f`.

## Explicit row adjudication

The following row was retained under the third runner's explicit interrupted-campaign provenance after its original receipt rejected a client dispatch-window check. Its raw rejection flag and original receipt digest remain recorded; the exporter does not rewrite the raw receipt.

- Source receipt `62fbdccf760aefc6849ebfc401584bb9537addeabe3650fd81a8103f2847e1b1`, row ordinal 15: `dispatch_window_matches` was explicitly corrected: the pinned Go client enforces the configured 30-second deadline, while `actual_dispatch_duration_s` is the last request start offset, not dispatch-window duration. The last offset and elapsed must be finite, positive, and ordered; no 29.9-second lower bound applies; report SHA-256 `56ca2c3af4e1a938b24d08c381df6b89095b85dc4eda76ee14337b0ddfd20dd5`.

Publication clarification: these measurements come from three sequential COW startups: 15 retained one-worker cells, one rejected one-worker B128/C8 attempt, and 16 three-worker cells. All use fixed 16-request warmups; host page cache was not reset. They are not randomized paired runs. The other two payload/filter categories and native Qdrant were not rerun in this diagnostic.

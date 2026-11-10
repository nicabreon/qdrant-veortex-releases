# Veortex shared three-CPU SQ8 full matrix

Revision date: 10 November 2026. Native values are explicitly earlier-run H0 references; this campaign measured only Veortex AVX-512 VNNI and Auto.

**Curation state:** PROVISIONAL — RESTORATION PENDING. Campaign `shared-cpu-fullmatrix-20261110t075650z` status `TIMING`. Fresh measurements: 1/1 accepted; 0 rejected; 31 expected cells not recorded. Historical native reference cells: 16 (not new tests).

Candidate source `560259c84af2b292867b9b2970ec731bcd33e07f`, ELF `63e9c5d1ffb9075bcfa3981c04a65c8240c9b18f1ad095456a93e9943ae466c6`, common Go client `5477653066b11acf0ce1f53545f6bd98aad9175ed3c4072a89b051298e05cde0`. Six focused collection tests passed. Four support_cpu tests passed after compiling the exact production module and its four tests directly with a rustc --test wrapper; the full segment test suite was not run. Selected pipeline: `SEPARATE_TOPK=1` (separate TopK and deferred payload materialization). That setting was selected after the passing same-ELF focused A/B: [report](shared-postprocessing-ab-20261110.md).

The fixture is 3 million 512D cosine vectors, SQ8 flat search, three one-million-point shards, three payload indexes, and HNSW disabled. Each node had a three-vCPU quota, a disjoint full three-CPU mask (4–6, 7–9, 10–12), and no per-thread pinning. Veortex used shared postprocessing placement, three ring workers, a 2 GiB queue budget, and three search/Rayon threads. Both fresh Veortex backends ran the same selected pipeline mode and ELF.

Each category uses 1,024 distinct saved Top10 queries, checked against the pinned FP32 oracle before timing. Independent checks currently passed: 1/8; a complete timing matrix requires every category on both fresh backends. Every timed cell has 16 warmup requests, a 60-second dispatch, and a final drain. HTTP req/s = successful HTTP requests / elapsed; query/s = successful query members / elapsed. Both include final drain. p50/p95/p99 are full-response validated latency percentiles. Errors include failed requests/queries, HTTP 429, transport, protocol, and correctness failures.

## Accepted measurements and historical native references

The tables contain only accepted rows. Measurement acceptance means correctness, route, CPU-mask/work, ISA, and error gates passed; it is not a throughput target. Valid lower-throughput measurements remain included. `Native (prior H0)` is a previous three-CPU run, not measured alongside or rerun in this campaign. Rate/latency cell: HTTP req/s / query/s / p50 / p95 / p99 ms / elapsed s.

### No filter / no payload

| B / C | Engine and scope | HTTP req/s / query/s / p50 / p95 / p99 / elapsed | Requests success/fail | Queries success/fail | Exact truth matches | 429 / transport / protocol / correctness errors |
|---:|---|---:|---:|---:|---:|---:|
| B1 / C64 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 55.43 / 55.43 / 1137.39 / 1546.88 / 1881.56 / 61.11 | 3387 / 0 | 3387 / 0 | 3387 | 0 / 0 / 0 / 0 |
| B1 / C64 | Veortex AVX-512 VNNI (AMX disabled) | 226.60 / 226.60 / 282.70 / 296.75 / 313.74 / 60.16 | 13632 / 0 | 13632 / 0 | 13632 | 0 / 0 / 0 / 0 |
| B1 / C128 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 55.71 / 55.71 / 2280.24 / 2461.91 / 2854.50 / 62.17 | 3464 / 0 | 3464 / 0 | 3464 | 0 / 0 / 0 / 0 |
| B64 / C4 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 4.02 / 257.33 / 986.82 / 1078.83 / 1261.08 / 60.93 | 245 / 0 | 15680 / 0 | 15680 | 0 / 0 / 0 / 0 |
| B128 / C4 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 2.03 / 259.37 / 1965.13 / 2419.23 / 2990.62 / 61.69 | 125 / 0 | 16000 / 0 | 16000 | 0 / 0 / 0 / 0 |

### No filter / payload

| B / C | Engine and scope | HTTP req/s / query/s / p50 / p95 / p99 / elapsed | Requests success/fail | Queries success/fail | Exact truth matches | 429 / transport / protocol / correctness errors |
|---:|---|---:|---:|---:|---:|---:|
| B1 / C64 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 54.08 / 54.08 / 1168.60 / 1375.51 / 1662.05 / 61.07 | 3303 / 0 | 3303 / 0 | 3303 | 0 / 0 / 0 / 0 |
| B1 / C128 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 54.27 / 54.27 / 2329.92 / 2899.84 / 3734.77 / 62.19 | 3375 / 0 | 3375 / 0 | 3375 | 0 / 0 / 0 / 0 |
| B64 / C4 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 4.00 / 255.84 / 982.57 / 1260.06 / 1418.92 / 60.79 | 243 / 0 | 15552 / 0 | 15552 | 0 / 0 / 0 / 0 |
| B128 / C4 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 2.00 / 255.44 / 1989.36 / 2520.61 / 2965.36 / 61.63 | 123 / 0 | 15744 / 0 | 15744 | 0 / 0 / 0 / 0 |

### Active only (~90%) / payload

| B / C | Engine and scope | HTTP req/s / query/s / p50 / p95 / p99 / elapsed | Requests success/fail | Queries success/fail | Exact truth matches | 429 / transport / protocol / correctness errors |
|---:|---|---:|---:|---:|---:|---:|
| B1 / C64 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 50.23 / 50.23 / 1268.74 / 1386.95 / 1677.05 / 61.20 | 3074 / 0 | 3074 / 0 | 3074 | 0 / 0 / 0 / 0 |
| B1 / C128 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 47.99 / 47.99 / 2666.88 / 2974.24 / 3420.46 / 62.56 | 3002 / 0 | 3002 / 0 | 3002 | 0 / 0 / 0 / 0 |
| B64 / C4 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 3.98 / 254.82 / 995.40 / 1293.28 / 1409.85 / 61.03 | 243 / 0 | 15552 / 0 | 15552 | 0 / 0 / 0 / 0 |
| B128 / C4 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 1.99 / 254.83 / 2004.97 / 2404.76 / 2658.87 / 61.78 | 123 / 0 | 15744 / 0 | 15744 | 0 / 0 / 0 / 0 |

### Active + position exclusion (~9%) / payload

| B / C | Engine and scope | HTTP req/s / query/s / p50 / p95 / p99 / elapsed | Requests success/fail | Queries success/fail | Exact truth matches | 429 / transport / protocol / correctness errors |
|---:|---|---:|---:|---:|---:|---:|
| B1 / C64 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 119.30 / 119.30 / 534.13 / 601.67 / 669.96 / 60.47 | 7214 / 0 | 7214 / 0 | 7214 | 0 / 0 / 0 / 0 |
| B1 / C128 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 120.32 / 120.32 / 1057.46 / 1261.05 / 1473.20 / 60.98 | 7337 / 0 | 7337 / 0 | 7337 | 0 / 0 / 0 / 0 |
| B64 / C4 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 14.21 / 909.52 / 281.15 / 346.82 / 386.55 / 60.23 | 856 / 0 | 54784 / 0 | 54784 | 0 / 0 / 0 / 0 |
| B128 / C4 | Qdrant native 1.20 — earlier three-CPU run, not rerun | 7.06 / 903.89 / 565.16 / 685.52 / 733.47 / 60.47 | 427 / 0 | 54656 / 0 | 54656 | 0 / 0 / 0 / 0 |

## Rejected fresh-row diagnostics

No fresh timing row was rejected.

Independent accuracy: 1/8 fresh runs passed. Per-node ring gates require each node's submitted/completed delta to equal warmup query members plus successful timed query members, with zero fallback and HNSW calls. AVX rows prove VNNI-positive/AMX-zero on each node; Auto rows prove AMX work on each node. CPU evidence requires active work and each sampled thread's full three-CPU mask.

Per-node stage work and queue-wait counter deltas, plus their three-node means, are retained as diagnostics in JSON and CSV. Stage and wait totals can overlap; they are not additive measures of critical-path latency and do not identify a root cause by themselves.

Original-container restoration healthy: False; immutable lower metadata unchanged: False; overlays removed before restart: False; cleanup errors: 0.

The historical native comparison is cross-run, not a concurrent native arm. Builds use unmatched compiler flags; each cell was measured once in a fixed sequence on a shared VM. These are selected load points, not maximum capacity, confidence intervals, or long-duration stability claims. Curated outputs omit raw query bodies, client reports, credentials, and runtime environment values.

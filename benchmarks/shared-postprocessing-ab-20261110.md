# Same-ELF shared postprocessing A/B

Revision date: 10 November 2026. This focused B1/C128 run compares the postprocessing pipeline setting with the same Veortex ELF and three shared CPUs per node.

**Curation state:** FINAL CURATION; restoration verified. Campaign status: `MEASUREMENTS_COMPLETE_RECORDED_SCOPE`. 4/4 recorded timing rows accepted; 0 rejected; 0 expected cells were not recorded.

Each node had a 3-vCPU container quota and full disjoint 3-CPU mask (4–6, 7–9, 10–12); no thread affinity pinning was applied. Both arms used `POSTPROCESSING_PLACEMENT=shared`, Auto tier, three ring workers, and the same 2 GiB query-admission budget. The only intended environment difference was `SEPARATE_TOPK`: 0 runs inline/combined TopK; 1 uses separate TopK and deferred payload-materialization workers on the same shared mask. This tests pipeline scheduling under the same CPU allocation; it is not a CPU-count scaling test.

Candidate source `560259c84af2b292867b9b2970ec731bcd33e07f` and ELF `63e9c5d1ffb9075bcfa3981c04a65c8240c9b18f1ad095456a93e9943ae466c6`; common Go client `5477653066b11acf0ce1f53545f6bd98aad9175ed3c4072a89b051298e05cde0`. Six focused collection tests passed. Four support_cpu tests passed after compiling the exact production module and its four tests directly with a rustc --test wrapper; the full segment test suite was not run. Common-client checks: 21.

All cells use 1,024 distinct saved Top10 queries in each category. Independent FP32 accuracy checks are currently 4/4 complete; the final report requires both categories on each arm (ordered IDs and scores within 1e-6). Timed rows have 16 successful warmups, 60 seconds of dispatch, and a final drain. HTTP req/s = successful HTTP requests / actual elapsed; query/s = successful queries / actual elapsed. Elapsed includes final drain. p50/p95/p99 are full-response validated latency percentiles.

## Accepted timing rows

Rate and latency cells are HTTP req/s / query/s / p50 / p95 / p99 ms / elapsed s. Rows appear here only when correctness, route, CPU-mask/work, ISA, and zero-error gates passed. This acceptance gate is not a performance target; valid low-throughput rows remain visible.

| Category | Pipeline mode | HTTP req/s / query/s / p50 / p95 / p99 / elapsed | Requests success/fail | Queries success/fail | Exact truth matches | 429 / transport / protocol / correctness errors |
|---|---|---:|---:|---:|---:|---:|
| No filter / no payload | SEPARATE_TOPK=0 — inline/combined TopK | 1066.96 / 1066.96 / 118.91 / 145.65 / 187.64 / 60.11 | 64136 / 0 | 64136 / 0 | 64136 | 0 / 0 / 0 / 0 |
| No filter / no payload | SEPARATE_TOPK=1 — separate TopK + deferred payload materialization | 1300.86 / 1300.86 / 95.49 / 123.85 / 141.55 / 60.10 | 78182 / 0 | 78182 / 0 | 78182 | 0 / 0 / 0 / 0 |
| Active only (~90%) / payload | SEPARATE_TOPK=1 — separate TopK + deferred payload materialization | 1234.17 / 1234.17 / 101.81 / 129.89 / 146.19 / 60.08 | 74150 / 0 | 74150 / 0 | 74150 | 0 / 0 / 0 / 0 |
| Active only (~90%) / payload | SEPARATE_TOPK=0 — inline/combined TopK | 760.96 / 760.96 / 170.56 / 181.42 / 188.12 / 60.13 | 45757 / 0 | 45757 / 0 | 45757 | 0 / 0 / 0 / 0 |

## Rejected-row diagnostics

No rejected timing rows recorded.

The per-node ring gate requires submitted and completed query deltas to equal 16 warmups plus all successful timed queries on every node, with zero fallback and HNSW calls. Accepted rows also require Auto AMX work on every node, full three-CPU masks with active search work, and both treatment worker pools sampled on their full masks; the control must have neither pool. Worker sampling proves presence and mask only, not utilization.

Independent accuracy: 4/4 runs passed. Original-container restoration healthy: True; immutable lower metadata unchanged: True; overlays removed before restart: True; cleanup errors: 0.

The same ELF and common client were used in both arms, so compiler flags were held constant within this A/B. The fixed A/B/B/A order and changing host state remain possible confounders. This scope supports the recorded B1/C128 cases only; it does not establish universal speedup, saturation, or a performance distribution.

Curated JSON and CSV retain every recorded timing row, including rejection reasons and CPU/ring/worker evidence. Raw client reports, query bodies, credentials, and private environment values are excluded.

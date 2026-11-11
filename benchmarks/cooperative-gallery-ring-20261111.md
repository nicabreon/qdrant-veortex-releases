# Cooperative gallery ring: three-node cluster diagnostic

**Outcome:** the candidate production-path gallery-split adapter passed all eight accepted cells, per-cell F32 accuracy, ring-route, three-scan-worker, and restoration checks. It was **not promoted**: each candidate row was slower than its historical three-worker query-split counterpart. The comparison uses different source commits and ELFs, so it is not a same-binary A/B or causal attribution.

The measured fixture was 3,000,000 512D cosine SQ8 points across three nodes, 1,000,000 points per node, with three shared CPUs per node and no per-thread pinning. The workload used B1/C64, C128, C256, and C384 for both unfiltered/no-payload and active-only (~90% eligible)/payload categories. Each cell had a 30-second dispatch window followed by drain, Top10 output, a 12-candidate-per-segment rescore cap, and 1,024 F32-oracle queries checked before timing.

| Category | B1/C | Candidate HTTP req/s | p50 / p95 / p99 (ms) | Success / failed | Historical 3-worker query-split req/s | Change | Candidate process CPU equivalents N0 / N1 / N2 |
|---|---:|---:|---:|---:|---:|---:|---:|
| unfiltered_no_payload | 1/64 | **599.45** | 105.16 / 122.62 / 129.06 | 18,023 / 0 | 745.05 | -19.5% | 2.09 / 2.05 / 2.10 |
| unfiltered_no_payload | 1/128 | **825.20** | 154.14 / 168.66 / 180.68 | 24,868 / 0 | 1300.13 | -36.5% | 2.30 / 2.27 / 2.31 |
| unfiltered_no_payload | 1/256 | **1139.27** | 224.35 / 239.76 / 247.20 | 34,367 / 0 | 1569.09 | -27.4% | 2.62 / 2.55 / 2.58 |
| unfiltered_no_payload | 1/384 | **1299.96** | 289.31 / 365.77 / 413.11 | 39,344 / 0 | 1784.63 | -27.2% | 2.64 / 2.55 / 2.59 |
| active_only | 1/64 | **569.14** | 110.20 / 128.14 / 135.99 | 17,121 / 0 | 728.07 | -21.8% | 2.09 / 2.04 / 2.08 |
| active_only | 1/128 | **772.75** | 164.28 / 182.12 / 194.14 | 23,272 / 0 | 1300.13 | -40.6% | 2.32 / 2.30 / 2.26 |
| active_only | 1/256 | **998.93** | 254.26 / 278.95 / 288.05 | 30,157 / 0 | 1500.90 | -33.4% | 2.68 / 2.56 / 2.51 |
| active_only | 1/384 | **1115.83** | 342.55 / 406.55 / 444.82 | 33,750 / 0 | 1674.67 | -33.4% | 2.72 / 2.55 / 2.59 |

All eight matched category/concurrency pairs were slower in the candidate, by 19.5% to 40.6%. The historical rows are from source `0aa62c281b7262368ca6f1ed69de71647be10ac0` / ELF `074f45b364a8e80da3fb9307d637812072fd755f56b91aeb8bdd4bf92b1ba60d`; this candidate uses source `085399a27a74a58fad9017b2bacaab9a40fcf455` / ELF `6a374536ddd71bd81f247c664f8a56dd82e413abfda1ac7b7a8d17cd967b008e`. The categories have identical 1,024-query oracle hashes across the two campaigns, but their manifest hashes differ. Treat this as a historical diagnostic comparison, not an isolated estimate of the gallery-split change.

Every candidate node proved positive completed tasks from `veortex-scan-0`, `veortex-scan-1`, and `veortex-scan-2`; peak active scan tasks reached three, task failures were zero, and the pool was idle at each drained row boundary. Per-node total and per-worker task counts, scan-worker CPU ticks, process CPU, route counters, logical work ratios, timing/report hashes, and historical row identities are in the [curated JSON](cooperative-gallery-ring-20261111.json) and [CSV](cooperative-gallery-ring-20261111.csv).

The candidate logical reuse diagnostic `query_vector_dots / gallery_vectors_read` is a work-counter ratio (about 47–91 across per-node cells), not physical memory traffic or DRAM bandwidth. Whole-process CPU equivalents cover the observer window including warmup, timed dispatch, and drain; scan-worker tick equivalents are a separate named-thread diagnostic. Cumulative stage timers can overlap and are not additive end-to-end latency. This campaign makes no bandwidth-saturation or performance-causality claim.

All eight F32 checks passed 1,024/1,024 queries at tolerance `1e-6`; all timed requests succeeded with zero failed queries, zero route fallback, and zero HNSW calls. Originals were restored healthy, lower metadata remained unchanged, and cleanup reported no errors. The preceding 05:17 attempt remains rejected (receipt SHA-256 `108a2ae762141a4de9dda068df68082d1d59f32fc364c1207c3339e7d0879fe0`): its gallery-scan CPU-proof gate failed, although cleanup restored the originals without errors, and it was not reclassified. The accepted 05:31 follow-up uses the corrected validated-thread-interval accounting.

The separate 4,334 scan-query/s result came from a 1M-point scorer-only component harness and is not demonstrated HTTP capacity. The requested efficiency goal remains at least 90% of an equivalent kernel baseline; this adapter has not met that goal. A controlled standalone scheduler experiment is the next step to isolate the gap. A source-derived scratch-size estimate is not a memory-traffic measurement. A later source edit `a492425e6` is unbuilt and unmeasured and is not represented here; its engine build is deferred while the standalone experiment proceeds.

## Provenance

Accepted receipt SHA-256: `ea71b92a2a716b257ddf97953aa3832b781aa880cb53bcb945a3896c292b4647`. Candidate client SHA-256: `3ac5765e0116dd6d4776996bc0e717bb2abecdd1950302b63aa4d00e1400436f`. Candidate build receipt SHA-256: `f9af0a3905b4bc3caaa846338380695c2bf5240543e0021bbb26d4cc4f0efb8c`. Runner / observer / CPU-evidence helper SHA-256: `8903437e1d10acb15d8b8acc912ecfa63caca1298a6c2b8a2d7607aa9ae9d26f` / `547754ccce091ae8564f5a4d84c8d212dd60d0b88694aa4634657fa0143f0bed` / `8380d7c6c1aa6c7bed9db752ee5608f732b75b613553660e89bfcbbeb1863c04`.

The historical comparator is the existing [worker-scaling batch/concurrency dataset](worker-scaling-batch-concurrency-20261111.json), source commit `0aa62c281b7262368ca6f1ed69de71647be10ac0` and ELF SHA-256 `074f45b364a8e80da3fb9307d637812072fd755f56b91aeb8bdd4bf92b1ba60d`.

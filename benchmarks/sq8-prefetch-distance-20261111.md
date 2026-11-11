# SQ8 prefetch distance — 11 November 2026

This is a two-arm same-ELF configuration probe: VX_PF8=6 control versus VX_PF8=0, with VX_PFH=9 fixed and fused score pruning disabled in both profiles. All four accepted timing rows are retained. **Outcome: keep the default `VX_PF8=6`.** Turning it off reduced throughput by 17.8% without filter/payload and 19.0% with active filter/payload. The 5,000 HTTP RPS B1 target remains unmet.

## Scope

- Source: `a8af3ee1ceb3a7fbee4deec705b8dbda32f9585e` (tree `bb934e4c482c791269291ac31887a2ced17875c6`), based on `560259c84af2b292867b9b2970ec731bcd33e07f`; 36 changed files pinned by source-pin SHA `745625f6529a24cd31f24129a8df735283117ef3fd63ec028ebd3bb972ccc75a`.
- Candidate ELF SHA-256: `ba68b4b06cb5dacf3419aafa83a23c23009de546c9868dabf945e3aa06f0e81d`; the same candidate ELF served both profiles.
- Candidate build receipt SHA-256: `29ff4ce703bdda08b01ae17b75c0c8bf202ba5371fa11dc7f239daf3d0eb1dcd`. Focused selections: quantization / turboquant:: (125 cases), quantization / encoded_vectors_u8:: (4 cases), segment / index::hnsw_index::point_scorer::tests:: (34 cases). This is only the pinned focused-test scope.
- Workload: B1/C512, 3M × 512 cosine SQ8 points, HNSW disabled, Top10, oversampling 1.2 (12 candidates per segment), and categories `unfiltered_no_payload, active_only`.
- Runtime: three nodes, each with shared CPU mask `[[4, 5, 6], [7, 8, 9], [10, 11, 12]]` and a 3-CPU Docker quota. Per-thread pinning was disabled. Admission permits stayed at 640, fast-join capacity at 64, physical ring lane limit at 96, and ring/search/Rayon worker limits at 3. All stages share their node CPU set.
- Each profile/category pair has a passing F32 check over 1,024 manifest queries at score tolerance 1e-6. The client records 16 warmups followed by a 30-second measured dispatch.
- The only profile environment difference is VX_PF8. The 28 common environment entries are unchanged; VX_PFH remains 9 and QDRANT_VEORTEX_SQ8_FUSED_SCORE_PRUNING remains 0 in both profiles.
- The private cached score-store policy is unchanged. Global SQ8 streaming-store counters are not used as a proxy for this setting.

- Metadata is present on every point in both categories. Active-only means the approximately 90% active filter **with payload enabled**.
- HTTP RPS uses successful completed responses / actual monotonic elapsed time, including drain and validation. Timed requests reuse saved 1,024-query truth pairs; this is not a fresh holdout, and the historical gallery seed remains unknown. C512 latency includes queueing and is not single-request latency.
- The same COW dataset is reused, with no page-cache reset. The candidate ELF is an experimental build, not the downloadable V45.1 binary. Guest CPU allocation does not establish dedicated host cores.

## Results

| VX_PF8 | Category | Successful / failed HTTP | Actual HTTP RPS | p50 (ms) | p95 (ms) | p99 (ms) |
|---|---|---:|---:|---:|---:|---:|
| 6 (control) | No filter / no payload | 58,305 / 0 | 1,931.96 | 260.20 | 395.38 | 438.49 |
| 6 (control) | Active filter (~90%) + payload | 50,817 / 0 | 1,684.40 | 301.26 | 458.28 | 517.35 |
| 0 (probe) | No filter / no payload | 48,027 / 0 | 1,588.81 | 322.28 | 459.80 | 516.73 |
| 0 (probe) | Active filter (~90%) + payload | 41,375 / 0 | 1,364.33 | 367.85 | 554.57 | 622.99 |

All four rows passed client quality, shared-CPU, intended AMX route, ring-admission, zero-fallback, and HNSW-disabled gates. Fused score pruning stayed disabled, and both fused AMX counters remained exactly zero on every node in both profiles. These counters are a zero-only guard, not evidence that the fused path ran.

This is an empirical software-prefetch tile-count configuration probe. It does not establish that software prefetch is the bottleneck or that samples identify hardware stalls. The table reports every accepted row, including regressions, within this workload, source, ELF, and runtime profile.

Receipt SHA-256: `8b895d4320f331cc3a77bb6013c7331a6ffc79649becf9b4cdde014c3d5e3e61`.

This public evidence was derived from the strict private curator; engine source remains private. Original containers were restored healthy, six before/after lower inventories were identical, and scratch/overlay cleanup completed without errors.

`VX_PF8` controls SQ8 gallery prefetch distance. Zero skips the software-prefetch scheduling branch, including its quotient calculations; the probe therefore measures that combined configuration change. `VX_PFH` controls instruction hint/scheduling bits and was held at 9. Neither score arithmetic nor rerank candidate count changed.

All rows, raw counter deltas, source/ELF/client/helper pins, and exact common flags are preserved in [JSON](sq8-prefetch-distance-20261111.json) and [CSV](sq8-prefetch-distance-20261111.csv). This supplements the [complete shared-CPU matrix](runtime-limits-20261110.md) without replacing its results.

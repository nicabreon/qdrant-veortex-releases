# SQ8 fused score pruning — 11 November 2026

This is a two-arm same-ELF comparison of fused score pruning off and on at PFH9. All four accepted timing rows are retained. **The candidate was not promoted:** throughput changed by -1.04% without filter/payload and +3.28% with active filter/payload. These single ordered A/B measurements do not establish a repeatable gain; the 5,000 HTTP RPS B1 target remains unmet.

## Scope

- Source: `a8af3ee1ceb3a7fbee4deec705b8dbda32f9585e` (tree `bb934e4c482c791269291ac31887a2ced17875c6`), based on `560259c84af2b292867b9b2970ec731bcd33e07f`; 36 changed files pinned by source-pin SHA `745625f6529a24cd31f24129a8df735283117ef3fd63ec028ebd3bb972ccc75a`.
- Candidate ELF SHA-256: `ba68b4b06cb5dacf3419aafa83a23c23009de546c9868dabf945e3aa06f0e81d`; the same candidate ELF served both profiles.
- Candidate build receipt SHA-256: `29ff4ce703bdda08b01ae17b75c0c8bf202ba5371fa11dc7f239daf3d0eb1dcd`. Focused selections: quantization / turboquant:: (125 cases), quantization / encoded_vectors_u8:: (4 cases), segment / index::hnsw_index::point_scorer::tests:: (34 cases). This is only the pinned focused-test scope.
- Workload: B1/C512, 3M × 512 cosine SQ8 points, HNSW disabled, Top10, oversampling 1.2 (12 candidates per segment), and categories `unfiltered_no_payload, active_only`.
- Runtime: three nodes, each with shared CPU mask `[[4, 5, 6], [7, 8, 9], [10, 11, 12]]` and a 3-CPU Docker quota. Per-thread pinning was disabled. Admission permits stayed at 640, fast-join capacity at 64, physical ring lane limit at 96, and ring/search/Rayon worker limits at 3. All stages share the node CPU set.
- Each profile/category pair has a passing F32 check over 1,024 manifest queries at score tolerance 1e-6. The client records 16 warmups followed by a 30-second measured dispatch.
- The private cached score-store policy is unchanged in both arms. Global SQ8 streaming-store counters are not evidence for fused score pruning.

- Metadata is present on every point in both categories. Active-only means the approximately 90% active filter **with payload enabled**. No-filter requests return no payload. Both search the distributed collection through the coordinator.
- Timed requests reuse the saved 1,024-query truth pairs; this is not a fresh holdout. The historical gallery seed remains unknown.
- Actual HTTP RPS is successful completed responses divided by monotonic elapsed time, including drain and body validation. B1 HTTP RPS equals query/s. C512 latency includes queuing and is not isolated single-request latency. Both arms reuse the same COW dataset without resetting page cache.

## Results

| Fused pruning | Category | Successful / failed HTTP | Actual HTTP RPS | p50 (ms) | p95 (ms) | p99 (ms) |
|---|---|---:|---:|---:|---:|---:|
| Off (control) | No filter / no payload | 56,577 / 0 | 1,873.95 | 270.63 | 403.92 | 447.62 |
| Off (control) | Active filter (~90%) + payload | 52,159 / 0 | 1,727.10 | 284.21 | 451.54 | 513.61 |
| On | No filter / no payload | 55,969 / 0 | 1,854.42 | 268.08 | 421.48 | 476.78 |
| On | Active filter (~90%) + payload | 53,781 / 0 | 1,783.67 | 279.85 | 430.33 | 495.56 |

All four rows passed client quality, shared-CPU, intended AMX route, ring-admission, zero-fallback, and HNSW-disabled gates. The off arm recorded exactly zero fused AMX calls and score-cell deltas on every node. The on arm recorded positive deltas for both counters on every node. The source-pinned counters count successful fused AMX calls and all score cells processed by those calls; no minimum counter fraction was required.

The table reports every accepted row, including any regressions. It does not treat global streaming-store telemetry as proof of fused-path use and does not claim results outside this workload, source, ELF, and runtime profile.

Receipt SHA-256: `a25c75f4d9bd1fe6f4ca49979b33327dd4e679e2b65326519d841e3447cafecb`.

This public report was derived from the strict private curator. Engine source remains private. The candidate ELF is not the downloadable V45.1 build. All 163 selected tests passed; this is not a full-workspace or lifecycle acceptance claim.

All 218,486 measured requests succeeded with ordered Top-10 IDs and scores matching their saved F32 truth within 1e-6. Original containers were restored healthy, all six lower-data inventories remained identical, and scratch/overlay cleanup completed without errors.

The opt-in still computes all dot products. It uses conservative owner cutoffs to avoid writing and handing off score lanes that cannot qualify; ties and unordered lanes remain candidates for canonical TopK processing. It changes neither rerank candidate count nor score arithmetic.

A separate read-only analysis of the earlier accepted CPU profile attributes 69.97% of captured ring period to the main AMX pipeline and 5.08% to its F32 epilogue. Within the pipeline, tile-load and dot instructions account for 79.38% of sampled period. These leaf user-CPU-clock samples do not measure hardware stalls or memory bandwidth. They suggest that score emission alone has limited scope, but do not establish why this A/B result changed.

The build used Rust 1.98.0, release opt-level 3, fat LTO, one codegen unit, and debug information disabled. An earlier build-driver attempt stopped because a test filter matched zero cases; the filter was corrected, and the failed attempt and passing receipt were retained. That attempt had no engine compile/test failure.

Full counter deltas, common flags, source/ELF/client/helper pins, and validation are in [JSON](sq8-fused-score-pruning-20261111.json) and [CSV](sq8-fused-score-pruning-20261111.csv). This two-category diagnostic supplements the [complete shared-CPU matrix](runtime-limits-20261110.md), which remains unchanged.

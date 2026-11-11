# SQ8 AMX operand-preload scorer diagnostic

**Decision: retain the existing baseline/default.** This is a scorer diagnostic.

The operand-preload schedule has small, mixed results in this synthetic scorer. Among the four route-eligible rows, three are slightly faster by their seven-sample medians and one is slightly slower. The largest loss is n=1,000,000, nq=32, which is a route control. These measurements do not justify promoting the schedule.

## Measurement scope

- Synthetic signed-I8 query by U8 gallery scoring; one process pinned to CPU 4.
- Same test binary and source for both arms; only the test-local schedule override changes.
- VX_PFH=9, VX_PF8=6; dimension 512, 516-byte vector stride, chunk size 1,024, 384 KiB score scratch.
- Vector counts: 100,000 and 1,000,000; query counts: 32, 64, 70, and 96.
- One paired warmup, then seven alternating baseline/preload pairs. Tables report medians, not latency tails.
- Telemetry is disabled during timed sweeps; cached SQ8 score stores are scoped for the sweep. Full score hashes and scalar spot-oracles are checked outside timing.
- Both tested gallery sizes produce an even gallery-tile count. PFH 9 makes the 2G2Q schedule eligible for 64 and 96 queries (four and six active query tiles). The 32- and 70-query cases (two and five tiles) are route controls. A separate telemetry-enabled correctness test checks the route counters.
- No production engine binary was built or promoted. This is not HTTP, retrieval-recall, or cluster-throughput evidence.

## Results

Delta is preload median minus baseline median; positive values mean preload took longer. Speedup is baseline divided by preload; values above 1 favor preload.

| Vectors | Queries | Preload route | Baseline median (ms) | Preload median (ms) | Delta (ms) | Speedup | Change (%) |
|---:|---:|:---|---:|---:|---:|---:|---:|
| 100,000 | 32 | control | 2.963283 | 3.000788 | +0.037505 | 0.987502 | +1.27% |
| 100,000 | 64 | eligible | 3.421692 | 3.434299 | +0.012607 | 0.996329 | +0.37% |
| 100,000 | 70 | control | 4.900986 | 4.945409 | +0.044423 | 0.991017 | +0.91% |
| 100,000 | 96 | eligible | 4.247972 | 4.183078 | -0.064894 | 1.015513 | -1.53% |
| 1,000,000 | 32 | control | 32.730931 | 33.589579 | +0.858648 | 0.974437 | +2.62% |
| 1,000,000 | 64 | eligible | 41.628405 | 41.241341 | -0.387064 | 1.009385 | -0.93% |
| 1,000,000 | 70 | control | 55.061412 | 54.926931 | -0.134481 | 1.002448 | -0.24% |
| 1,000,000 | 96 | eligible | 46.682824 | 46.506267 | -0.176557 | 1.003796 | -0.38% |

<details>
<summary>Seven raw samples and score hashes</summary>


| Vectors | Queries | Baseline samples (ns) | Preload samples (ns) | Matching full-score hash |
|---:|---:|:---|:---|:---|
| 100,000 | 32 | [3582206,3177150,3117046,2963283,2883139,2779025,2684938] | [3444721,3269591,3136750,3000788,2785243,2814051,2798873] | a48b78f2e9e2cd54 |
| 100,000 | 64 | [3654770,3536064,3524746,3375029,3356082,3421692,3367884] | [3489460,3513465,3434299,3545510,3296899,3314611,3399776] | 763f3fa7ea447658 |
| 100,000 | 70 | [5244468,4903795,4791219,4861572,4938029,4900986,4867652] | [5023510,5014972,4827409,4763019,4931719,4945409,5725021] | 726ff6bf7d829e54 |
| 100,000 | 96 | [4298408,4247972,4486681,4237786,4179313,4246795,4510985] | [4236575,4176079,4209824,4183078,4126564,4079252,4426032] | bb9440a2cacbdd65 |
| 1,000,000 | 32 | [35552205,32658486,32702735,33111372,32496191,33046808,32730931] | [33710933,32936225,33589579,34741272,33834445,32669788,32697849] | fa1386df93b6b965 |
| 1,000,000 | 64 | [43028601,40291026,42474700,41925691,40661251,40198277,41628405] | [40732664,40400420,41241341,41377706,41976301,40449606,42302461] | b888ded08329db16 |
| 1,000,000 | 70 | [55061412,54503975,55872573,55231762,55211598,54667793,54739211] | [57230255,54518464,54926931,54847287,54345474,55041261,55452710] | 5840013ba71143f4 |
| 1,000,000 | 96 | [46373380,47501400,46682824,46522860,47344191,46338041,47058092] | [48603519,46506267,48192929,46322404,46961352,46324092,45906354] | e7b4e524ea865a98 |

</details>

## Provenance

- Source commit: c645d1e52a1aadb7a73db5940f1742bfaac16f8a (tree 309fd348555563e5afb40213a64e34b4fbee64d3).
- Main source SHA256: de1b25a83c8aca0d5d63bbea0ec520008b4c4dc968484d9bb756c5206a032505; preload correctness/microbenchmark source SHA256: e11c432ad345ea541ea991c5fdb0e95a95f22a7684ae2bcff63aa77985299c19.
- Quantization correctness selection: 133 passed cases (129 TurboQuant and 4 EncodedVectorsU8); no engine build. Focused test manifest SHA256: 258b04bfab737e86b358c794b0566134eb753a6b66d4db49fd72bfd01870ff6c.
- Test binary SHA256: bc23db9de0a8dc57f26049a155e9cbeff507615b8b4d8cb3e0dccd593f9d95ee; test-build receipt SHA256: d5419edc27641e3503ed19f87e1ca1797c48a08c561a8906356c944f820f5336.
- Micro receipt SHA256: 6b87f193e575f1772ad5864c335d31f695783ae948700445fb3192dd163b383b; driver SHA256: 5d27ca81ca579dcf82732cd6a3fc1e53ab27d6cae3486d4e7ba2ba7fc8bc2a64; stdout SHA256: d38fd19d95a1153a1a6c0c022f5c87228759a46d2eb6da38b4d35cf13a5aa21f; stderr SHA256: e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855.
- The micro receipt, stdout, source/test identity, test-build receipt, test binary, and selected test manifest were cross-checked before this preview was written.

The full machine-readable rows and raw arrays are in [JSON](sq8-amx-preload-20261111.json) and [CSV](sq8-amx-preload-20261111.csv).

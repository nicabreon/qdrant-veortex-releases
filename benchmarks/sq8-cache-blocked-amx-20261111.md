# SQ8 cache-blocked AMX scorer microdiagnostic

**Decision: retain the baseline.** The cache-blocked variant is not a winner in this screen. It is slightly faster only at `nq=16`; it is slower in the other eight measured cells. At `nq=96`, speedup is `0.76×` for 100k vectors and `0.73×` for 1M vectors.

This is a synthetic full-score scorer microbenchmark using generated signed-I8 queries and U8 gallery rows, dimension 512, one guest CPU (CPU 4), and chunk size 1024. Timings are medians of three measured repetitions after one warmup, not tail latency. It provides no HTTP, end-to-end retrieval, recall, or cluster-RPS evidence. No engine binary was built or promoted; the experiment used a quantization test binary.

The candidate and baseline produced matching full-score hashes in all ten cells, and representative scores were checked against an independent integer/F32 oracle. Focused correctness checks passed: 127 `turboquant` cases and 4 `encoded_vectors_u8` cases (131 total) with cache-blocked mode enabled. The separately run microbenchmark test also passed.

| Vectors (`n`) | Queries (`nq`) | Chunk | Repeats | Baseline median (ms) | Cache-blocked median (ms) | Speedup | Score hash |
|---:|---:|---:|---:|---:|---:|---:|:---|
| 100000 | 16 | 1024 | 3 | 3.123 | 3.010 | 1.038× | `33fe14ef44f0342e` |
| 100000 | 32 | 1024 | 3 | 2.717 | 2.743 | 0.991× | `bd51c24b8624247c` |
| 100000 | 64 | 1024 | 3 | 3.618 | 4.117 | 0.879× | `731d7f25c727d89c` |
| 100000 | 70 | 1024 | 3 | 4.758 | 5.264 | 0.904× | `9dd79b53fb2d93b1` |
| 100000 | 96 | 1024 | 3 | 4.350 | 5.743 | 0.757× | `6d1d6b34d9b8ff8b` |
| 1000000 | 16 | 1024 | 3 | 31.555 | 31.303 | 1.008× | `43fdebde15f68de3` |
| 1000000 | 32 | 1024 | 3 | 32.569 | 33.318 | 0.978× | `e624742278387819` |
| 1000000 | 64 | 1024 | 3 | 39.813 | 48.468 | 0.821× | `0d097033645db228` |
| 1000000 | 70 | 1024 | 3 | 54.443 | 61.973 | 0.878× | `0ddf7ab1c4bf8ddc` |
| 1000000 | 96 | 1024 | 3 | 46.443 | 63.294 | 0.734× | `1874fee7adf06ca2` |

Source commit/tree: `94748eee94e77fc13c82f9db02e701bfaa4c1007` / `1df8eca49c041fd21140db9f7db5b9429dcb1578`.

Provenance hashes: micro receipt `6ea0876aef4a58fff47dad4e9371bb82dee9c2e1d710ee6feba7e91b5c8c0e18`, stdout `1231b6a8858c4683e607920a5d5322ff39500ebc985c43135a28056920c979b0`, source test binary `91111c1b412d88653ac83ec0ae22405e0f38608667cb6b11c50d72e19f8347d6`, micro runner `34feab085d6aea86eeb5f6242c3c24699d598e7b1c028ff7a11f16850297718c`, quantization build driver `ba6c120570222c46faae0702bbeb9a0d85e0610baa3de26ddc0741be65bf87d5`, and focused-test build receipt `542dcb5cef55d8fbed32f6b9fdaf8e25125713661f8adf5bcaa7b620e7a38c4a`.

Machine-readable rows and full provenance are in [`diagnostic.json`](sq8-cache-blocked-amx-20261111.json); [`diagnostic.csv`](sq8-cache-blocked-amx-20261111.csv) contains the ten measurements.

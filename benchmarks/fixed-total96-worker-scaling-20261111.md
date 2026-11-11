# Revision — 11 November 2026: the same total 96 queries

**This new test keeps the query count and identities fixed.** One worker scores all 96 queries from query set 0; three workers score disjoint query slices 0–31, 32–63, and 64–95. Every query searches the full 1,000,000-vector SQ8 gallery (512D). Both arms perform 96,000,000 query-vector scores.

| Workers | Queries per worker | Total queries | Median scan ms | Min–max ms | Median scan query/s | Median CPU equivalents |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 96 | 96 | 64.902 | 62.866–76.706 | 1,479.15 | 1.000 |
| 3 | 32 | 96 | 46.555 | 41.576–79.776 | 2,062.10 | 2.945 |

The measured speedup for the same 96-query workload is **1.39×**. Each throughput value is 96 divided by that sample’s full-group elapsed time. The displayed values are medians of seven retained samples per arm; no sample was discarded. The three-worker maximum was 79.776 ms, so these medians do not establish production tail-latency stability.

The earlier result **1,634→4,683 scan query/s** measured **96 queries per worker**, or 96 total for one worker versus 288 total for three workers. It is an aggregate-capacity observation under increased load. It does not measure completion time for a fixed 96-query group, and 4,683 is already the aggregate rate, not a per-worker rate to multiply again. That original experiment and its raw samples remain unchanged in the [earlier report](single-shard-cooperative-scan-20261111.md).

The earlier cooperative-gallery result (58.943 → 22.148 ms) used the same total 96 queries while splitting the gallery across workers. It was measured in a separate earlier run and is not a contemporaneous third arm of this new experiment.

Method: the existing production AMX scorer, one immutable 516 MB strided gallery, signed-I8 queries and unsigned-U8 gallery codes with an F32 affine score. All threads inherit the same CPU 4–6 mask, with no per-thread affinity changes. PF8=6/PFH=9, cached score stores and telemetry disabled are held fixed. Each worker has bounded 96-row scratch capacity; only 32 rows are active per worker in the three-worker arm. The 1/3/3/1 worker schedule provides seven samples per arm, after warmup. Allocation, query packing/AMX setup, thread creation and verification are outside timing. Verification waits until all workers finish timing. The independent oracle and concurrent-output/serial-reference fingerprint checks passed.

Splitting the query batch changes each worker’s batch shape from 96 to 32 and creates three logical gallery traversals. It does not preserve gallery reuse per query. Those facts can affect scaling; actual DRAM traffic and the individual causes of the scaling difference were not isolated.

**Scope:** scan kernel only, in one process on the existing KVM VM (Xeon Silver 4510 guest identity, 16 vCPU, about 47 GiB RAM). This is not 3M cluster HTTP RPS, a B1 latency test, Top10/F32 recall, or a production cooperative-shard feature. The private test-only source was committed and pushed; no production Qdrant binary was replaced.

Source `3e3710a6c3b04f039f18d04d02bc816986be39e7`; Rust 1.98.0 release test binary SHA-256 `a5dfbdc3d835d32f2c6a0f4156cc2f3f94b6fbab079baf188518b96bea72ed49`. Build receipt SHA-256 `f8b30a037a2d72f4765d5d3102a7ae6b74970c94bc30e7294a53e2be216d823f`. The private fixture is not a complete public reproduction package.

[Raw samples and provenance](fixed-total96-worker-scaling-20261111.json) · [CSV](fixed-total96-worker-scaling-20261111.csv)

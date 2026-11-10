# SQ8 runtime tuning — 11 November 2026 (WIB)

Additive probes on the same engine as the [worker-capacity diagnostics](worker-capacity-diagnostics-20261110.md). Existing results remain unchanged. Each row uses full-gallery B1/C512, three million 512D cosine vectors, three one-million-point shards, and three shared CPUs per node. All phases share each node CPU mask, with no per-thread affinity. Metadata exists in both categories. HNSW is disabled.

Ordered Top10 is returned after FP32 reranking of up to 12 candidates per segment. Before every timed cell, 1,024 saved queries are checked against independent saved FP32 truth, followed by 16 HTTP warmups. The same saved queries are reused for timing. Every timed response is validated, with score tolerance 1e-6. Each point is one 30-second dispatch window plus drain; HTTP RPS equals successful completions divided by actual elapsed time. These are short configuration probes, not maximum or long-run stability measurements.

Three workers, a 2 GiB query budget, 640 singleton permits, 640 singleton/shard inflight caps, and a 90 ms admission wait remain fixed. The engine ELF, dataset, query corpus, client and resource masks are unchanged. Each variant changes one runtime setting from fast join 64 / `VX_PFH=9`: either the join threshold becomes 96, or the existing query-tile load hint becomes 13. The variants run separately and are not combined.

| Variant | Category | HTTP RPS | p50 ms | p95 ms | p99 ms | Success / failed |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Fast join 96 | No filter / no payload | 1,942.30 | 261.54 | 375.37 | 406.78 | 58,785 / 0 |
| Fast join 96 | Active filter (~90%) + payload | 1,701.07 | 286.65 | 457.20 | 548.55 | 51,350 / 0 |
| Query tile load hint 13 | No filter / no payload | 1,922.01 | 257.25 | 402.02 | 456.78 | 57,996 / 0 |
| Query tile load hint 13 | Active filter (~90%) + payload | 1,704.45 | 295.74 | 440.77 | 489.08 | 51,500 / 0 |

The earlier fast-join-64 / hint-9 C512 observations were 2,025.96 RPS without filter/payload and 1,695.61 RPS with active filter + payload. Those are cross-run references measured at another time, not simultaneous controls. Host/cache variability and fixed run order prevent attributing small differences to a setting alone. No setting is promoted to a default from these probes, and 5,000 HTTP RPS is not achieved.

All 4 listed rows passed their CPU/activity/ISA, ring-only, F32, zero-error/fallback/HNSW checks. Originals were restored healthy, immutable lower metadata matched, and cleanup passed after each included campaign.

Engine source: `0aa62c281b7262368ca6f1ed69de71647be10ac0`; ELF SHA-256: `074f45b364a8e80da3fb9307d637812072fd755f56b91aeb8bdd4bf92b1ba60d`. Engine source remains private; this candidate differs from the downloadable V45.1 release. [JSON](sq8-runtime-tuning-20261111.json) and [CSV](sq8-runtime-tuning-20261111.csv) contain accepted observations, per-node CPU/reuse summaries and provenance hashes.

# SQ8 CPU profile — 10 November 2026

These are CPU-profile observations on the same private candidate as the [worker/capacity diagnostics](worker-capacity-diagnostics-20261110.md). They are not additional throughput measurements. Profiled RPS and latency are deliberately excluded from the unprofiled benchmark tables.

The workload searches all 3,000,000 512D cosine vectors, with three one-million-point shards, RF=1 and HNSW disabled. Three Docker nodes each have three shared guest CPUs; all scan, TopK/rerank, payload, HTTP and routing threads share their node mask without per-thread affinity. Both cells use SQ8 Auto/AMX, B1/C384, three ring workers, fast join 64, 640 admission/inflight caps and a 90 ms admission wait. Metadata exists in both categories. Each response returns ordered Top10 after FP32 reranking of up to 12 local candidates.

## Method and validation

Before each 30-second dispatch window, all 1,024 saved queries are checked against independent saved FP32 truth, followed by 16 HTTP warmups. Those queries are reused for timing, not held out. Sampling starts at least three seconds after client launch, after both sampled nodes report three active rings and more than 128 admitted queries. Node 0 is the HTTP coordinator; node 1 is a remote shard. Node 2 is not CPU-profiled.

A private, no-network helper records user-mode `cpu-clock:u` leaf IPs for 10 seconds at a requested 199 Hz. No callchains, stack contents or request buffers are captured. The helper uses CPUs outside the server masks. Target libc/libm/libgcc/loader files are copied from the owned benchmark clones and hash-matched across nodes; offline symbolization uses those files and a symlink to the SHA-verified engine ELF. Engine bytes are not duplicated. The host perf sysctls remain unchanged.

Shares below are weighted by each recorded event period in nanoseconds. They describe sampled user-mode work, not exact CPU time, wall-clock latency, kernel time, cache-miss counts or DRAM bandwidth. A sampled instruction address does not identify the cause or duration of a stall.

Both profile cells passed the F32, full CPU-mask, active-worker, AMX, ring-only and zero-fallback/HNSW gates. All 98,219 timed responses matched saved FP32 truth, with zero failed HTTP requests. Original containers were restored healthy, lower dataset metadata matched, and helper/COW cleanup passed.

## Results

| Category | Node | Ring samples | Resolved ring | Ring / process | AMX core / ring | TopK support / process | Async runtime / process |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| No filter / no payload | 0 | 2,909 | 96.32% | 62.36% | 68.99% | 11.43% | 22.08% |
| No filter / no payload | 1 | 3,697 | 96.32% | 78.29% | 71.46% | 13.96% | 0.00% |
| Active filter (~90%) + payload | 0 | 2,583 | 95.90% | 56.39% | 67.67% | 11.77% | 26.65% |
| Active filter (~90%) + payload | 1 | 3,597 | 96.55% | 76.97% | 70.86% | 12.65% | 0.00% |

The main AMX scoring function accounts for about 68–71% of sampled ring work in both categories and nodes. Score conversion, threshold/pruning and score copies, accounting, and ring orchestration account for the remaining ring work. This makes kernel data access and AMX scheduling reasonable optimization targets; it does not prove a memory-bandwidth bottleneck.

TopK/reranking support is already outside the scan ring, on supporting threads sharing the same three CPUs. The coordinator spends a larger sampled share in async runtime threads than the remote node. That group includes HTTP handling, routing/fanout and existing metrics work; this profile does not isolate their individual costs. Payload completion itself is a separate thread group, available in the JSON. None of these shares should be added as milliseconds in a request latency breakdown.

At the unprofiled C512 peak, the observed whole-process cluster cost is approximately 4.22 CPU-ms/query. A 5,000-RPS target under nine shared CPUs permits at most 1.80 CPU-ms/query: roughly a 57% cost reduction. More queue depth or workers alone has not supplied that improvement. No 5,000-RPS result is claimed.

## Scope and provenance

This is one short sample per node/category on one VM. Physical-core isolation, physical cache topology, actual DRAM bandwidth and kernel-mode costs were not established. There is no new native-Qdrant comparison, TQ2/TQ4/AVX-only result, write/failover claim or long-run stability claim here. Engine source and raw profiles remain private; public aggregates and hashes do not make the proprietary implementation independently auditable.

Two earlier profiler attempts are retained privately: the first failed its perf buffer mapping, and the second failed symbol-resolution quality. The final run uses an explicit eight-page buffer, skips helper-side build-ID synthesis and symbolizes against matched target files. These are profiler remediations, not engine changes; rejected profile timings are not used.

Engine source: `0aa62c281b7262368ca6f1ed69de71647be10ac0`. ELF SHA-256: `074f45b364a8e80da3fb9307d637812072fd755f56b91aeb8bdd4bf92b1ba60d`. Campaign receipt SHA-256: `41b52ea52273732e6de17bc5c2b967c810410a75820cb0512511f1ad143fc6ef`. The measured candidate remains distinct from the downloadable V45.1 release. Root curation and sampler hashes, matched library hashes, counts and event-period aggregates are in the [JSON](cpu-profile-20261110.json).

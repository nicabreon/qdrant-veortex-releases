# Stock Qdrant 1.20 benchmark scaffolding

This directory contains public, external benchmark helpers. The affinity shim interposes on `pthread_setname_np`; it does not modify Qdrant source or the supplied Qdrant executable. Recorded historical V45 measurements live in `../benchmarks/`; they are separate from this setup guide.

The official GNU v1.20 binary needs a newer glibc than the host provides. The Compose file uses a pinned Ubuntu 24.04 image (glibc 2.39) and bind-mounts the exact binary supplied by the caller. Set `QDRANT_BINARY_PATH` to that executable in `reproduce/.env`.

Build and self-check the small affinity library:

```sh
./reproduce/build-search-affinity-shim.sh
./reproduce/selftest-search-affinity.sh
```

The self-check exercises `search-cpu-*`, `search-io-*`, and `search-ioall-*` names. With `BENCH_SUPPORT_CPUS` and `BENCH_COMPUTE_CPU` set, the library pins the process main thread to the two support CPUs during library initialization. Search workers are pinned to the compute CPU inside `pthread_setname_np`, before that call returns to the new worker. If both variables are absent, the library leaves affinity unchanged; if only one is set, an id is invalid, or an affinity syscall fails, it exits with status 126.

Each Compose node gets a three-CPU cpuset and a three-CPU quota. Defaults use CPUs `4,5,6`, `7,8,9`, and `10,11,12`; compute defaults are `4`, `7`, and `10`, with the other two CPUs assigned to support work. Change these values in `.env` to match the host. Docker must allow all three CPUs in each node cpuset so the shim can move a named worker from the inherited support mask to its compute CPU.

The pinned Ubuntu runner image omits the system CA bundle, which Qdrant's inference client initializes even when inference is unused. Compose bind-mounts the host CA bundle read-only and sets `SSL_CERT_FILE`; set `HOST_CA_CERT_BUNDLE` in `.env` if the host bundle is stored elsewhere.

Generate fresh, local-only node configurations and mTLS certificates, then start the cluster:

```sh
cp reproduce/native120.env.example reproduce/.env
# Edit QDRANT_BINARY_PATH and CPU ids in reproduce/.env.
./reproduce/build-search-affinity-shim.sh
./reproduce/generate-native120-configs.sh
docker compose --env-file reproduce/.env -f reproduce/docker-compose.native120.yml up -d --wait
```

The config generator creates one shared API key and separate node certificates signed by a new local CA. It does not read or copy credentials from another cluster. Generated configs, private keys, and `configs/generated/api-key.txt` are ignored by Git and should remain local; the key file is mode `0600` and the generator never prints its value. The generated CA private key is deleted after the node certificates are signed. Public HTTP endpoints bind to loopback only; peer gRPC uses TLS with client authentication.

Compose health checks only confirm that each HTTP port accepts TCP connections. Before benchmarking, check that all three Qdrant peers have converged, verify process and thread CPU masks, and record the binary and shim hashes. The Compose file uses separate named storage volumes; it does not load or prepare a dataset.

## Generate and run the B1 stock workload

`workload.py` and `bench.go` provide a separate, portable workload path against
the public Qdrant API. This path does not build Qdrant, change Docker settings,
or call fork-only routes. Run commands from the repository root. Python 3 and
NumPy are required for generation and upload (`python3 -m pip install -r reproduce/requirements.txt`).

The default fixture is one seeded normalized-Gaussian 3,000,000 × 512 FP32
gallery, generated before any category bodies, with deterministic ABIS payloads.
The same gallery and queries can be loaded into separate SQ8, TQ2, and TQ4
collections. It records 3 automatic shards, RF1, and HNSW `m=0` / `payload_m=0`;
the quantization configuration is selected at collection creation. The raw
gallery is 5.72 GiB; deterministic metadata adds about 1.1 GB and the query
file about 2 MiB, so reserve at least 6.8 GiB for the generated files.
Generation checks free filesystem space before writing, but cannot see
per-user/container quotas and excludes Qdrant storage, WAL, and temporary
segment or optimization space. Each retained profile collection needs
additional capacity for raw vectors and quantized segments. The seed and NumPy
version are recorded in `dataset.json` (default seed `20261109`).

```sh
python3 reproduce/workload.py generate --out reproduce-data --seed 20261109
```

To create a fresh empty collection, pass `--create`; it fails if that name
already exists. Without `--create`, the helper requires a matching empty
collection and verifies the vector, shard, replication, HNSW, and selected
quantization settings before upload. `load` refuses to add points to a nonempty
collection; use `prepare-manifests` for an already-loaded compatible
collection. The helper does not delete or convert collections. API-key
authentication is read from `QDRANT_API_KEY` and is never saved to the
repository or results.

```sh
export QDRANT_API_KEY='…' # only when the cluster requires an API key
python3 reproduce/workload.py load \
  --data-dir reproduce-data \
  --endpoint http://127.0.0.1:6333 \
  --collection native120_sq8_3m \
  --profile sq8 \
  --create
```

The default `--peer-endpoints` list matches the three Compose HTTP ports
6333–6335. Before collection creation or upload, the loader verifies all three
endpoints report an enabled cluster, the same three-peer membership, and one
common Raft leader. After load, it also checks all three peer IDs, each active local shard's
owner and positive local point estimate, coverage of the three shards, and
the absence of shard transfers or resharding. Those per-shard counts are
estimates; the collection-level point count is checked separately. Pass a
comma-separated replacement list if host ports differ. The loader creates or
checks exactly three payload indexes before upload: `abis.subject_id` keyword,
`abis.active` bool, and `attributes.position` keyword. Each must cover all
points before preparation succeeds. Every upsert sends the deterministic
payload for every point, including runs whose timed request uses
`with_payload=false`.

The loader sets `optimizers_config.indexing_threshold=0` during bulk upload, so
the global 10,000,000 KB default cannot prevent indexing on this 3M-point
fixture. After upload it enables threshold 1 and one optimizer thread, then
waits for a green collection, `optimizer_status=ok`, exact point and
indexed-vector counts, and all three complete payload indexes. Once quantized
segments are ready, it freezes the recorded final optimizer config, including
`max_optimization_threads=0` (which disables further optimization).
`--readiness-timeout` controls this preparation wait; it is not a latency SLA.
A collection quantization setting alone does not prove its quantized segments
finished building. `prepare-manifests` checks the optimized state again.

The historical candidate caps and matching Top10 oversampling are:

| Profile | Candidate cap per segment | Oversampling |
| --- | ---: | ---: |
| SQ8 | 12 | 1.2 |
| TQ2 | 1767 | 176.7 |
| TQ4 | 40 | 4.0 |

These caps were sufficient on recorded historical conversions, not universal
minimums for a newly generated seed. Accuracy must pass on the selected gallery
before performance claims. `--candidate-count N` sets an explicit cap (N >=
10); every timed body pins `quantization.oversampling=N/10` and records whether
the cap is historical or an override. Keep one collection per profile; these
helpers never convert or delete a collection.

```sh
# Optional additional profile collections; SQ8 was created above.
python3 reproduce/workload.py load --data-dir reproduce-data --endpoint http://127.0.0.1:6333 --collection native120_tq2_3m --profile tq2 --create
python3 reproduce/workload.py load --data-dir reproduce-data --endpoint http://127.0.0.1:6333 --collection native120_tq4_3m --profile tq4 --create
```

Capture native exact-FP32 truth separately from timing, then build manifests
for all four categories: `nf_false`, `nf_true`, `active90_payload` (90% active),
and `narrow9_payload` (about 9%). The no-payload and payload unfiltered modes
share exact Top10 truth. Preparation uses the standard search endpoint with
`exact=true` and `quantization.ignore=true`, verifies each returned payload
against the deterministic ID mapping, and stores truth under
`reproduce-manifests/truth/`; those reference searches are excluded from the
timed reports.

```sh
python3 reproduce/workload.py prepare-manifests \
  --queries reproduce-data/queries.npy \
  --endpoint http://127.0.0.1:6333 \
  --collection native120_sq8_3m \
  --profile sq8 \
  --out reproduce-manifests
```

For TQ2 and TQ4, use their collection and profile, and reuse the SQ8 truth
directory so every profile uses the same exact references. The query hash and
profile cap are pinned in each manifest. Cached truth assumes all collections
hold the same raw gallery and query vectors; cached files alone cannot prove
that provenance.

```sh
python3 reproduce/workload.py prepare-manifests --queries reproduce-data/queries.npy --endpoint http://127.0.0.1:6333 --collection native120_tq2_3m --profile tq2 --cached-truth-dir reproduce-manifests/truth --out reproduce-manifests-tq2
python3 reproduce/workload.py prepare-manifests --queries reproduce-data/queries.npy --endpoint http://127.0.0.1:6333 --collection native120_tq4_3m --profile tq4 --cached-truth-dir reproduce-manifests/truth --out reproduce-manifests-tq4
```

Build the standalone Go client and run its offline preflight. `run` repeats the
same preflight for every category before it sends any benchmark requests.

```sh
go build -o reproduce/bench reproduce/bench.go
for manifest in reproduce-manifests/{nf_false,nf_true,active90_payload,narrow9_payload}.json; do
  reproduce/bench --manifest "$manifest" --validate-manifest-only
done
```

Before timing, check every one of the 1,024 approximate requests per category
against exact-FP32 truth on the live collection. This untimed quality check
blocks performance claims for a profile if a query fails; historical caps do
not guarantee accuracy on a fresh gallery.

```sh
python3 reproduce/verify-accuracy.py \
  --manifest-dir reproduce-manifests \
  --out reproduce-quality/accuracy.json
```

The default run measures all four categories at C1 and C160 for 60 seconds
each, with max-inflight matched to concurrency and `GOMAXPROCS=7`. Each pass
uses 16 successful full-response warm-up requests before its measured dispatch
window; the warm-up is recorded in that Go report and excluded from the timer.
Each measured request is checked for ordered IDs/scores and its payload contract.

```sh
taskset -c 0,1,2,3,13,14,15 python3 reproduce/workload.py run \
  --manifest-dir reproduce-manifests \
  --bench reproduce/bench \
  --out reproduce-results
```

The runner saves the individual Go reports and `summary.json`, including actual
dispatch and drain durations, elapsed time, completion-based RPS, p50/p95/p99
full-response validated latency, warm-up counts, and client, HTTP, transport,
candidate-truth, payload, and metadata-hash validation counters. RPS divides
successful completed responses by elapsed time through final response
validation, including drain. Failed requests remain in the reports and
summary. Each summary row records `passed` and `status`; a failed request,
capacity rejection, unsuccessful warm-up, candidate-truth mismatch, or payload
contract mismatch marks that row `COMPLETED_WITH_FAILURES`. The command exits
nonzero after writing every scheduled row. For a short smoke run, use
`--concurrency 1 --seconds 10`; the warm-up count can be changed with
`--warmup-requests 16` or disabled with `--warmup-requests 0`.

### Existing data and historical query inputs

To use an already-loaded compatible collection or snapshot, skip `generate`
and `load` and point `prepare-manifests` at it. The query input can be a `.npy`
matrix, JSON/JSONL vectors, or a cached manifest from this Go client; cached
manifests are read only to recover their 1,024 query vectors. For example:

```sh
python3 reproduce/workload.py prepare-manifests \
  --queries /path/to/historical-query-manifest.json \
  --endpoint http://127.0.0.1:6333 \
  --collection existing_sq8_collection \
  --out reproduce-manifests
```

`--cached-truth-dir` can reuse category JSONL exact results instead of making
the preparation searches. It accepts `<category>.jsonl` (one Top10 array per
line) and the historical `*-independent-f32.jsonl.gz` captures; historical
32-hit rows are reduced to their first 10. Cached truth must match the same
gallery and query vectors. The Go preflight verifies structure and metadata
digests; only the timed pass establishes whether the live collection returns
the same candidates and scores.

The historical fixture seed is unknown. A fresh generated gallery makes the
protocol repeatable, but it does not claim identical vectors, Top10, recall,
accuracy, or performance numbers to an old run. Use the original snapshot and
query vectors for direct historical comparisons. The Go validator expects
payload values from the deterministic ID mapping in `bench.go`.

Native truth uses the same stock Qdrant collection and binary as the timed
search, with `exact=true` and `quantization.ignore=true`; it checks SQ8 results
against exact search over the retained FP32 vectors. This is a separate,
untimed reference pass, not an independent engine or external oracle. The
`--cached-truth-dir` option cannot establish that supplied truth belongs to the
gallery and query vectors; that correspondence must come from snapshot and
query provenance. Historical 32-hit captures are truncated to their first 10
entries to match the B1 Top10 contract. The narrow filter selects 269,999 of
3,000,000 generated points (about 9%); the active filter selects 2,700,000
(90%).

The loader creates automatic three-shard collections. It does not recreate the
historical custom-shard layout with one 1M-point key per node; use the original
snapshot for that placement or prepare an independently provisioned matching
collection. The generated automatic-shard corpus supports protocol and
workload comparisons, but does not claim byte-for-byte historical placement.

## Record CPU and binary identity during load

Run the affinity capture while requests are active, not before the first query.
It records each runtime ELF hash, Docker CPU quota/cpuset, worker affinity, and
cumulative CPU ticks. Docker access and Linux `/proc` visibility are required.
For different CPU mappings, pass `--compute-cpus` and `--support-cpus`.

```sh
python3 reproduce/capture-runtime.py \
  --compose reproduce/docker-compose.native120.yml \
  --env-file reproduce/.env --variant native \
  --out reproduce-results/runtime-during-load.json
```

For V45, use `--variant veortex` and add a second `--compose` argument for
`reproduce/docker-compose.veortex-v45.override.yml`. This capture checks named
workers; it cannot by itself prove fast-path routing for every request.

The historical cluster used custom sharding with three keys (`node_0`,
`node_1`, `node_2`), one physical shard and exactly 1M points per node. Its
collection-level `shard_number=1` is a per-key count. The fresh generator's
default automatic three-shard collection can have slightly different physical
placement; inspect `/collections/<name>/cluster` on every node and record it.

Do not run stock and Veortex simultaneously on the same cpusets. Warm each
engine separately on the same gallery, queries, filters and candidate settings.
The stock shim pins the entire upstream search closure, including TopK/F32
rerank, to its one search CPU; V45 places scan on one CPU and its TopK/F32
support pipeline on the other two. Both have the same total three-CPU quota,
but stage allocation and official/compiler build provenance differ.

## Match the recorded C160 sweep

The published VM has 16 logical CPUs. Its Go client was restricted to
`0,1,2,3,13,14,15`, disjoint from the engine containers on `4..12`, with
`GOMAXPROCS=7`. The command above inherits that client affinity. Remap both
client and engine CPU lists for another host; do not let the load generator
compete with the measured scan CPUs. Tested helper tools: Python 3.10.12,
NumPy 2.2.6 (`requirements.txt`), and Go 1.25.1.

The historical V45 table contains four C160 category rows and an unfiltered
repeat. Select `--concurrency 160` for that sweep, then run its final control row
using the same manifest, client CPUs, warmup and timer:

```sh
taskset -c 0,1,2,3,13,14,15 python3 reproduce/workload.py run \
  --manifest-dir reproduce-manifests --bench reproduce/bench \
  --concurrency 160 --out reproduce-results-c160
taskset -c 0,1,2,3,13,14,15 reproduce/bench \
  --manifest reproduce-manifests/nf_false.json \
  --mode closed-loop --concurrency 160 --max-inflight 160 \
  --seconds 60 --gomaxprocs 7 --warmup-requests 16 --timeout 30s \
  --score-tolerance 0.000001 --output reproduce-results-c160/nf-repeat.json
```

For the native1.20 measurement order, first run a separate `--concurrency 1`
sweep, then the C160 sweep and repeat. The generic default `1,160` alternates
those two concurrency levels within each category. Run each quantization
profile sequentially using its own manifests and saved exact truth. Keeping
three 3M collections simultaneously requires substantially more disk than one
profile; save results before manually retiring any disposable collection. No
helper deletes a collection or volume automatically.

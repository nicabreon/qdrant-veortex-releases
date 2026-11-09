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

## Generate and run the B1 SQ8 workload

`workload.py` and `bench.go` provide a separate, portable workload path against
the public Qdrant API. This path does not build Qdrant, change Docker settings,
or call fork-only routes. Run commands from the repository root. Python 3 and
NumPy are required for generation and upload (`python3 -m pip install numpy`).

The default fixture is one seeded normalized-Gaussian 3,000,000 × 512 FP32
gallery, generated before any category bodies, with deterministic ABIS payloads.
It records 3 shards, RF1, HNSW `m=0` / `payload_m=0`, and scalar SQ8 (`int8`,
quantile 1, always in RAM). The raw gallery is 5.72 GiB; deterministic metadata
adds about 1.1 GB and the query file about 2 MiB, so reserve at least 6.8 GiB
for the generated files. Generation checks currently free filesystem space
before writing. That check cannot see per-user or container quotas and excludes
Qdrant storage, WAL, and temporary segment or optimization space; reserve
additional capacity for those. The seed and NumPy version are recorded in
`dataset.json` (default seed `20261109`).

```sh
python3 reproduce/workload.py generate --out reproduce-data --seed 20261109
```

To create a fresh collection, pass `--create`; it fails if that collection
already exists. Without `--create`, the helper requires an existing collection
and verifies the vector, shard, replication, HNSW, and scalar-quantization
settings before upload. API-key authentication is read from the environment
variable `QDRANT_API_KEY` and is never saved to the repository or results.

```sh
export QDRANT_API_KEY='…' # only when the cluster requires an API key
python3 reproduce/workload.py load \
  --data-dir reproduce-data \
  --endpoint http://127.0.0.1:6333 \
  --collection native120_sq8_3m \
  --create
```

The default `--peer-endpoints` list matches the three Compose HTTP ports
6333–6335. The loader verifies all three peer IDs, each active local shard's
owner and positive local point estimate, coverage of the three shards, and
the absence of shard transfers or resharding. Those per-shard counts are
estimates; the collection-level point count is checked separately. Pass a
comma-separated replacement list if host ports differ. The loader also
requires a green collection with exactly the requested point count and an
empty payload-index schema. Every upsert sends the deterministic payload for
every point, including runs whose timed request uses `with_payload=false`.

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
  --out reproduce-manifests
```

Build the standalone Go client and run its offline preflight. `run` repeats the
same preflight for every category before it sends any benchmark requests.

```sh
go build -o reproduce/bench reproduce/bench.go
for manifest in reproduce-manifests/{nf_false,nf_true,active90_payload,narrow9_payload}.json; do
  reproduce/bench --manifest "$manifest" --validate-manifest-only
done
```

The default run measures all four categories at C1 and C160 for 60 seconds
each, with max-inflight matched to concurrency and `GOMAXPROCS=7`. Each pass
uses 16 successful full-response warm-up requests before its measured dispatch
window; the warm-up is recorded in that Go report and excluded from the timer.
Each measured request is checked for ordered IDs/scores and its payload contract.

```sh
python3 reproduce/workload.py run \
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
summary. For a short smoke run, use
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

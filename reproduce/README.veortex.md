# Frozen Veortex V45 benchmark setup

This is a separate Compose overlay for the frozen Veortex V45 executable. It reuses the three-node Ubuntu 24.04 cluster, TLS/mTLS configuration mounts, three-CPU cpusets and quota from `docker-compose.native120.yml`, while replacing the native-only shim mount and environment. The overlay sets `LD_PRELOAD` to an empty value and does not mount the external affinity shim. Veortex handles its own CPU allocation through its runtime variables.

The S8 receipt pins the executable to SHA-256 `9a44f09da70af7921da7b2a6893b98c1ea3d9dcab61986d3504b63f4e3dfa0e8` and source commit `bc0eec0015771e8c59134b1b83a740418efcff7e`. Download and extract the public GitHub Release asset for tag `v1.20.0-veortex.v45.20261109`, then set `QDRANT_BINARY_PATH` in the safe environment example to the extracted `bin/qdrant`. Verify the digest before use. No API key or private credential is stored in the example.

The node allocations are:

| Node | Three-CPU cpuset | Veortex scan compute CPU | Support CPUs |
|---|---|---:|---|
| node0 | `4,5,6` | `4` | `5,6` |
| node1 | `7,8,9` | `7` | `8,9` |
| node2 | `10,11,12` | `10` | `11,12` |

This keeps the S8 allocation of one scan compute CPU and two support CPUs for TopK/rerank work. `MAX_RING_WORKERS=1`, `MAX_SEARCH_THREADS=1`, and `RAYON_NUM_THREADS=2` are pinned to the receipt values. The other Veortex and `VX_*` flags in the overlay also match the receipt. Four V45 TQ feature controls were `UNSET_BINARY_DEFAULT` in that receipt, so this setup leaves them unset. These are reproduction settings only; this file makes no new performance claim.

The runner image omits system CA roots required during Qdrant startup. Compose mounts the host CA bundle at `/etc/ssl/certs/ca-certificates.crt` and sets `SSL_CERT_FILE`; change `HOST_CA_CERT_BUNDLE` if the host uses another path.

Prepare the local config and safe env file, then inspect the merged Compose model:

```sh
cp reproduce/veortex-v45.env.example reproduce/.env
# Download/extract release tag v1.20.0-veortex.v45.20261109 and set
# QDRANT_BINARY_PATH in .env to the extracted bin/qdrant.
sha256sum "$(sed -n 's/^QDRANT_BINARY_PATH=//p' reproduce/.env)"
./reproduce/generate-native120-configs.sh
docker compose --env-file reproduce/.env \
  -f reproduce/docker-compose.native120.yml \
  -f reproduce/docker-compose.veortex-v45.override.yml config --quiet
```

The config generator creates fresh local API and TLS credentials under `configs/generated`; keep those files private. The overlay shares the native compose file's default host ports, so stop any existing benchmark cluster before starting this one. Compose `!override` tags remove the native shim and replace the environment and bind mounts; use Docker Compose v2.24.4 or newer.

Start only after verifying the binary digest and reviewing the rendered configuration:

```sh
docker compose --env-file reproduce/.env \
  -f reproduce/docker-compose.native120.yml \
  -f reproduce/docker-compose.veortex-v45.override.yml up -d --wait
```

While synthetic requests are active, optionally capture the configured cpusets and live thread masks/ticks:

```sh
python3 reproduce/capture-runtime.py \
  --compose reproduce/docker-compose.native120.yml \
  --compose reproduce/docker-compose.veortex-v45.override.yml \
  --env-file reproduce/.env \
  --variant veortex \
  --compute-cpus 4,7,10 \
  --support-cpus '5,6;8,9;11,12' \
  --out reproduce/validation/veortex-runtime-capture.json
```

This is an instantaneous CPU-affinity and cumulative thread-tick capture. It does not prove scorer routing or physical host CPU isolation.

## V45.1 admission-budget follow-up

To reproduce the bounded-admission remediation, use release tag
`v1.20.0-veortex.v45.1.20261109`, executable SHA-256
`90d54aeabbaa17350b94161f6a7926528b13452b0b50296f0bc45fc0e96969e0`.
Keep the original V45 overlay unchanged for the primary 80-row campaign.
The new overlay changes only the runtime byte budget to 640 MiB and identifies
this separately built binary, whose configurable ceiling is 2 GiB. Default
admission wait and request timeouts are unchanged.

```sh
cp reproduce/admission-budget.env.example reproduce/.env
# Set QDRANT_BINARY_PATH to the extracted V45.1 bin/qdrant; remap CPU IDs if needed.
./reproduce/generate-native120-configs.sh
docker compose --env-file reproduce/.env \
  -f reproduce/docker-compose.native120.yml \
  -f reproduce/docker-compose.admission-budget.override.yml config --quiet
docker compose --env-file reproduce/.env \
  -f reproduce/docker-compose.native120.yml \
  -f reproduce/docker-compose.admission-budget.override.yml up -d --wait
```

Use the dataset, metadata, exact truth, and manifest preparation described in
[README.md](README.md). After the collection and its payload indexes are ready,
run the same common client and four B64/C4 cases:

```sh
python3 reproduce/run-batch-matrix.py \
  --engine-label veortex-v45.1 \
  --manifest-dir reproduce-manifests \
  --client reproduce/bench-matrix \
  --batch-sizes 64 \
  --seconds 60 --warmup-requests 16 --timeout 60s \
  --gomaxprocs 7 --client-cpus 0,1,2,3,13,14,15 \
  --output admission-budget-results
```

The runner reads the API key from `QDRANT_API_KEY` in the local environment;
it is not a CLI argument. Capture runtime CPU evidence separately while requests
are active, following the command above with the new overlay. The public
`capture-runtime.py` is a snapshot collector; the published campaign retains
its separate interval CPU observations in the result JSON.
Generated fixtures use the documented reproduction seed and will not recreate
the older unknown-seed gallery byte-for-byte. Validate the new fixture against
FP32; do not assume the old rankings, candidate cap recall, or measured speed.
See the [recorded four-category results](../benchmarks/h2h-sq8-admission-remediation-20261109.md).

## SQ8 AVX-512-only comparison

The [recorded backend comparison](../benchmarks/sq8-avx512-vs-amx-20261110.md)
uses V45.1 with the same 640 MiB admission profile in both arms. The ring and
the one-compute/two-support CPU placement stay enabled. Append the
[kernel-selection overlay](docker-compose.avx512-only.override.yml) after
the two files above:

```sh
export QDRANT_VEORTEX_KERNEL_TIER=avx512vnni
docker compose --env-file reproduce/.env \
  -f reproduce/docker-compose.native120.yml \
  -f reproduce/docker-compose.admission-budget.override.yml \
  -f reproduce/docker-compose.avx512-only.override.yml up -d --wait
```

The tier is read at process startup; changing a client environment variable
alone does not change an already-running server. The overlay merges the kernel
selection into every node's existing environment. It does not remove the ring,
queue, CPU, TLS, or support-worker settings. On a host without AVX-512 VNNI,
the implementation falls back to a supported lower tier, so check the counters
instead of treating the requested tier as proof of execution.

After preparing and validating the four manifests using the preceding fixture
instructions, measure only B1/C128 with the common Go client. The following
uses the short manifest names generated by `workload.py`:

```sh
mkdir -p avx512-results
for category in nf_false nf_true active90_payload narrow9_payload; do
  taskset -c 0,1,2,3,13,14,15 reproduce/bench-matrix \
    --manifest "reproduce-manifests/${category}.json" \
    --batch-size 1 --concurrency 128 --max-inflight 128 \
    --seconds 60 --warmup-requests 16 --timeout 60s --gomaxprocs 7 \
    --score-tolerance 0.000001 \
    --output "avx512-results/${category}.json"
done
```

`QDRANT_API_KEY` must already be set privately for the client. Compare each
node's `/metrics` immediately before and after each row: require positive
`veortex_kernel_calls_total{tier="avx512vnni"}` deltas and zero
`veortex_kernel_calls_total{tier="amx"}` deltas, plus active ring work and no
fallback. Retain CPU-affinity observations while the workload is active.

For the paired control, set `QDRANT_VEORTEX_KERNEL_TIER=auto`, apply the same
three-file Compose command, wait for readiness, and repeat the client commands
into a separate `auto-results` directory. Do not run both arms simultaneously.
Require positive AMX deltas on every node for the control. All other settings,
the binary, fixture, metadata, filters, candidate cap, and reference truth must
stay the same. No engine rebuild is needed. This compares backend paths:
their tiling and score epilogues also differ, so it is not an isolated
instruction-throughput experiment. A regenerated fixture still needs its own
FP32 correctness validation.

## Revision note — 10 November 2026 (WIB): shared three-CPU profile

This is a separate experiment from the retained one-compute/two-support profiles
above. Each node keeps its disjoint three-CPU Docker cpuset and quota, while all
search and service threads share those CPUs. Native has `max_search_threads=3`
and no active preload shim. Veortex has three unpinned ring slots,
`SEPARATE_TOPK=0`, and no `COMPUTE_CPUS` or `SUPPORT_CPUS` environment keys.
Both use `RAYON_NUM_THREADS=3`. Three ring slots permit concurrency; they do not
guarantee that every workload activates three workers or saturates all CPUs.

For native, append `docker-compose.native-shared3.override.yml` to the native
base. For Veortex, append `docker-compose.veortex-shared3.override.yml` after
the native base and admission-budget override. The latter requires V45.1 and
uses a 2 GiB retained-query reservation cap to accommodate B128/C4. This is a
cap, not an eager 2 GiB allocation. Choose `avx512vnni` or `auto` before startup.
The environment is replaced so the old CPU-map keys are removed entirely;
empty values would be invalid.

```sh
# Native: set QDRANT_BINARY_PATH in the local env file to the official binary.
docker compose --env-file reproduce/.env \
  -f reproduce/docker-compose.native120.yml \
  -f reproduce/docker-compose.native-shared3.override.yml up -d --wait

# Veortex: stop native first and point QDRANT_BINARY_PATH at V45.1.
export QDRANT_VEORTEX_KERNEL_TIER=avx512vnni
docker compose --env-file reproduce/.env \
  -f reproduce/docker-compose.native120.yml \
  -f reproduce/docker-compose.admission-budget.override.yml \
  -f reproduce/docker-compose.veortex-shared3.override.yml up -d --wait
```

Keep fixture, metadata, indexes, query manifests, Top10 truth, and the three-CPU
budget identical. Run B1 with C64/C128, then B64/C4 and B128/C4 with the common
Go client. Its added B128 option changes only the benchmark client; neither
engine needs rebuilding. Use a new output directory for each engine/tier and
cell, 16 validated warmup requests, 60 seconds of dispatch, and a 60-second
request timeout. Report successful HTTP requests/s and query/s separately;
every query in a batch still returns Top10.

Capture full per-thread CPU masks, positive runtime, whole-process CPU usage,
and per-node kernel counters while the load runs. There must be no mask narrowed
to a reserved compute/support CPU. Native's available SIMD paths do not prove
the ISA selected on each request. This shared-budget comparison addresses the
old CPU-allocation difference; it still compares full systems with different
compiler builds rather than isolating a kernel instruction's speed.

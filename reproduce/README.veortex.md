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

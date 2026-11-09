# Manual deployment

This guide installs the frozen Qdrant 1.20.0–Veortex V45 research executable on Linux x86_64. It describes a single-node launch; configure clustering separately using the Qdrant 1.20 documentation. The archive is distributed from the [V45 GitHub Release](https://github.com/nicabreon/qdrant-veortex-releases/releases/tag/v1.20.0-veortex.v45.20261109) and contains `bin/qdrant` plus release notices.

## Check the host and artifact

The ELF requires x86_64 GNU/Linux and glibc 2.34 or later. Its recorded dynamic dependencies are `libgcc_s.so.1`, `libm.so.6`, `libc.so.6`, and the GNU dynamic loader. Confirm the architecture and glibc version before installing:

```sh
uname -m
getconf GNU_LIBC_VERSION
```

Download the `.tar.gz` asset from the release page, then extract it under `/opt/qdrant-veortex`. Substitute the actual downloaded asset path below:

```sh
RELEASE_ARCHIVE=/path/to/downloaded-v45-release.tar.gz
sudo install -d -m 0755 /opt/qdrant-veortex
sudo tar -xzf "$RELEASE_ARCHIVE" -C /opt/qdrant-veortex
sha256sum /opt/qdrant-veortex/bin/qdrant
/opt/qdrant-veortex/bin/qdrant --version
```

The executable SHA-256 must be `9a44f09da70af7921da7b2a6893b98c1ea3d9dcab61986d3504b63f4e3dfa0e8`; the version output should identify Qdrant 1.20.0. The release manifest records the source commit, source tree, build ID, and binary digest. Do not launch the executable unless the digest matches.

The runtime also needs a readable operating-system CA trust store. Install the distribution's `ca-certificates` package on a host. Minimal container images may not include it; mount a CA bundle into the container and point `SSL_CERT_FILE` at that bundle. These system trust roots are separate from the Qdrant API and peer TLS certificates configured for the deployment.

Some optimized kernels use AVX-512 VNNI and AMX INT8 when those features are exposed and enabled by the host operating system. An x86_64 architecture and compatible glibc do not guarantee that an optimized path is available. Check the host and VM CPU feature exposure, then run a smoke test on disposable data before migrating a collection. The tested VM's feature set and the limits of the published measurements are recorded in [the benchmark report](benchmarks/historical-v45-20261102.md).

## Configure and start

Run Qdrant as a dedicated unprivileged service account. Keep its configuration, persistent storage, snapshots, credentials, and logs in administrator-controlled paths. Use separate persistent storage and snapshot locations for each node; do not share a Qdrant storage directory between processes. Create a site-specific configuration from the [Qdrant configuration reference](https://qdrant.tech/documentation/operations/configuration/), set persistent paths, and bind the API to loopback or a private interface.

Start it with the custom configuration path:

```sh
/opt/qdrant-veortex/bin/qdrant --config-path /etc/qdrant-veortex/config.yaml
```

Self-hosted Qdrant is open to reachable clients by default. Before exposing an API endpoint, configure an API key and TLS either in Qdrant or at a trusted TLS-terminating proxy, restrict network access, and store secrets outside this repository and shell history. Use read-only credentials for clients that only query. In a cluster, configure the same administrative API key on every peer, enable peer-to-peer TLS, and firewall the internal gRPC port (6335) so only cluster members can reach it. Keep the peer certificates' names and addresses aligned with each node's peer URI, and use a managed certificate authority with a renewal and rotation process.

Before upgrades or experiments with another build, create snapshots and test restoration on a separate copy. In distributed mode, create a collection snapshot on each node because each node's snapshot contains only its local shard data. Keep this research binary and the Qdrant 1.20.0 data format together until an upgrade path has been tested against copies of the data.

Qdrant's current self-hosted security guidance, configuration reference, snapshot instructions, and upgrade guidance are linked here:

- [Security and access control](https://qdrant.tech/documentation/security/)
- [Configuration](https://qdrant.tech/documentation/operations/configuration/)
- [Snapshots](https://qdrant.tech/documentation/operations/snapshots/)
- [Upgrades](https://qdrant.tech/documentation/operations/upgrades/)

The benchmark Compose configuration in this repository is a local lab fixture. Its generated API key, CA, and node certificates are disposable and are not production credentials or certificate-management guidance.

## V45 reference CPU profile

The published S8 measurements used three nodes with three vCPUs available to each container: one designated scan/score compute CPU and two support CPUs for TopK/rerank and service work. The logical CPU IDs below describe that test VM only. Remap them to CPUs available to the target host and keep each compute CPU inside its node's cpuset.

| Node | Three-vCPU cpuset | `QDRANT_VEORTEX_COMPUTE_CPUS` | `QDRANT_VEORTEX_SUPPORT_CPUS` |
|---|---|---:|---|
| node0 | `4,5,6` | `4` | `5,6` |
| node1 | `7,8,9` | `7` | `8,9` |
| node2 | `10,11,12` | `10` | `11,12` |

The frozen receipt also set `QDRANT__STORAGE__PERFORMANCE__MAX_SEARCH_THREADS=1`, `QDRANT_VEORTEX_MAX_RING_WORKERS=1`, and `RAYON_NUM_THREADS=2`. Singleton admission was configured for 160 permits with a 90 ms maximum admission wait. Separately, `QDRANT_VEORTEX_COALESCE_WINDOW_US=1000` sets a 1 ms coalescing window; it is not the admission wait or a worker count. These values describe the measured profile, not recommended defaults for other workloads.

The receipt used `VX_PFH=9`, a bitmask of bits 8 and 1. Bit 8 selects the tested AMX 2×2 schedule (two gallery tiles by two query tiles) only when `n_tiles` is even and `active_q_tiles` is at least four and even; otherwise the kernel uses its active-group path. Bit 1 selects the T1 software-prefetch hint. Hardware tiles remain 16-vector groups, so `9` does not mean a 9×9 tile. `VX_PF8` is a separate setting and must not be inferred from `VX_PFH`.

The S8 receipt reports its stated SQ8 target met and records observed one-compute-CPU affinity for the measured rows on that VM. This is evidence for that run and its configured host, not a guarantee for another kernel, hypervisor, container runtime, or CPU layout. The published C160 results are finite closed-loop measurements; they do not establish maximum throughput, single-request latency, or long-duration stability. The benchmark report describes the workload, the limited interpretation, and the results for other tested modes.

For a reproducible local cluster configuration, follow [the frozen V45 environment profile](reproduce/README.veortex.md) and [its safe environment example](reproduce/veortex-v45.env.example). Those files pin the receipt settings and binary hash; they do not replace the operational security and backup steps above.

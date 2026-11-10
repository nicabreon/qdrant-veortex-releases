# Capacity benchmark client (separate revision)

This copy extends only the original client's concurrency/in-flight ceiling from 160 to 1,024 and updates two help strings. HTTP behavior, query bodies, result validation, timeout handling and throughput calculations are unchanged. The original [client](../bench-matrix/main.go) remains frozen for historical results. This helper is not engine source.

The measured build used Go 1.25.1 from the public repository root with `go env GOMOD` reporting `/dev/null` and `GO111MODULE`/`GOWORK` unset. Its `go version -m` settings matched the original client, including no `DefaultGODEBUG` override. An inherited parent module or forcing `GO111MODULE=off` produced different compatibility settings in diagnostic builds; those builds were not used for the cluster results. Build/cache/tmp paths were on persistent disk.

From the repository root, using existing directories on persistent disk:

```sh
GOCACHE=/persistent/go-cache GOTMPDIR=/persistent/go-tmp \
  go build -o ./bench-matrix-capacity ./reproduce/cmd/bench-matrix-capacity/main.go
```

Inspect `go version -m ./bench-matrix-capacity` when comparing builds. Source SHA-256 is `16c957e8539df6c91e01b993e97314d464615845b9be7715bfb2a300f9c48126`; the measured executable SHA-256 is `3ac5765e0116dd6d4776996bc0e717bb2abecdd1950302b63aa4d00e1400436f`. Local rebuilds are not promised to be byte-identical. The [validation record](validation.json) covers all 21 existing mock cases plus nine capacity/boundary probes.

Example for an existing validated manifest (set `QDRANT_API_KEY` in your shell):

```sh
taskset -c 0,1,2,3,13,14,15 ./bench-matrix-capacity \
  --manifest /path/to/manifest.json --batch-size 1 \
  --concurrency 512 --max-inflight 512 --gomaxprocs 7 \
  --warmup-requests 16 --seconds 30 --timeout 60s \
  --score-tolerance 0.000001 --output result.json
```

The CPU mask above is the client mask on the tested 16-vCPU VM; the three server masks were `4,5,6`, `7,8,9`, `10,11,12`. It is not engine thread affinity. Concurrency accepts 1..1,024; `--max-inflight=0` defaults to concurrency, otherwise it must be at least concurrency and at most 1,024. Higher values do not increase engine capacity by themselves.

See the [diagnostic report](../../../benchmarks/worker-capacity-diagnostics-20261110.md) for the three-node engine profile, actual completed-request rates, p95/p99 and scope. The measured engine ELF differs from downloadable V45.1, and the historical fixture seed is unknown. This client alone does not reproduce that engine or reconstruct the exact historical dataset.

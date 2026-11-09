# Shared batched-search client

`bench-matrix` is the common closed-loop HTTP client for comparing stock Qdrant with the frozen Veortex executable at batch sizes B1, B4, B16, B32, and B64. It reads a frozen B1 manifest, reuses its query bodies and Top10 exact FP32 truth, and validates every returned query before counting an HTTP request as successful. It is a per-row client; the campaign runner owns engine startup, lifecycle, and matrix scheduling.

Build the client once and keep that executable for every engine, category, and matrix cell:

```sh
GO111MODULE=off go build -o reproduce/bench-matrix reproduce/cmd/bench-matrix/main.go
sha256sum reproduce/cmd/bench-matrix reproduce/cmd/bench-matrix/main.go
```

First validate each manifest offline. This checks its 1,024 request bodies, filters, candidate truth, deterministic metadata digest, query count, Top10 limit, and payload mode without reading `QDRANT_API_KEY` or sending requests:

```sh
reproduce/bench-matrix --manifest "$MANIFEST" --validate-manifest-only
```

Run one row with the same client for either engine:

```sh
export QDRANT_API_KEY='…'
reproduce/bench-matrix \
  --manifest "$MANIFEST" \
  --output "$ROW_OUTPUT" \
  --mode closed-loop \
  --concurrency "$C" \
  --max-inflight "$C" \
  --batch-size "$B" \
  --seconds 60 \
  --gomaxprocs 7 \
  --warmup-requests 16 \
  --timeout 60s \
  --score-tolerance 0.000001
```

The manifest endpoint supplies the collection and consistency query. B1 posts the original request to `/points/search`; larger batches post the same original bodies, in contiguous cyclic query order, as `{"searches":[...]}` to `/points/search/batch`, preserving `consistency=quorum`. Each row starts its timer after warm-up, stops dispatch at the configured duration, and drains in-flight requests. `actual_elapsed_s` includes drain. `successful_http_rps` counts only fully validated HTTP requests; `query_qps` counts B vectors only for those successful requests. Full-response latency includes body reading and client validation. The report also includes server JSON time, connection-acquire time, warm-up and timed counts, HTTP/protocol/failure counts, manifest hash, and client executable hash.

`passed` is true only when every configured warm-up request and every dispatched timed request passes, all requested queries have exact ordered Top10 ID and score matches within tolerance, and every requested payload contract passes. A failed warm-up aborts before timed dispatch and writes a `WARMUP_FAILED` report. Timed failures remain in the row, produce `COMPLETED_WITH_FAILURES`, and return a nonzero exit code. Do not discard or silently rerun failed rows.

Payload requests validate every required deterministic ABIS and attributes field against the returned numeric ID, including required `false` values. No-payload requests require the payload field to be omitted. An explicit `null` is treated as a present payload and fails that contract. These checks verify the response against the frozen synthetic metadata recipe and query truth; they do not replace a separate live accuracy preflight of all 1,024 queries per category.

The client uses HTTP/1.1 persistent connections, disables compression and proxy discovery, keeps normal TLS certificate verification, caps response bodies at 8 MiB, and reads an API key only from `QDRANT_API_KEY`. It never writes the credential to its report. `--help` lists the accepted flags and limits.

The checked-in `validation-receipt.json` records offline fake-server coverage for all five batch sizes, payload omission, injected correctness failures, 429s, warm-up abort, drain arithmetic, and report metrics. Those tests exercise client behavior only; they are not cluster results or performance measurements.

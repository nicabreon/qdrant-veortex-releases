# SQ8 B64/C4 admission remediation

Status: build and focused Rust tests are pending. No candidate throughput is published yet.

The candidate expands the configurable queue-byte ceiling to 2 GiB, preserves the 384 MiB default, and tests an explicit 640 MiB limit with the same 3M × 512D collection, Top10 per query and a 1,024-query corpus. Three nodes have three CPUs each, including one compute CPU per node. Request timeouts remain 60 seconds.

See the [confirmed HTTP 429 diagnosis](ADMISSION_REMEDIATION.md) and the [unchanged primary 80-row report](h2h-sq8-batch-20261109.md).

# Qdrant–Veortex V45 research binary

This is a binary-only research distribution of a Qdrant 1.20.0 build containing the Veortex search engine. It does not include the Qdrant or Veortex engine source. The runtime executable is distributed as a separate release archive; download it from the [V45 release page](https://github.com/nicabreon/qdrant-veortex-releases/releases/tag/v1.20.0-veortex.v45.20261109).

The release artifact is identified by its provenance and hash:

- Qdrant source commit: `bc0eec0015771e8c59134b1b83a740418efcff7e`
- Source tree: `f3335fe4f9474c3bbc5274785c4bde930fc272be`
- ELF SHA-256: `9a44f09da70af7921da7b2a6893b98c1ea3d9dcab61986d3504b63f4e3dfa0e8`
- Target: x86_64 GNU/Linux; glibc 2.34 or later

Verify the downloaded file against the SHA-256 before running it. Follow [manual deployment](DEPLOYMENT.md) for host requirements, configuration, and operational guidance.

The V45 S8 SQ8 run met its stated target and recorded one-compute-CPU affinity during its measured rows on the tested VM. The published results use a finite workload and a reused query corpus; they are empirical coverage, not a universal recall guarantee. The TQ2/TQ4 throughput-parity target against SQ8 was not met in this cohort. C160 closed-loop runs do not establish maximum throughput, single-request latency, or long-duration stability. These results are not general capacity recommendations or hardware-compatibility guarantees. The [recorded results](benchmarks/historical-v45-20261102.md) document the measured scope and limitations.

## Reproduce and inspect

- [General benchmark and cluster reproduction guide](reproduce/README.md)
- [Veortex V45 environment profile](reproduce/README.veortex.md)
- [Third-party notices and dependency inventory](third_party/THIRD_PARTY_NOTICES.md)
- [License audit manifest and hashes](third_party/license-audit.json)
- [colored 3.1.1 MPL-2.0 source availability](third_party/SOURCE-AVAILABILITY.md)

The benchmark helpers in `reproduce/` are separate from the engine binary. They do not build Qdrant. They include workload-generation and validation tools plus an external affinity helper for benchmark setups; they are not part of the Qdrant executable.

## License scope

[`LICENSE`](LICENSE) contains the Apache License 2.0 text. Qdrant and the external reproduction and benchmark helper source in `reproduce/` are identified as Apache-2.0 components in [`NOTICE`](NOTICE). That license notice does not assign a standalone license to Veortex source or grant rights to engine source code that is not included here. The owner authorized redistribution of this specific Veortex-containing binary. See [`third_party/`](third_party/THIRD_PARTY_NOTICES.md) for component-specific attributions and dependency terms.

# Shared-CPU full-matrix harness correction — 10 November 2026

The first full-matrix attempt was rejected by its worker-pool proof. Its performance measurement is **excluded from accepted performance tables**.

The benchmark launcher serialized a Python boolean as `QDRANT_VEORTEX_SEPARATE_TOPK=True`. This candidate recognizes `1` or lowercase `true` to enable supporting TopK workers, so that launch did not activate the requested pipeline. The readiness assertion compared against the same incorrect serialization; the independent worker-name and CPU-mask proof subsequently caught the mismatch.

This was a **benchmark-launcher configuration error**. The correction emits canonical `1`/`0`, checks the actual container environment, and retains the independent supporting-worker proof. It requires no engine source change or rebuild. The corrected campaign runs from a new evidence directory; the rejected attempt remains archived separately.

The rejected attempt recorded one timing row, zero accepted timing rows, and one passing 1,024-query FP32 accuracy check. Its originals were restored healthy, immutable dataset-layer metadata was unchanged, and cleanup reported zero errors. Passing accuracy alone did not satisfy the requested execution-path contract.

Candidate source: `560259c84af2b292867b9b2970ec731bcd33e07f`. ELF SHA-256: `63e9c5d1ffb9075bcfa3981c04a65c8240c9b18f1ad095456a93e9943ae466c6`. The passing [same-binary pipeline comparison](shared-postprocessing-ab-20261110.md) used the correct flag and remains valid.

The accompanying [diagnostic receipt](shared-cpu-fullmatrix-remediation-20261110.json) pins the rejected attempt and its restoration outcome. No throughput from that attempt is used to characterize the supporting-worker configuration.

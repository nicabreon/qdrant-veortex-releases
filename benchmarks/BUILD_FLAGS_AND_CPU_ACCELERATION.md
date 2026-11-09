# Build flags and CPU acceleration: native Qdrant versus Veortex

This note describes the exact artifacts used by the [80-row SQ8 comparison](h2h-sq8-batch-20261109.md) and the separate [V45.1 admission follow-up](h2h-sq8-admission-remediation-20261109.md). It adds provenance and source analysis; no benchmarks were rerun for this note. The [JSON receipt](build-provenance-20261109.json) records artifact hashes, embedded toolchain identifiers, and the limits of each observation.

## Native was downloaded, not rebuilt

The native baseline was extracted from the official [Qdrant v1.20.0 release](https://github.com/qdrant/qdrant/releases/tag/v1.20.0), asset `qdrant-x86_64-unknown-linux-gnu.tar.gz`. We checked its archive SHA-256 against the official asset digest:

```text
Archive: 2361f3df0dedfef31f5444f9f15bd15d6b4a6cba6ad952daecc5fbe3867c5ee6
ELF:     5081acd073ef29701415dc2d1655d98750be8c08008541febc20cf2935800f2f
```

We did not rebuild native with the Veortex toolchain or alter its executable. It ran in the pinned Ubuntu 24.04 container because its glibc requirements exceeded the host's. An external `LD_PRELOAD` affinity shim constrained search workers to the designated compute CPU; that is a runtime scheduling intervention, not a compiler flag. Its code is published in [the reproduction directory](../reproduce/README.md).

## What is known about the builds

| Item | Official native 1.20.0 | Veortex V45 / V45.1 |
|---|---|---|
| Provenance | Official GNU release asset | Local release builds from pinned source |
| Source commit | `222b2e44ab1c3f17e8246396ead6558e45041df7` | V45 `bc0eec0015771e8c59134b1b83a740418efcff7e`; V45.1 `a1a2af190e6f03508efa0b9105b88507dec9f7aa` |
| Rust identifier embedded in ELF | `1.99.1 (58cf8f9c3 2026-10-13)` | `1.98.0 (88d9e12ae 2026-08-18)` |
| Linker identifier embedded in ELF | LLD `23.1.1` | LLD `22.1.8` |
| Other embedded component identifiers | GCC `13.3.0`; clang `23.1.0git` | GCC `12.3.0`; clang `22.1.0-rc2` |
| Checked-in release profile | `lto="fat"`, `codegen-units=1` | Same settings |
| Effective Rust optimization/debug profile | Full artifact build invocation not captured | Cargo artifact metadata: `opt_level="3"`, `debuginfo=0`, debug assertions and overflow checks off |
| Global CPU-target flags / `RUSTFLAGS` | Not established for the downloaded artifact | No global CPU-target flag in the recorded command/overrides; V45.1's observed Cargo fingerprint has `rustflags=[]` |
| Optional Cargo features | Full effective feature set not captured | Recorded Qdrant artifact features: `["default"]`; the source default feature list is empty |

The embedded identifiers above come from `readelf -p .comment` on the actual three binaries. They identify linked components, not a complete build attestation or proof that every translation unit used those compilers. The current V45.1 fingerprint is not historical fingerprint evidence for V45; both have their own retained build receipts and Cargo artifact metadata.

The pinned native [Cargo profile](https://github.com/qdrant/qdrant/blob/222b2e44ab1c3f17e8246396ead6558e45041df7/Cargo.toml#L391-L393) documents source defaults, not proof that the official build had no overrides. Its [release workflow](https://github.com/qdrant/qdrant/blob/222b2e44ab1c3f17e8246396ead6558e45041df7/.github/workflows/release-artifacts.yml#L24-L46) selects stable Rust and delegates artifact building to a pinned upload action; it does not list a complete effective rustc invocation. The source minimum Rust version is not the compiler version used. The separate Dockerfile's `mold`/`TARGET_CPU` recipe must not be attributed to this downloaded GNU artifact: its ELF instead identifies LLD.

## Our flags and what they mean

The recorded engine command for both Veortex builds was:

```sh
taskset -c 0,1 nice -n 10 rustup run 1.98.0 cargo build \
  --bin qdrant --release --locked --offline -j 2 \
  --message-format=json-render-diagnostics
```

The builder sets `CARGO_INCREMENTAL=0`, `CARGO_PROFILE_RELEASE_DEBUG=0`, `CARGO_BUILD_JOBS=2`, disk-based target/temp directories, and the pinned `GIT_COMMIT_ID`. The V45.1 driver clears inherited `RUSTFLAGS`, `CARGO_ENCODED_RUSTFLAGS`, `CARGO_BUILD_RUSTFLAGS`, and `CARGO_PROFILE_*` / `CARGO_TARGET_*` overrides before applying its recorded environment.

| Setting | Meaning and interpretation |
|---|---|
| `--release`, `opt_level=3` | Optimize runtime code. A higher optimization level is not a guarantee of faster execution. |
| `lto="fat"` | Optimize across crate boundaries, at greater build/link cost. Both source profiles specify it. |
| `codegen-units=1` | Use one code-generation unit per crate; can improve generated code at a compile-time cost. |
| `debuginfo=0` | Omit debug information. This is separate from enabling/disabling runtime debug assertions. |
| `--locked`, `--offline` | Preserve lockfile resolution and avoid network fetching; these are dependency controls. |
| `-j 2`, `CARGO_BUILD_JOBS=2`, `taskset`, `nice` | Limit compiler jobs, placement, and priority during the build. They do not set the running server's compute budget. |
| No global `target-cpu=native` | Does not disable specialized SIMD/AMX functions: guarded runtime dispatch selects per-function implementations. |

Flag semantics are documented in the [Cargo profiles reference](https://doc.rust-lang.org/cargo/reference/profiles.html) and [rustc codegen reference](https://doc.rust-lang.org/rustc/codegen-options/index.html).

Both checked source trees also compile the x86 quantization **C helpers** using `-march=haswell -O3 -mpopcnt`; see the pinned native [build script](https://github.com/qdrant/qdrant/blob/222b2e44ab1c3f17e8246396ead6558e45041df7/lib/quantization/build.rs#L19-L36). Those are translation-unit flags, not the global Rust target or a ceiling on the separate Rust AVX-512/AMX implementations. They are source-recipe evidence for native, not a recovered official C compiler command.

`VX_PFH`, ring limits, coalescing windows, worker counts, `RAYON_NUM_THREADS`, and CPU affinity settings are **runtime configuration**, documented separately in [deployment](../DEPLOYMENT.md) and [the tested environment profile](../configs/admission-budget-node0.env.example).

## CPU acceleration by search path

This table describes x86 source support at the pinned commits, not a claim that every listed implementation ran in the SQ8 campaign. The proprietary fork's additions are reported from local source review; the fork source is not published here.

| Path | Stock Qdrant 1.20.0 | Qdrant + Veortex V45 / V45.1 |
|---|---|---|
| Scalar quantization SQ8, dot/cosine/L2 | AVX-512 VNNI + BW, AVX-VNNI, AVX2 + FMA, SSE4.1, then scalar fallback | Adds shared-read multi-query kernels and ring: AMX INT8, AVX-512 VNNI, AVX-512 BW, AVX-VNNI, AVX2, SSE4.1 + SSSE3, scalar |
| TurboQuant TQ2/TQ4 | AVX-512 F/BW/VNNI, AVX2, SSE4.1 + SSSE3, scalar | Adds the Veortex shared-read kernels/ring with the same tier family as SQ8 |
| Turbo8 / TQ8 | Native TurboQuant AVX-512 VNNI, AVX2, SSE kernels | Upstream path retained; no Veortex shared-read ring for this format in these releases |
| Turbo16 / TQ16 | AVX-512 BW kernel, selected only when the common backend detects AVX-512 F + BW + VNNI; then AVX2, SSE | Upstream path retained; no Veortex shared-read ring for this format in these releases |
| FP32 dot/cosine and exact candidate rerank | AVX + FMA, SSE, scalar, subject to dimension checks | Adds AVX-512 candidate rerank/blocking, with AVX2 + FMA and scalar fallbacks; not AMX FP32 arithmetic |
| FP16 dot/cosine | AVX + FMA + F16C, SSE, scalar | Upstream metric path retained; not a claim of Veortex FP16 ring coverage |
| Product quantization (PQ) | SSE4.1 lookup/scoring, scalar; ARM NEON separately | Upstream path retained; no Veortex shared-read ring for PQ in these releases |
| Binary quantization (BQ) | Binary-query scoring: AVX-512 VPOPCNTDQ/VL, SSE4.2, scalar; 4-/8-bit scalar-query scoring has a separate AVX2/SSE4.2 path | Upstream paths retained; no Veortex shared-read ring for BQ in these releases |

Native source references: [SQ8 dispatch](https://github.com/qdrant/qdrant/blob/222b2e44ab1c3f17e8246396ead6558e45041df7/lib/quantization/src/encoded_vectors_u8.rs#L867-L902), [TurboQuant backend selector](https://github.com/qdrant/qdrant/blob/222b2e44ab1c3f17e8246396ead6558e45041df7/lib/quantization/src/turboquant/simd/mod.rs#L12-L78), [TQ16](https://github.com/qdrant/qdrant/blob/222b2e44ab1c3f17e8246396ead6558e45041df7/lib/quantization/src/turboquant/simd/query16bit/mod.rs#L38-L66), [FP32 metrics](https://github.com/qdrant/qdrant/blob/222b2e44ab1c3f17e8246396ead6558e45041df7/lib/segment/src/spaces/simple.rs#L124-L186), and [FP16 dot metric](https://github.com/qdrant/qdrant/blob/222b2e44ab1c3f17e8246396ead6558e45041df7/lib/segment/src/spaces/metric_f16/simple_dot.rs#L22-L52).

The [PQ dispatcher](https://github.com/qdrant/qdrant/blob/222b2e44ab1c3f17e8246396ead6558e45041df7/lib/quantization/src/encoded_vectors_pq.rs#L658-L673) selects SSE4.1 rather than an AVX2/AVX-512 PQ scorer. The [BQ dispatcher](https://github.com/qdrant/qdrant/blob/222b2e44ab1c3f17e8246396ead6558e45041df7/lib/quantization/src/encoded_vectors_binary.rs#L455-L577) has encoding-dependent paths: the binary-query AVX-512 entry also checks lower ISA features; scalar 4-/8-bit query scoring does not select that entry.

SQ8's L1 metric uses the AVX2 implementation even through its VNNI entry; the table's SQ8 VNNI statement is for dot/cosine/L2. Turbo8 is not the same representation as scalar SQ8. ARM NEON paths, including NEON dot-product paths in TurboQuant, exist upstream, but this repository's releases and measurements are Linux x86_64 only. A search of the pinned native source found no AMX implementation. Optional upstream GPU support accelerates [HNSW index construction/linking](https://github.com/qdrant/qdrant/blob/222b2e44ab1c3f17e8246396ead6558e45041df7/lib/segment/src/index/hnsw_index/hnsw/build.rs#L162-L183); it is not a general GPU online-query path and is excluded from this CPU flat-search comparison.

Native already accepts HTTP batches and has storage/scorer batch APIs, including contiguous-vector runs in TurboQuant. Those are not the Veortex per-shard ring that admits concurrent queries and reuses gallery reads across them. Likewise, the ring's existence does not imply that every Qdrant datatype, metric, query, filter, or index uses it.

## Supported versus actually observed

In the published SQ8 matrix, all four Veortex **B1/C1** rows recorded **zero AMX calls** on all three nodes. Every Veortex row at **B1/C4 or higher concurrency**, and every explicit-batch row, recorded positive AMX-call deltas on all three nodes. The source can select a SIMD path for small query groups and AMX for larger eligible groups when CPU, OS tile state, and per-thread Linux permission allow it. Failed B64 rows are still failed rows despite positive kernel work.

The [published JSON](h2h-sq8-batch-20261109.json) contains these per-row `route_metric_delta` observations. They are engine counters, not an independent instruction-level profiler. We did not capture the official native executable's exact selected ISA per row; its source dispatch and the guest's feature list establish available paths, not instruction-by-instruction proof. Memory bandwidth was not measured in this matrix.

The measured difference may reflect shared gallery reads, ISA choice, tiling, scheduling, and support-stage placement together. Native kept scoring, TopK, and reranking in its one compute-CPU search closure; Veortex used one compute CPU for scan/score and the two support CPUs for TopK, FP32 rerank, and payload completion. Together with unmatched toolchains and incomplete native flags, this prevents attributing the entire gain to one kernel mechanism. The direction or size of the compiler-version effect has not been measured. A same-toolchain upstream rebuild plus controlled ablations would be a separate experiment, not a reinterpretation of these frozen results.

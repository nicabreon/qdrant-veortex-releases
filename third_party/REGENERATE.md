# Regenerating the license inventory

This directory was produced for the V45 x86_64 Linux artifact from Qdrant source commit `bc0eec0015771e8c59134b1b83a740418efcff7e` (tree `f3335fe4f9474c3bbc5274785c4bde930fc272be`) and its locked default-feature dependency graph. `license-audit.json` records the ELF SHA-256, Cargo.lock SHA-256, target-filtered Cargo metadata SHA-256, dependency inventory, and the exact `colored` source archive checksum.

To regenerate from an available checkout of that exact V45 source, with Rust/Cargo 1.98 and the Cargo registry/cache already populated, run from the release repository root:

```sh
rustup run 1.98.0 cargo metadata \
  --format-version 1 \
  --locked \
  --offline \
  --filter-platform x86_64-unknown-linux-gnu \
  --manifest-path /path/to/v45/source/Cargo.toml \
  > /tmp/qdrant-v45-metadata.json

python3 third_party/regenerate_notices.py \
  --metadata /tmp/qdrant-v45-metadata.json \
  --lock /path/to/v45/source/Cargo.lock \
  --qdrant-license /path/to/v45/source/LICENSE \
  --output third_party
```

`cargo metadata` inspects dependency metadata only: this workflow does not compile Qdrant or access the network. The generator copies only package files whose names identify legal text (`LICENSE`, `NOTICE`, `COPYING`, `COPYRIGHT`, and related names); for native binding crates it searches recursively for those legal filenames, without copying native source. It also copies the exact `colored-3.1.1.crate` from the Cargo cache and verifies it against the package checksum in Cargo.lock.

The expected hashes for the original input artifacts are:

- V45 Cargo.lock: `ad00f0767d39ab2b97286bec07a45033e81dc72b3c233877fb7ab46a21b86ac8`
- Target-filtered Cargo metadata JSON: `a49afefbf3495231c5020397c00d154fef3d6254f86b1329413bd6b2633e7c47`
- V45 ELF: `9a44f09da70af7921da7b2a6893b98c1ea3d9dcab61986d3504b63f4e3dfa0e8`

The inventory covers the normal/default runtime dependency closure only; it excludes dev and build dependencies. Review `license-audit.json` for the exact scope including local Qdrant path dependencies; see the two noted review items: the MPL-2.0 `colored` component (source archive included) and three local Qdrant path packages with missing per-package license metadata. This is an inventory of declared metadata and included texts, not a legal opinion or a blanket compliance guarantee.

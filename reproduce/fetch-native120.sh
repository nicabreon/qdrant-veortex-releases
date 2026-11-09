#!/usr/bin/env bash
set -euo pipefail
# Official unmodified upstream release; verify both archive and extracted ELF.
dest="${1:-./binaries/native120}"
mkdir -p -- "$dest"
if [[ -e "$dest/qdrant" ]]; then
  printf 'Refusing to overwrite %s/qdrant\n' "$dest" >&2
  exit 1
fi
tmp="$(mktemp -d "$dest/.download.XXXXXX")"
trap 'rm -rf -- "$tmp"' EXIT
url=https://github.com/qdrant/qdrant/releases/download/v1.20.0/qdrant-x86_64-unknown-linux-gnu.tar.gz
curl --fail --location --retry 3 --output "$tmp/upstream.tar.gz" "$url"
printf '%s  %s\n' 2361f3df0dedfef31f5444f9f15bd15d6b4a6cba6ad952daecc5fbe3867c5ee6 "$tmp/upstream.tar.gz" | sha256sum --check --status
tar -xzf "$tmp/upstream.tar.gz" -C "$tmp" qdrant
printf '%s  %s\n' 5081acd073ef29701415dc2d1655d98750be8c08008541febc20cf2935800f2f "$tmp/qdrant" | sha256sum --check --status
chmod 0755 "$tmp/qdrant"
mv -- "$tmp/qdrant" "$dest/qdrant"
printf 'Verified native Qdrant v1.20.0: %s/qdrant\n' "$dest"

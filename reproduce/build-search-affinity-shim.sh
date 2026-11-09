#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
source_file="${script_dir}/search_affinity.c"
output_file="${1:-${script_dir}/libqdrant_search_affinity.so}"
compiler="${CC:-cc}"
temporary_file="$(mktemp "${output_file}.tmp.XXXXXX")"
cleanup_temporary() {
    local status=$?
    trap - EXIT
    if [[ -n "${temporary_file:-}" && -f "${temporary_file}" ]]; then
        rm -f -- "${temporary_file}"
    fi
    exit "${status}"
}
trap cleanup_temporary EXIT

"${compiler}" \
    -std=gnu11 -O2 -fPIC -shared -pthread \
    -Wall -Wextra -Werror -Wformat=2 \
    -Wl,-z,relro,-z,now -Wl,--no-undefined \
    "${source_file}" -ldl -o "${temporary_file}"

size_bytes="$(stat -c '%s' -- "${temporary_file}")"
if (( size_bytes >= 1048576 )); then
    printf 'Refusing unexpectedly large shim (%s bytes): %s\n' "${size_bytes}" "${temporary_file}" >&2
    exit 1
fi
chmod 0644 -- "${temporary_file}"
mv -f -- "${temporary_file}" "${output_file}"
temporary_file=""
trap - EXIT
printf '%s\n' "${output_file}"

#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
shim="${script_dir}/libqdrant_search_affinity.so"
selftest="${script_dir}/search-affinity-selftest"
compiler="${CC:-cc}"

if [[ ! -f "${shim}" ]]; then
    "${script_dir}/build-search-affinity-shim.sh" >/dev/null
fi

"${compiler}" \
    -std=gnu11 -O2 -pthread -Wall -Wextra -Werror -Wformat=2 \
    "${script_dir}/search-affinity-selftest.c" -o "${selftest}"

read -r support_cpu_0 support_cpu_1 compute_cpu < <(
    python3 -c 'import os; cpus=sorted(os.sched_getaffinity(0)); assert len(cpus) >= 3; print(*cpus[:3])'
)
BENCH_SUPPORT_CPUS="${support_cpu_0},${support_cpu_1}" \
BENCH_COMPUTE_CPU="${compute_cpu}" \
LD_PRELOAD="${shim}" \
"${selftest}"

expected_cpuset="$(python3 -c 'import os; print(",".join(map(str, sorted(os.sched_getaffinity(0)))))')"
BENCH_EXPECTED_CPUSET="${expected_cpuset}" \
env -u BENCH_SUPPORT_CPUS -u BENCH_COMPUTE_CPU \
    LD_PRELOAD="${shim}" "${selftest}" --pass-through

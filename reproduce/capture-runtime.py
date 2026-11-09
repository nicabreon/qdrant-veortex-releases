#!/usr/bin/env python3
"""Capture Docker CPU budgets and running search-worker affinity on Linux.

Run while requests are active: Veortex creates ring workers lazily. This is
CPU evidence, not independent proof that every request used a specific scorer.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess


def command(args):
    return subprocess.check_output(args, text=True, timeout=30).strip()


def classify_veortex_thread(name, mask, compute_cpu, support_cpus):
    """Classify one instantaneous V45 thread mask from the pinned source contract.

    Return (role, state, error). A startup transition is recorded without claiming the
    worker has entered its steady phase; it is not a mask violation by itself.
    """
    compute = [compute_cpu]
    support = sorted(set(support_cpus))
    support_mask = set(support)
    singleton_support = len(mask) == 1 and mask[0] in support_mask

    if name.startswith('veortex-flat-c'):
        # Linux TASK_COMM_LEN leaves at most 15 visible bytes. For CPU 10+, the
        # decimal suffix can be truncated, so compare the expected visible name
        # and rely on the exact affinity mask for the full CPU identity.
        expected_name = f'veortex-flat-c{compute_cpu}'[:15]
        if name != expected_name:
            return 'compute_worker', 'mask_violation', f'{name} does not match expected thread name {expected_name}'
        if mask == compute:
            return 'compute_worker', 'active_exact_compute', None
        # DedicatedCpuWorker names its OS thread before its startup pin. Its ready
        # handshake occurs only after successful pinning, so this inherited support
        # mask is a transient startup observation, never search execution.
        if mask == support:
            return 'compute_worker', 'startup_before_pin', None
        return 'compute_worker', 'mask_violation', f'{name} mask {mask}, expected {compute} (or inherited startup mask {support})'

    if name.startswith('veortex-ring-') or name == 'veortex-rerank':
        if mask == compute:
            return 'compute_worker', 'active_exact_compute', None
        return 'compute_worker', 'mask_violation', f'{name} mask {mask}, expected {compute}'

    if name.startswith('veortex-topk-'):
        if singleton_support:
            return 'support_worker', 'active_exact_support_cpu', None
        return 'support_worker', 'mask_violation', f'{name} mask {mask}, expected one support CPU from {support}'

    if name.startswith('veortex-filter-'):
        expected = [support[0]] if support else []
        if mask == expected:
            return 'support_worker', 'active_exact_support_cpu', None
        return 'support_worker', 'mask_violation', f'{name} mask {mask}, expected {expected}'

    # Linux comm truncates payload-materialize-N to "payload-materia". The worker
    # starts on its creator's compute mask, then pins to one support CPU.
    if name.startswith('payload-materia'):
        if singleton_support:
            return 'support_worker', 'active_exact_support_cpu', None
        if mask == compute:
            return 'support_worker', 'startup_before_support_pin', None
        return 'support_worker', 'mask_violation', f'{name} mask {mask}, expected one support CPU from {support} (or startup mask {compute})'

    # These three names are used only until the worker pins and changes its name.
    # Ring starts inherit support affinity; TopK/filter starts inherit compute
    # affinity. The affinity transition precedes the rename, so either endpoint can
    # appear in a one-shot /proc snapshot without requiring repeated stable samples.
    if name == 'vx-ring-start':
        if mask == compute or mask == support:
            return 'startup_transition', 'mask_transition_observed', None
        return 'startup_transition', 'mask_violation', f'{name} mask {mask}, expected {compute} or inherited support mask {support}'
    if name == 'vx-topk-start':
        if mask == compute or singleton_support:
            return 'startup_transition', 'mask_transition_observed', None
        return 'startup_transition', 'mask_violation', f'{name} mask {mask}, expected {compute} or one support CPU from {support}'
    if name == 'vx-filter-start':
        if mask == compute or (support and mask == [support[0]]):
            return 'startup_transition', 'mask_transition_observed', None
        return 'startup_transition', 'mask_violation', f'{name} mask {mask}, expected {compute} or {[support[0]] if support else []}'

    if set(mask).issubset(support_mask):
        return 'support_thread', 'within_support_mask', None
    return 'support_thread', 'mask_violation', f'support thread {name} has mask {mask}, expected subset of {support}'


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--compose', action='append', required=True)
    p.add_argument('--env-file', required=True)
    p.add_argument('--variant', choices=['native', 'veortex'], required=True)
    p.add_argument('--compute-cpus', default='4,7,10')
    p.add_argument('--support-cpus', default='5,6;8,9;11,12')
    p.add_argument('--out', required=True)
    a = p.parse_args()
    compute = [int(x) for x in a.compute_cpus.split(',')]
    support = [sorted(set(map(int, group.split(',')))) for group in a.support_cpus.split(';')]
    if len(compute) != 3 or len(support) != 3:
        p.error('Supply one compute CPU and one support pair per node')
    compose = ['docker', 'compose', '--env-file', a.env_file]
    for file in a.compose:
        compose += ['-f', file]
    report = {'utc': datetime.now(timezone.utc).isoformat(), 'variant': a.variant,
              'clock_ticks_per_second': os.sysconf('SC_CLK_TCK'), 'nodes': [],
              'errors': [],
              'coverage': {'kind': 'single_instantaneous_snapshot',
                           'complete_phase_coverage': False,
                           'cpu_utilization_measured': False,
                           'note': 'Cumulative CPU ticks are not CPU utilization. Short-lived and startup phases can be missed; this snapshot does not prove scorer routing or physical host CPU isolation.'},
              'scope': 'Instantaneous affinity and cumulative ticks only; collect during load. Does not prove scorer routing or physical host CPU isolation.'}
    for node in range(3):
        cid = command(compose + ['ps', '-q', f'node{node}'])
        if not cid:
            raise RuntimeError(f'node{node} is absent')
        item = json.loads(command(['docker', 'inspect', cid]))[0]
        top = command(['docker', 'top', cid, '-eo', 'pid,comm']).splitlines()[1:]
        pids = [int(line.split()[0]) for line in top if 'qdrant' in line.split()[-1]]
        if len(pids) != 1:
            raise RuntimeError(f'Expected one Qdrant process in node{node}, got {pids}')
        pid = pids[0]
        status = Path(f'/proc/{pid}/status').read_text()
        ns_pid = int(next(line for line in status.splitlines() if line.startswith('NSpid:')).split()[-1])
        runtime_hash = command(['docker', 'exec', '-e', 'LD_PRELOAD=', cid, 'sha256sum', f'/proc/{ns_pid}/exe']).split()[0]
        row = {'node': node, 'container_id': cid, 'image': item['Image'],
               'cpuset': item['HostConfig']['CpusetCpus'], 'nano_cpus': item['HostConfig']['NanoCpus'],
               'runtime_elf_sha256': runtime_hash, 'threads': []}
        compute_workers = 0
        support_workers = 0
        startup_transitions = 0
        for task in sorted(Path(f'/proc/{pid}/task').iterdir()):
            try:
                name = (task/'comm').read_text().strip()
                mask = sorted(os.sched_getaffinity(int(task.name)))
                stat = (task/'stat').read_text().split(') ', 1)[1].split()
                if a.variant == 'native':
                    search = name.startswith(('search-cpu-', 'search-io-', 'search-ioall-'))
                    if search:
                        compute_workers += 1
                        role, state = 'compute_worker', 'active_exact_compute'
                        error = None if mask == [compute[node]] else f'{name} mask {mask}, expected {[compute[node]]}'
                    else:
                        role, state = 'support_thread', 'within_support_mask'
                        error = None if set(mask).issubset(set(support[node])) else f'support thread {name} has mask {mask}'
                else:
                    role, state, error = classify_veortex_thread(name, mask, compute[node], support[node])
                    if role == 'compute_worker' and state == 'active_exact_compute':
                        compute_workers += 1
                    elif role == 'support_worker' and state == 'active_exact_support_cpu':
                        support_workers += 1
                    elif role == 'startup_transition' or state.startswith('startup_'):
                        startup_transitions += 1
                if error:
                    report['errors'].append(f'node{node}: {error}')
                row['threads'].append({'tid': int(task.name), 'name': name, 'allowed_cpus': mask,
                                       'role': role, 'affinity_state': state,
                                       'cpu_ticks': int(stat[11]) + int(stat[12]), 'last_cpu': int(stat[36])})
            except FileNotFoundError:
                continue
        row['coverage'] = {'active_compute_workers_observed': compute_workers,
                           'active_support_workers_observed': support_workers,
                           'startup_transitions_observed': startup_transitions,
                           'status': ('ACTIVE_COMPUTE_SNAPSHOT' if compute_workers else
                                      'TRANSITION_ONLY_SNAPSHOT' if startup_transitions else
                                      'NO_SEARCH_WORKER_OBSERVED')}
        if not compute_workers and not startup_transitions:
            report['errors'].append(f'node{node}: no active named search workers; capture during load')
        if item['HostConfig']['NanoCpus'] != 3000000000:
            report['errors'].append(f'node{node}: CPU quota is not 3 CPUs')
        expected = set(support[node]) | {compute[node]}
        actual = set()
        for part in item['HostConfig']['CpusetCpus'].split(','):
            bounds = list(map(int, part.split('-')))
            actual.update(range(bounds[0], bounds[-1] + 1))
        if actual != expected or len(support[node]) != 2 or compute[node] in support[node]:
            report['errors'].append(f'node{node}: cpuset differs from disjoint compute + 2 support CPUs')
        report['nodes'].append(row)
    dest = Path(a.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'output': str(dest), 'nodes': len(report['nodes']), 'errors': report['errors']}))
    if report['errors']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()

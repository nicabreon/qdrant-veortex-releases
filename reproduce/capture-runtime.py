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
    support = [set(map(int, group.split(','))) for group in a.support_cpus.split(';')]
    if len(compute) != 3 or len(support) != 3:
        p.error('Supply one compute CPU and one support pair per node')
    compose = ['docker', 'compose', '--env-file', a.env_file]
    for file in a.compose:
        compose += ['-f', file]
    report = {'utc': datetime.now(timezone.utc).isoformat(), 'variant': a.variant,
              'clock_ticks_per_second': os.sysconf('SC_CLK_TCK'), 'nodes': [],
              'errors': [], 'scope': 'Instantaneous affinity and cumulative ticks; collect during load. Does not prove scorer routing or physical host CPU isolation.'}
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
        workers = 0
        for task in sorted(Path(f'/proc/{pid}/task').iterdir()):
            try:
                name = (task/'comm').read_text().strip()
                mask = sorted(os.sched_getaffinity(int(task.name)))
                stat = (task/'stat').read_text().split(') ', 1)[1].split()
                search = name.startswith(('search-cpu-', 'search-io-', 'search-ioall-')) if a.variant == 'native' else name.startswith('veortex-ring-')
                if search:
                    workers += 1
                    if mask != [compute[node]]:
                        report['errors'].append(f'node{node}: {name} mask {mask}, expected {[compute[node]]}')
                if a.variant == 'native' and not search and not set(mask).issubset(support[node]):
                    report['errors'].append(f'node{node}: support thread {name} has mask {mask}')
                if a.variant == 'veortex' and name.startswith(('veortex-topk-', 'veortex-rerank')) and not set(mask).issubset(support[node]):
                    report['errors'].append(f'node{node}: support worker {name} has mask {mask}')
                row['threads'].append({'tid': int(task.name), 'name': name, 'allowed_cpus': mask,
                                       'cpu_ticks': int(stat[11]) + int(stat[12]), 'last_cpu': int(stat[36])})
            except FileNotFoundError:
                continue
        if not workers:
            report['errors'].append(f'node{node}: no active named search workers; capture during load')
        if item['HostConfig']['NanoCpus'] != 3000000000:
            report['errors'].append(f'node{node}: CPU quota is not 3 CPUs')
        expected = support[node] | {compute[node]}
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

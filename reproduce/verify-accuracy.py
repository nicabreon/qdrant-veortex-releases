#!/usr/bin/env python3
"""Check every prepared approximate request against exact-FP32 Top10 truth.

This is a quality pass, excluded from benchmark timing. It never adjusts caps,
retries failed requests, modifies data, or treats a failed response as a match.
"""
import argparse
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import time
import workload


def verify_one(manifest, index, timeout, key_env, tolerance):
    body = json.loads(base64.b64decode(manifest['request_bodies_base64'][index]))
    if body.get('limit') != 10 or body.get('params', {}).get('exact') is not False:
        raise ValueError('quality request must be approximate and return Top10')
    q = body['params']['quantization']
    if q.get('ignore') is not False or q.get('rescore') is not True or 'oversampling' not in q:
        raise ValueError('quality request must use pinned quantization, oversampling and FP32 rescore')
    response = workload.api_request(manifest['endpoint'], 'POST', body=body, timeout=timeout, api_key_env=key_env)
    hits = response.get('result')
    expected = manifest['candidate_truth'][index]
    if not isinstance(hits, list) or len(hits) != 10 or len(expected) != 10:
        raise ValueError('result and reference must each contain exactly 10 hits')
    for rank, (hit, ref) in enumerate(zip(hits, expected), 1):
        if str(hit['id']) != str(ref['id']):
            raise ValueError(f'ordered ID mismatch at rank {rank}: actual={hit["id"]}, expected={ref["id"]}')
        score = float(hit['score'])
        reference_score = float(ref['score'])
        if not math.isfinite(score) or not math.isfinite(reference_score) or abs(score-reference_score) > tolerance:
            raise ValueError(f'FP32 score mismatch at rank {rank}')
        if manifest['with_payload']:
            if hit.get('payload') != workload.payload_for_id(int(ref['id'])):
                raise ValueError(f'metadata mismatch at rank {rank}')
        elif hit.get('payload') not in (None, {}):
            raise ValueError(f'unexpected payload at rank {rank}')


def run(args):
    output = Path(args.out)
    if output.exists():
        raise ValueError('Refusing to overwrite an existing accuracy report')
    if not 1 <= args.concurrency <= 160:
        raise ValueError('concurrency must be in 1..160')
    report = {'schema': 'qdrant_top10_live_accuracy_v1',
              'utc': datetime.now(timezone.utc).isoformat(),
              'scope': 'All 1024 queries per category against cached exact-FP32 truth; reused corpus, not a holdout or universal recall claim. Excluded from performance timing.',
              'concurrency': args.concurrency, 'score_tolerance': args.score_tolerance, 'categories': []}
    for category in workload.CATEGORIES:
        path = Path(args.manifest_dir)/(category+'.json')
        manifest = json.loads(path.read_text())
        if manifest['query_count'] != 1024 or manifest['result_limit'] != 10 or len(manifest['request_bodies_base64']) != 1024 or len(manifest['candidate_truth']) != 1024:
            raise ValueError('Expected exactly 1024 requests and references, each Top10')
        row = {'category': category, 'manifest_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
               'profile': manifest.get('pins', {}).get('profile'),
               'candidate_count_per_segment': manifest.get('pins', {}).get('candidate_count_per_segment'),
               'queries': 1024, 'passed': 0, 'failed': 0, 'first_errors': []}
        start = time.monotonic()
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            pending = {pool.submit(verify_one, manifest, i, args.timeout, args.api_key_env, args.score_tolerance): i for i in range(1024)}
            for future in as_completed(pending):
                try:
                    future.result()
                    row['passed'] += 1
                except Exception as error:
                    row['failed'] += 1
                    if len(row['first_errors']) < 50:
                        row['first_errors'].append({'query': pending[future], 'error': str(error)[:400]})
        row['elapsed_s'] = time.monotonic()-start
        report['categories'].append(row)
        print(json.dumps({k: v for k, v in row.items() if k != 'first_errors'}), flush=True)
    report['passed'] = all(row['passed'] == 1024 and row['failed'] == 0 for row in report['categories'])
    report['status'] = 'PASSED_CORPUS' if report['passed'] else 'FAILED_CORPUS'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2)+'\n')
    return report['passed']


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest-dir', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--concurrency', type=int, default=32)
    p.add_argument('--timeout', type=float, default=30)
    p.add_argument('--score-tolerance', type=float, default=1e-6)
    p.add_argument('--api-key-env', default='QDRANT_API_KEY')
    args = p.parse_args()
    if args.timeout <= 0 or not 0 <= args.score_tolerance <= 1e-6:
        p.error('timeout must be positive and score tolerance must be in 0..1e-6')
    if not run(args):
        raise SystemExit(1)


if __name__ == '__main__':
    main()

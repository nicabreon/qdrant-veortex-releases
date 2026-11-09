#!/usr/bin/env python3
"""Portable corpus, truth-manifest, and run helpers for the stock Qdrant bench."""

from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import struct
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


DIM = 512
QUERY_COUNT = 1024
TOPK = 10
MAX_POINTS = 3_000_000
POSITIONS = (
    "left_thumb", "left_index", "left_middle", "left_ring", "left_little",
    "right_thumb", "right_index", "right_middle", "right_ring", "right_little",
)
CATEGORIES = {
    "nf_false": {"with_payload": False, "filter": None},
    "nf_true": {"with_payload": True, "filter": None},
    "active90_payload": {
        "with_payload": True,
        "filter": {"must": [{"key": "abis.active", "match": {"value": True}}]},
    },
    "narrow9_payload": {
        "with_payload": True,
        "filter": {
            "must": [
                {"key": "abis.active", "match": {"value": True}},
                {"key": "attributes.position", "match": {"value": "left_index"}},
            ],
            "must_not": [
                {"key": "abis.subject_id", "match": {"value": "00000000-0000-4000-8000-000000000001"}}
            ],
        },
    },
}
MANIFEST_SCHEMA = "benchmark_abis_payload_b1_top10_go_manifest_v1"
PROFILE_SETTINGS = {
    "sq8": {
        "quantization_config": {"scalar": {"type": "int8", "quantile": 1.0, "always_ram": True}},
        "branch": "scalar",
        "default_candidate_count": 12,
    },
    "tq2": {
        "quantization_config": {"turbo": {"bits": "bits2", "always_ram": True}},
        "branch": "turbo",
        "default_candidate_count": 1767,
    },
    "tq4": {
        "quantization_config": {"turbo": {"bits": "bits4", "always_ram": True}},
        "branch": "turbo",
        "default_candidate_count": 40,
    },
}
PAYLOAD_INDEXES = {
    "abis.subject_id": "keyword",
    "abis.active": "bool",
    "attributes.position": "keyword",
}
OPTIMIZER_SETTINGS = {
    "indexing_threshold": 1,
    "default_segment_number": 1,
    "max_segment_size": 4_194_304,
    "max_optimization_threads": 0,
}
OPTIMIZER_BULK_SETTINGS = {**OPTIMIZER_SETTINGS, "indexing_threshold": 0}
OPTIMIZER_BUILD_SETTINGS = {**OPTIMIZER_SETTINGS, "indexing_threshold": 1, "max_optimization_threads": 1}
LEGACY_TRUTH_FILES = {
    "nf_false": ("nf_false.jsonl", "unfiltered_payload-independent-f32.jsonl.gz"),
    "nf_true": ("nf_true.jsonl", "unfiltered_payload-independent-f32.jsonl.gz"),
    "active90_payload": ("active90_payload.jsonl", "active_only-independent-f32.jsonl.gz"),
    "narrow9_payload": ("narrow9_payload.jsonl", "active_position_exclude-independent-f32.jsonl.gz"),
}


def require_numpy():
    try:
        import numpy as np
    except ImportError as exc:
        raise SystemExit("NumPy is required for generate/load. Install it with: python3 -m pip install numpy") from exc
    return np


def compact_json(value) -> bytes:
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def payload_for_id(point_id: int) -> dict:
    active = (point_id // 10) % 10 != 0
    status = "active" if active else "inactive"
    return {
        "abis": {
            "active": active,
            "biometric_record_id": f"00000001-0000-4000-8000-{point_id:012x}",
            "collection_id": "00000002-0000-4000-8000-000000000001",
            "model_version": "gaussian-512-bench-v1",
            "normalization_version": "cosine-l2-f32-v1",
            "operation": "upsert",
            "subject_id": f"00000000-0000-4000-8000-{point_id // 10:012x}",
        },
        "attributes": {"position": POSITIONS[point_id % 10], "status": status},
    }


def metadata_digest(hits: list[dict]) -> str:
    rows = [{"id": int(hit["id"]), "payload": payload_for_id(int(hit["id"]))} for hit in hits]
    return hashlib.sha256(compact_json(rows)).hexdigest()


def profile_candidate_params(profile: str, candidate_count=None) -> dict:
    if profile not in PROFILE_SETTINGS:
        raise ValueError(f"unsupported quantization profile {profile!r}; choose sq8, tq2, or tq4")
    default_count = PROFILE_SETTINGS[profile]["default_candidate_count"]
    cap = default_count if candidate_count is None else candidate_count
    if isinstance(cap, bool) or not isinstance(cap, int) or cap < TOPK:
        raise ValueError(f"candidate count must be an integer >= {TOPK}")
    return {
        "profile": profile,
        "candidate_count_per_segment": cap,
        "oversampling": cap / TOPK,
        "default_candidate_count_per_segment": default_count,
        "candidate_count_source": "historical_sufficient_cap" if candidate_count is None else "explicit_override",
    }


def quantization_matches(actual, profile: str) -> bool:
    expected = PROFILE_SETTINGS[profile]["quantization_config"]
    if not isinstance(actual, dict) or set(actual) != set(expected):
        return False
    branch = PROFILE_SETTINGS[profile]["branch"]
    actual_values = actual.get(branch)
    return isinstance(actual_values, dict) and all(actual_values.get(key) == value for key, value in expected[branch].items())


def payload_schema_errors(schema, *, expected_points=None, allow_missing=False):
    if not isinstance(schema, dict):
        return ["payload_schema is not an object"]
    errors = []
    unexpected = sorted(set(schema) - set(PAYLOAD_INDEXES))
    if unexpected:
        errors.append(f"unexpected indexed payload fields: {unexpected}")
    if not allow_missing:
        missing = sorted(set(PAYLOAD_INDEXES) - set(schema))
        if missing:
            errors.append(f"missing indexed payload fields: {missing}")
    for field, value in schema.items():
        expected_type = PAYLOAD_INDEXES.get(field)
        if expected_type is None:
            continue
        if not isinstance(value, dict) or value.get("data_type") != expected_type:
            errors.append(f"payload index {field} must have data_type={expected_type}")
            continue
        points = value.get("points")
        if expected_points is not None and points != expected_points:
            errors.append(f"payload index {field} covers {points!r} points; expected {expected_points}")
        elif points is not None and (isinstance(points, bool) or not isinstance(points, int) or points < 0):
            errors.append(f"payload index {field} has invalid points count {points!r}")
    return errors


def optimizer_readiness_errors(result, profile: str, *, expected_points=None, optimizer_settings=None):
    result = result if isinstance(result, dict) else {}
    errors = []
    if result.get("status") != "green":
        errors.append(f"collection status is {result.get('status')!r}, expected 'green'")
    if result.get("optimizer_status") != "ok":
        errors.append(f"optimizer_status is {result.get('optimizer_status')!r}, expected 'ok'")
    points = result.get("points_count")
    if isinstance(points, bool) or not isinstance(points, int) or points < TOPK:
        errors.append(f"points_count is invalid: {points!r}")
    elif expected_points is not None and points != expected_points:
        errors.append(f"points_count is {points}, expected {expected_points}")
    indexed = result.get("indexed_vectors_count")
    if indexed != points:
        errors.append(f"indexed_vectors_count is {indexed!r}, expected points_count {points!r}")
    config = result.get("config") or {}
    optimizer = config.get("optimizer_config") or {}
    for key, expected in (optimizer_settings or OPTIMIZER_SETTINGS).items():
        if optimizer.get(key) != expected:
            errors.append(f"optimizer_config.{key} is {optimizer.get(key)!r}, expected {expected}")
    if not quantization_matches(config.get("quantization_config") or {}, profile):
        errors.append(f"quantization_config does not match profile {profile}")
    errors.extend(payload_schema_errors(result.get("payload_schema"), expected_points=points))
    return errors


def get_collection_info(collection_url, api_key_env, timeout=60):
    return api_request(collection_url, "GET", api_key_env=api_key_env, timeout=timeout).get("result") or {}


def update_collection_optimizers(collection_url, settings, *, api_key_env, timeout):
    body = {"optimizers_config": settings}
    api_request(f"{collection_url}?timeout={timeout}", "PATCH", body=body,
                api_key_env=api_key_env, timeout=timeout)


def ensure_payload_indexes(collection_url, schema, *, api_key_env, timeout):
    errors = payload_schema_errors(schema, allow_missing=True)
    if errors:
        raise RuntimeError("collection payload indexes are incompatible: " + "; ".join(errors))
    for field_name, field_schema in PAYLOAD_INDEXES.items():
        if field_name in schema:
            continue
        endpoint = f"{collection_url}/index?wait=true"
        api_request(endpoint, "PUT", body={"field_name": field_name, "field_schema": field_schema},
                    api_key_env=api_key_env, timeout=timeout)


def verify_cluster_membership(endpoints: list[str], *, api_key_env: str):
    if len(endpoints) != 3:
        raise RuntimeError("--peer-endpoints must list all 3 node HTTP endpoints before collection creation")
    observations = []
    peer_ids = set()
    leaders = set()
    membership = None
    for endpoint in endpoints:
        endpoint = validate_base_url(endpoint)
        result = api_request(endpoint_for(endpoint, "/cluster"), "GET", api_key_env=api_key_env).get("result") or {}
        if result.get("status") != "enabled":
            raise RuntimeError(f"{endpoint}/cluster reports status={result.get('status')!r}, expected 'enabled'")
        peer_id = result.get("peer_id")
        if isinstance(peer_id, bool) or not isinstance(peer_id, int):
            raise RuntimeError(f"{endpoint}/cluster does not report an integer peer ID")
        peer_id = str(peer_id)
        if peer_id in peer_ids:
            raise RuntimeError("--peer-endpoints did not resolve to three distinct cluster peer IDs")
        peer_ids.add(peer_id)
        peers = result.get("peers") or {}
        normalized = {
            str(key): (value.get("uri") if isinstance(value, dict) else value)
            for key, value in peers.items()
        }
        if len(normalized) != 3:
            raise RuntimeError(f"{endpoint}/cluster reports {len(normalized)} peers, expected 3")
        raft = result.get("raft_info") or {}
        leader = raft.get("leader")
        if leader is None:
            raise RuntimeError(f"{endpoint}/cluster reports no Raft leader")
        leaders.add(str(leader))
        if membership is None:
            membership = normalized
        elif normalized != membership:
            raise RuntimeError("the three /cluster endpoints disagree on peer membership")
        observations.append({"endpoint": endpoint, "peer_id": peer_id, "leader": str(leader)})
    if set(membership or {}) != peer_ids:
        raise RuntimeError(f"cluster membership {sorted(membership or {})} does not match contacted peers {sorted(peer_ids)}")
    if len(leaders) != 1 or next(iter(leaders)) not in peer_ids:
        raise RuntimeError(f"the three nodes do not report one common Raft leader: {sorted(leaders)}")
    return {"members": membership, "leader_id": next(iter(leaders)), "observations": observations}


def wait_collection_ready(collection_url, *, profile, expected_points, api_key_env, timeout,
                          readiness_timeout, poll_interval, optimizer_settings=None):
    deadline = time.monotonic() + readiness_timeout
    last_result = {}
    last_errors = ["collection has not been checked yet"]
    while True:
        last_result = get_collection_info(collection_url, api_key_env, timeout=timeout)
        last_errors = optimizer_readiness_errors(
            last_result, profile, expected_points=expected_points,
            optimizer_settings=optimizer_settings,
        )
        if not last_errors:
            return last_result
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError(
                f"collection did not reach benchmark-ready state within {readiness_timeout}s: "
                + "; ".join(last_errors)
            )
        time.sleep(min(poll_interval, remaining))


def validate_base_url(value: str) -> str:
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.netloc or parts.username or parts.password or parts.fragment:
        raise ValueError("endpoint must be an absolute HTTP(S) base URL without credentials or a fragment")
    if parts.query:
        raise ValueError("endpoint must not include a query string")
    return value.rstrip("/")


def api_request(endpoint: str, method: str, *, body=None, api_key_env="QDRANT_API_KEY", timeout=60):
    headers = {"Accept": "application/json"}
    api_key = os.environ.get(api_key_env, "")
    if api_key:
        headers["api-key"] = api_key
    encoded = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        encoded = compact_json(body)
    request = Request(endpoint, data=encoded, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read()
            status = response.status
    except HTTPError as exc:
        preview = exc.read(4096).decode("utf-8", "replace")
        raise RuntimeError(f"HTTP {exc.code} for {method} {endpoint}: {preview}") from exc
    except URLError as exc:
        raise RuntimeError(f"request failed for {method} {endpoint}: {exc}") from exc
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"non-JSON response from {method} {endpoint} (HTTP {status})") from exc
    if status < 200 or status >= 300:
        raise RuntimeError(f"HTTP {status} for {method} {endpoint}: {value}")
    return value


def endpoint_for(base: str, suffix: str) -> str:
    return f"{base.rstrip('/')}{suffix}"


def write_metadata(path: Path, count: int):
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for point_id in range(count):
            stream.write(json.dumps({"id": point_id, "payload": payload_for_id(point_id)}, separators=(",", ":")))
            stream.write("\n")


def cmd_generate(args):
    np = require_numpy()
    out = Path(args.out).resolve()
    if args.points < TOPK or args.points > MAX_POINTS:
        raise SystemExit(f"--points must be in {TOPK}..{MAX_POINTS}; the Go validator is pinned to the 3M ID range")
    if args.dimension != DIM or args.queries != QUERY_COUNT:
        raise SystemExit("the Go benchmark contract requires --dimension 512 and --queries 1024")
    if args.batch_size < 1 or args.seed < 0:
        raise SystemExit("--batch-size must be positive and --seed must be non-negative")
    out.mkdir(parents=True, exist_ok=True)
    gallery_path = out / "gallery.f32"
    metadata_path = out / "metadata.jsonl"
    queries_path = out / "queries.npy"
    dataset_path = out / "dataset.json"
    existing = [path for path in (gallery_path, metadata_path, queries_path, dataset_path) if path.exists()]
    if existing and not args.force:
        raise SystemExit(f"refusing to overwrite {existing[0]}; choose a new --out directory or pass --force")

    gallery_bytes = args.points * DIM * 4
    sample_metadata_bytes = max(
        len(compact_json({"id": point_id, "payload": payload_for_id(point_id)})) + 1
        for point_id in range(20)
    )
    metadata_bytes_upper_bound = args.points * (sample_metadata_bytes + len(str(args.points - 1)) - 1)
    query_bytes = QUERY_COUNT * DIM * 4 + 4096
    required_bytes = gallery_bytes + metadata_bytes_upper_bound + query_bytes
    available_bytes = shutil.disk_usage(out).free
    if available_bytes < required_bytes:
        raise SystemExit(
            f"need at least {required_bytes:,} free bytes for gallery/metadata/queries; "
            f"only {available_bytes:,} are available (Qdrant storage and filesystem quotas are not included)"
        )
    if args.force:
        for path in (gallery_path, metadata_path, queries_path, dataset_path):
            if path.exists():
                path.unlink()

    # Generate a single normalized FP32 gallery before category-specific query
    # bodies/manifests exist. The metadata file is a complete, separate input.
    gallery = np.memmap(gallery_path, dtype="<f4", mode="w+", shape=(args.points, DIM))
    rng = np.random.Generator(np.random.PCG64(args.seed))
    for start in range(0, args.points, args.batch_size):
        stop = min(args.points, start + args.batch_size)
        block = rng.standard_normal((stop - start, DIM), dtype=np.float32)
        norms = np.linalg.norm(block, axis=1, keepdims=True)
        if not np.isfinite(norms).all() or np.any(norms == 0):
            raise RuntimeError(f"generated gallery block {start}:{stop} has an invalid norm")
        block /= norms
        if not np.isfinite(block).all():
            raise RuntimeError(f"generated gallery block {start}:{stop} contains NaN or infinity")
        gallery[start:stop] = block
    gallery.flush()
    del gallery
    write_metadata(metadata_path, args.points)

    query_seed = (args.seed ^ 0x9E3779B97F4A7C15) & ((1 << 64) - 1)
    query_rng = np.random.Generator(np.random.PCG64(query_seed))
    queries = query_rng.standard_normal((QUERY_COUNT, DIM), dtype=np.float32)
    query_norms = np.linalg.norm(queries, axis=1, keepdims=True)
    if not np.isfinite(query_norms).all() or np.any(query_norms == 0):
        raise RuntimeError("generated query vectors have an invalid norm")
    queries /= query_norms
    if not np.isfinite(queries).all():
        raise RuntimeError("generated query vectors contain NaN or infinity")
    np.save(queries_path, queries, allow_pickle=False)
    query_hash = hashlib.sha256(queries.astype("<f4", copy=False).tobytes(order="C")).hexdigest()
    dataset = {
        "schema": "qdrant_stock_sq8_synthetic_dataset_v1",
        "points": args.points,
        "dimension": DIM,
        "seed": args.seed,
        "numpy_version": np.__version__,
        "bit_generator": "PCG64",
        "gallery": gallery_path.name,
        "gallery_encoding": "little-endian float32 row-major, L2-normalized Gaussian",
        "metadata": metadata_path.name,
        "metadata_schema": "deterministic ABIS payload; active=(id//10)%10!=0; position=id%10",
        "queries": queries_path.name,
        "query_count": QUERY_COUNT,
        "query_vectors_sha256_f32le": query_hash,
        "shards": 3,
        "replication_factor": 1,
        "hnsw_m": 0,
        "hnsw_payload_m": 0,
        "scalar_quantization": {"type": "int8", "quantile": 1.0, "always_ram": True},
    }
    dataset_path.write_text(json.dumps(dataset, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "generated", "directory": str(out), **dataset}, indent=2))


def qdrant_payload_rows(path: Path, count: int):
    with path.open("r", encoding="utf-8") as stream:
        for expected_id in range(count):
            line = stream.readline()
            if not line:
                raise RuntimeError(f"metadata file ended at ID {expected_id}")
            row = json.loads(line)
            if row.get("id") != expected_id or row.get("payload") != payload_for_id(expected_id):
                raise RuntimeError(f"metadata row {expected_id} does not match the Go deterministic payload contract")
            yield row["payload"]
        if stream.readline():
            raise RuntimeError(f"metadata file has more than {count} rows")


def verify_shard_layout(endpoints: list[str], collection: str, *, expected_points: int, api_key_env: str):
    if len(endpoints) != 3:
        raise RuntimeError("--peer-endpoints must list all 3 node HTTP endpoints to verify shard ownership")
    owners = []
    seen_peers = set()
    for endpoint in endpoints:
        endpoint = validate_base_url(endpoint)
        result = api_request(
            endpoint_for(endpoint, f"/collections/{collection}/cluster"),
            "GET", api_key_env=api_key_env,
        ).get("result") or {}
        peer_id = result.get("peer_id")
        if peer_id is None or peer_id in seen_peers:
            raise RuntimeError("peer endpoints did not return three distinct collection peer IDs")
        seen_peers.add(peer_id)
        if result.get("shard_count") != 3:
            raise RuntimeError(f"peer {peer_id} reports shard_count={result.get('shard_count')!r}, expected 3")
        local_shards = result.get("local_shards") or []
        remote_shards = result.get("remote_shards") or []
        if any(shard.get("state") != "Active" for shard in [*local_shards, *remote_shards]):
            raise RuntimeError(f"peer {peer_id} reports a non-active local or remote shard")
        if result.get("shard_transfers"):
            raise RuntimeError(f"peer {peer_id} reports in-progress shard transfers")
        if result.get("resharding_operations"):
            raise RuntimeError(f"peer {peer_id} reports in-progress resharding")
        for shard in local_shards:
            owners.append((shard.get("shard_id"), peer_id, shard.get("points_count")))

    shard_ids = [shard_id for shard_id, _, _ in owners]
    if sorted(shard_ids) != [0, 1, 2]:
        raise RuntimeError(f"local shard ownership must cover each shard 0, 1, 2 exactly once; got {owners}")
    if len({peer_id for _, peer_id, _ in owners}) != 3:
        raise RuntimeError(f"the 3 RF1 shards must be assigned to 3 distinct peers; got {owners}")
    local_points = sum(points_count or 0 for _, _, points_count in owners)
    if any(not isinstance(points_count, int) or points_count <= 0 for _, _, points_count in owners):
        raise RuntimeError(f"every active local shard must report a positive point estimate; got {owners}")
    return {
        "shards": [{"shard_id": shard_id, "peer_id": peer_id, "points_count_estimate": points_count}
                   for shard_id, peer_id, points_count in sorted(owners)],
        "local_points_count_estimate_sum": local_points,
        "collection_points_count": expected_points,
    }


def cmd_load(args):
    np = require_numpy()
    if args.batch_size < 1:
        raise SystemExit("--batch-size must be positive")
    if args.timeout < 1 or args.readiness_timeout <= 0 or args.poll_interval <= 0:
        raise SystemExit("--timeout, --readiness-timeout, and --poll-interval must be positive")
    data_dir = Path(args.data_dir).resolve()
    dataset = json.loads((data_dir / "dataset.json").read_text(encoding="utf-8"))
    count = int(dataset["points"])
    dimension = int(dataset["dimension"])
    if dataset.get("schema") != "qdrant_stock_sq8_synthetic_dataset_v1" or count < TOPK or count > MAX_POINTS or dimension != DIM:
        raise SystemExit("dataset.json does not match the supported normalized 512D workload schema")
    if args.profile not in PROFILE_SETTINGS:
        raise SystemExit("--profile must be sq8, tq2, or tq4")
    gallery_path = data_dir / dataset["gallery"]
    metadata_path = data_dir / dataset["metadata"]
    expected_bytes = count * dimension * 4
    if gallery_path.stat().st_size != expected_bytes:
        raise SystemExit(f"gallery size is {gallery_path.stat().st_size}, expected {expected_bytes} bytes")
    gallery = np.memmap(gallery_path, dtype="<f4", mode="r", shape=(count, dimension))
    for start in range(0, count, args.batch_size):
        stop = min(count, start + args.batch_size)
        block = gallery[start:stop]
        norms = np.linalg.norm(block, axis=1)
        if not np.isfinite(block).all() or not np.allclose(norms, 1.0, rtol=0.0, atol=1e-4):
            raise SystemExit(f"gallery vectors {start}:{stop} are non-finite or not L2-normalized")
    for _ in qdrant_payload_rows(metadata_path, count):
        pass

    base = validate_base_url(args.endpoint)
    collection = quote(args.collection, safe="")
    collection_url = endpoint_for(base, f"/collections/{collection}")
    endpoints = [value.strip() for value in args.peer_endpoints.split(",") if value.strip()]
    cluster_membership = verify_cluster_membership(endpoints, api_key_env=args.api_key_env)
    if args.create:
        create_body = {
            "vectors": {"gallery": {"size": dimension, "distance": "Cosine"}},
            "shard_number": 3,
            "replication_factor": 1,
            "hnsw_config": {"m": 0, "payload_m": 0},
            "optimizers_config": OPTIMIZER_BULK_SETTINGS,
            "quantization_config": PROFILE_SETTINGS[args.profile]["quantization_config"],
        }
        result = api_request(collection_url + "?wait=true", "PUT", body=create_body, api_key_env=args.api_key_env)
        print(f"collection creation: {result}", file=sys.stderr)
    collection_result = get_collection_info(collection_url, args.api_key_env, timeout=args.timeout)
    config = collection_result.get("config") or {}
    params = config.get("params") or {}
    vectors = params.get("vectors") or {}
    vector_config = vectors.get("gallery") if isinstance(vectors, dict) else None
    hnsw = config.get("hnsw_config") or {}
    quantization = config.get("quantization_config") or {}
    expected = (
        isinstance(vector_config, dict)
        and vector_config.get("size") == dimension
        and vector_config.get("distance") == "Cosine"
        and params.get("shard_number") == 3
        and params.get("replication_factor") == 1
        and hnsw.get("m") == 0 and hnsw.get("payload_m") == 0
        and quantization_matches(quantization, args.profile)
    )
    if not expected:
        raise SystemExit(f"collection config does not match named gallery/512/Cosine, 3 shards/RF1, m=0/payload_m=0, profile={args.profile}")
    starting_points = collection_result.get("points_count")
    if isinstance(starting_points, bool) or not isinstance(starting_points, int) or starting_points != 0:
        raise SystemExit(
            f"load requires an empty collection; found points_count={starting_points!r}. "
            "Use prepare-manifests for an already-loaded collection."
        )

    schema = collection_result.get("payload_schema") or {}
    schema_errors = payload_schema_errors(schema, expected_points=0, allow_missing=True)
    if schema_errors:
        raise SystemExit("collection payload indexes are incompatible: " + "; ".join(schema_errors))
    # Disable vector indexing while uploading so the global 10,000,000 KB
    # threshold cannot prevent quantization on this 3M-point fixture. Create
    # the three payload indexes before any point is uploaded.
    update_collection_optimizers(collection_url, OPTIMIZER_BULK_SETTINGS,
                                 api_key_env=args.api_key_env, timeout=args.timeout)
    ensure_payload_indexes(collection_url, schema, api_key_env=args.api_key_env, timeout=args.timeout)
    indexed_result = get_collection_info(collection_url, args.api_key_env, timeout=args.timeout)
    index_errors = payload_schema_errors(indexed_result.get("payload_schema"), allow_missing=False)
    if index_errors:
        raise RuntimeError("payload indexes are not ready for loading: " + "; ".join(index_errors))

    payload_iter = iter(qdrant_payload_rows(metadata_path, count))
    points_url = endpoint_for(base, f"/collections/{collection}/points?wait=true")
    sent = 0
    for start in range(0, count, args.batch_size):
        stop = min(count, start + args.batch_size)
        block = gallery[start:stop]
        points = []
        for offset, vector in enumerate(block):
            points.append({
                "id": start + offset,
                "vector": {"gallery": vector.tolist()},
                "payload": next(payload_iter),
            })
        api_request(points_url, "PUT", body={"points": points}, api_key_env=args.api_key_env, timeout=args.timeout)
        sent += len(points)
        print(f"uploaded {sent}/{count}", file=sys.stderr, flush=True)
    # max_optimization_threads=0 disables optimization in Qdrant. Enable one
    # optimizer thread while threshold=1 builds quantized segments, then freeze
    # the recorded final config only after every vector is indexed.
    update_collection_optimizers(collection_url, OPTIMIZER_BUILD_SETTINGS,
                                 api_key_env=args.api_key_env, timeout=args.timeout)
    wait_collection_ready(
        collection_url, profile=args.profile, expected_points=count,
        api_key_env=args.api_key_env, timeout=args.timeout,
        readiness_timeout=args.readiness_timeout, poll_interval=args.poll_interval,
        optimizer_settings=OPTIMIZER_BUILD_SETTINGS,
    )
    update_collection_optimizers(collection_url, OPTIMIZER_SETTINGS,
                                 api_key_env=args.api_key_env, timeout=args.timeout)
    final_result = wait_collection_ready(
        collection_url, profile=args.profile, expected_points=count,
        api_key_env=args.api_key_env, timeout=args.timeout,
        readiness_timeout=args.readiness_timeout, poll_interval=args.poll_interval,
    )
    shard_owners = verify_shard_layout(endpoints, collection, expected_points=count, api_key_env=args.api_key_env)
    print(json.dumps({
        "status": "uploaded", "collection": args.collection, "points": sent,
        "endpoint": base, "profile": args.profile,
        "indexed_vectors_count": final_result.get("indexed_vectors_count"),
        "optimizer_config": (final_result.get("config") or {}).get("optimizer_config"),
        "payload_schema": final_result.get("payload_schema") or {},
        "cluster_membership": cluster_membership,
        "shard_owners": shard_owners,
    }))


def parse_query_file(path: Path):
    np = require_numpy()
    if path.suffix.lower() == ".npy":
        rows = np.load(path, allow_pickle=False)
        vectors = np.asarray(rows, dtype=np.float32)
    else:
        raw = json.loads(path.read_text(encoding="utf-8")) if path.suffix.lower() == ".json" else None
        if isinstance(raw, dict) and raw.get("schema") == MANIFEST_SCHEMA:
            bodies = [json.loads(base64.b64decode(item)) for item in raw["request_bodies_base64"]]
            vectors = np.asarray([body["vector"]["vector"] for body in bodies], dtype=np.float32)
        elif raw is not None:
            rows = raw.get("queries", raw) if isinstance(raw, dict) else raw
            vectors = np.asarray(rows, dtype=np.float32)
        else:
            rows = []
            with path.open("r", encoding="utf-8") as stream:
                for line_no, line in enumerate(stream, 1):
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    if isinstance(row, dict) and "vector" in row:
                        row = row["vector"].get("vector", row["vector"]) if isinstance(row["vector"], dict) else row["vector"]
                    rows.append(row)
            vectors = np.asarray(rows, dtype=np.float32)
    if vectors.shape != (QUERY_COUNT, DIM):
        raise SystemExit(f"query input must contain shape ({QUERY_COUNT}, {DIM}); got {vectors.shape}")
    if not np.isfinite(vectors).all():
        raise SystemExit("query input contains NaN or infinite values")
    norms = np.linalg.norm(vectors, axis=1)
    if not np.allclose(norms, 1.0, rtol=0.0, atol=1e-4):
        raise SystemExit("query input must contain L2-normalized vectors (norm 1 within 1e-4)")
    return np.asarray(vectors, dtype="<f4", order="C")


def response_result(envelope, query_index, category, *, require_payload=True):
    result = envelope.get("result")
    if not isinstance(result, list) or len(result) != TOPK:
        raise RuntimeError(f"{category} query {query_index}: expected exactly {TOPK} result rows")
    hits = []
    seen = set()
    for rank, row in enumerate(result):
        if not isinstance(row, dict) or isinstance(row.get("id"), bool) or not isinstance(row.get("id"), int):
            raise RuntimeError(f"{category} query {query_index} rank {rank}: ID must be an integer")
        point_id = row["id"]
        score = row.get("score")
        if point_id < 0 or point_id >= MAX_POINTS or point_id in seen or isinstance(score, bool) or not isinstance(score, (float, int)) or not math.isfinite(score):
            raise RuntimeError(f"{category} query {query_index} rank {rank}: invalid ID or score")
        seen.add(point_id)
        actual_payload = row.get("payload")
        if require_payload and actual_payload != payload_for_id(point_id):
            raise RuntimeError(f"{category} query {query_index} rank {rank}: exact F32 truth payload does not match deterministic metadata")
        if actual_payload is not None and actual_payload != payload_for_id(point_id):
            raise RuntimeError(f"{category} query {query_index} rank {rank}: truth payload does not match deterministic metadata")
        hits.append({"id": point_id, "score": float(score)})
    for hit in hits:
        point_id = hit["id"]
        payload = payload_for_id(point_id)
        if category == "active90_payload" and not payload["abis"]["active"]:
            raise RuntimeError(f"{category} query {query_index}: exact truth includes inactive ID {point_id}")
        if category == "narrow9_payload" and (
            not payload["abis"]["active"]
            or payload["attributes"]["position"] != "left_index"
            or payload["abis"]["subject_id"] == "00000000-0000-4000-8000-000000000001"
        ):
            raise RuntimeError(f"{category} query {query_index}: exact truth includes ID {point_id} outside the narrow filter")
    return hits


def read_cached_truth(path: Path, category: str):
    rows = []
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            index = line_no - 1
            if isinstance(value, dict):
                if "query" in value:
                    index = int(value["query"])
                    if index != len(rows):
                        raise RuntimeError(f"cached truth {path} query indexes are not contiguous at {index}")
                value = value.get("exact_f32", value.get("result", value))
            if isinstance(value, list) and len(value) >= TOPK:
                # Historical independent captures retain 32 exact neighbors;
                # the standalone load client contract is exactly Top10.
                value = value[:TOPK]
            rows.append(response_result({"result": value}, index, category, require_payload=False))
    if len(rows) != QUERY_COUNT:
        raise RuntimeError(f"cached truth {path} must contain {QUERY_COUNT} rows, got {len(rows)}")
    return rows


def exact_body(query, category_filter):
    body = {
        "vector": {"name": "gallery", "vector": query.tolist()},
        "limit": TOPK,
        "with_payload": True,
        "with_vector": False,
        "params": {"exact": True, "quantization": {"ignore": True}},
    }
    if category_filter is not None:
        body["filter"] = category_filter
    return body


def measured_body(query, category_filter, with_payload, oversampling):
    body = {
        "vector": {"name": "gallery", "vector": query.tolist()},
        "limit": TOPK,
        "with_payload": with_payload,
        "with_vector": False,
        "params": {"exact": False, "quantization": {"rescore": True, "ignore": False, "oversampling": oversampling}},
    }
    if category_filter is not None:
        body["filter"] = category_filter
    return body


def cmd_prepare(args):
    np = require_numpy()
    try:
        candidate_params = profile_candidate_params(args.profile, args.candidate_count)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    queries = parse_query_file(Path(args.queries).resolve())
    base = validate_base_url(args.endpoint)
    collection = quote(args.collection, safe="")
    collection_url = endpoint_for(base, f"/collections/{collection}")
    collection_info = api_request(collection_url, "GET", api_key_env=args.api_key_env)
    collection_result = collection_info.get("result") or {}
    collection_config = collection_result.get("config") or {}
    point_count = collection_result.get("points_count")
    readiness_errors = optimizer_readiness_errors(collection_result, args.profile, expected_points=point_count)
    params = collection_config.get("params") or {}
    vectors = params.get("vectors") or {}
    vector_config = vectors.get("gallery") if isinstance(vectors, dict) else None
    hnsw = collection_config.get("hnsw_config") or {}
    if not isinstance(vector_config, dict) or vector_config.get("size") != DIM or vector_config.get("distance") != "Cosine":
        readiness_errors.append("collection vector gallery must be 512D Cosine")
    if params.get("replication_factor") != 1:
        readiness_errors.append(f"replication_factor is {params.get('replication_factor')!r}, expected 1")
    if hnsw.get("m") != 0 or hnsw.get("payload_m") != 0:
        readiness_errors.append("collection HNSW config must use m=0 and payload_m=0")
    if readiness_errors:
        raise SystemExit("collection is not benchmark-ready: " + "; ".join(readiness_errors))
    search_url = endpoint_for(base, f"/collections/{collection}/points/search")
    out = Path(args.out).resolve()
    truth_dir = out / "truth"
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"refusing to overwrite existing manifests or truth in {out}; choose a new --out directory")
    out.mkdir(parents=True, exist_ok=True)
    truth_dir.mkdir(exist_ok=True)
    query_hash = hashlib.sha256(queries.tobytes(order="C")).hexdigest()
    cache_dir = Path(args.cached_truth_dir).resolve() if args.cached_truth_dir else None
    truths = {}
    truth_hashes = {}

    # One exact search set per predicate. nf_false intentionally reuses the
    # same unfiltered exact truth as nf_true; only its measured body differs.
    truth_for_filter = {}
    for category, spec in CATEGORIES.items():
        filter_key = compact_json(spec["filter"]).decode("utf-8")
        if filter_key not in truth_for_filter:
            cache_path = None
            if cache_dir:
                cache_path = next((cache_dir / candidate for candidate in LEGACY_TRUTH_FILES[category]
                                   if (cache_dir / candidate).exists()), None)
                if cache_path is None and spec["filter"] is None:
                    alternate = "nf_true" if category == "nf_false" else "nf_false"
                    cache_path = next((cache_dir / candidate for candidate in LEGACY_TRUTH_FILES[alternate]
                                       if (cache_dir / candidate).exists()), None)
            if cache_path is not None:
                hits_by_query = read_cached_truth(cache_path, category)
                truth_source = f"cached:{cache_path.name}"
            else:
                hits_by_query = []
                for index, query in enumerate(queries):
                    body = exact_body(query, spec["filter"])
                    envelope = api_request(search_url, "POST", body=body, api_key_env=args.api_key_env, timeout=args.timeout)
                    if envelope.get("status") != "ok":
                        raise RuntimeError(f"exact truth query {index} returned status {envelope.get('status')!r}")
                    hits_by_query.append(response_result(envelope, index, category))
                    if (index + 1) % 64 == 0:
                        print(f"exact truth {category}: {index + 1}/{QUERY_COUNT}", file=sys.stderr, flush=True)
                truth_source = "native Qdrant exact FP32 search (exact=true, quantization.ignore=true)"
            cache_output = truth_dir / f"{category}.jsonl"
            with cache_output.open("w", encoding="utf-8", newline="\n") as stream:
                for hits in hits_by_query:
                    stream.write(json.dumps(hits, separators=(",", ":"), allow_nan=False) + "\n")
            truth_for_filter[filter_key] = (hits_by_query, truth_source, hashlib.sha256(cache_output.read_bytes()).hexdigest())

    for category, spec in CATEGORIES.items():
        filter_key = compact_json(spec["filter"]).decode("utf-8")
        hits_by_query, truth_source, truth_sha = truth_for_filter[filter_key]
        truths[category] = hits_by_query
        truth_hashes[category] = truth_sha
        bodies = [measured_body(query, spec["filter"], spec["with_payload"], candidate_params["oversampling"]) for query in queries]
        selected = [{"metadata_sha256": metadata_digest(hits)} for hits in hits_by_query]
        manifest = {
            "schema": MANIFEST_SCHEMA,
            "endpoint": f"{search_url}?consistency=quorum",
            "query_count": QUERY_COUNT,
            "result_limit": TOPK,
            "with_payload": spec["with_payload"],
            "request_bodies_base64": [base64.b64encode(compact_json(body)).decode("ascii") for body in bodies],
            "candidate_truth": hits_by_query,
            "expected_selected": selected,
            "pins": {
                "protocol": "stock Qdrant REST search, one request per query, Top10",
                "query_count": QUERY_COUNT,
                "result_limit": TOPK,
                "with_payload": spec["with_payload"],
                "filter": spec["filter"],
                "category": category,
                "profile": candidate_params["profile"],
                "candidate_count_per_segment": candidate_params["candidate_count_per_segment"],
                "default_candidate_count_per_segment": candidate_params["default_candidate_count_per_segment"],
                "candidate_count_source": candidate_params["candidate_count_source"],
                "oversampling": candidate_params["oversampling"],
                "query_vectors_sha256_f32le": query_hash,
                "query_source": str(Path(args.queries).resolve()),
                "truth_source": truth_source,
                "truth_jsonl_sha256": truth_sha,
                "truth_params": {"exact": True, "quantization": {"ignore": True}},
                "collection": args.collection,
                "collection_points_count": point_count,
                "indexed_vectors_count": collection_result.get("indexed_vectors_count"),
                "collection_status": collection_result.get("status"),
                "optimizer_status": collection_result.get("optimizer_status"),
                "optimizer_config": collection_config.get("optimizer_config"),
                "payload_schema": collection_result.get("payload_schema"),
                "vector_name": "gallery",
                "timed_params": {"exact": False, "quantization": {"rescore": True, "ignore": False, "oversampling": candidate_params["oversampling"]}},
            },
        }
        target = out / f"{category}.json"
        target.write_text(json.dumps(manifest, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
        print(f"wrote {target} (truth source: {truth_source})", file=sys.stderr)
    print(json.dumps({"status": "prepared", "manifests": [str(out / f"{name}.json") for name in CATEGORIES], "query_vectors_sha256_f32le": query_hash}, indent=2))


def percentile_field(report, field, percentile):
    value = report.get(field, {})
    return value.get(f"p{percentile}_ms") if isinstance(value, dict) else None


def run_one(args, manifest: Path, output: Path, concurrency: int, seconds: float):
    command = [
        str(Path(args.bench).resolve()),
        "--manifest", str(manifest.resolve()),
        "--output", str(output.resolve()),
        "--mode", "closed-loop",
        "--concurrency", str(concurrency),
        "--max-inflight", str(concurrency),
        "--seconds", str(seconds),
        "--timeout", args.timeout,
        "--api-key-env", args.api_key_env,
        "--gomaxprocs", str(args.gomaxprocs),
        "--warmup-requests", str(args.warmup_requests),
    ]
    print("+ " + " ".join(command), file=sys.stderr, flush=True)
    try:
        completed = subprocess.run(command, check=False)
        exit_code = completed.returncode
    except OSError as exc:
        return {}, None, f"could not start load generator: {exc}"
    if not output.is_file():
        return {}, exit_code, f"load generator exited {exit_code} without writing {output}"
    try:
        report = json.loads(output.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, exit_code, f"load generator report is unreadable: {exc}"
    return report, exit_code, None


def cmd_run(args):
    bench = Path(args.bench)
    if not bench.is_file():
        raise SystemExit(f"Go load generator not found: {bench}; build with `go build -o reproduce/bench ./reproduce/bench.go`")
    manifest_dir = Path(args.manifest_dir).resolve()
    out = Path(args.out).resolve()
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"refusing to overwrite existing results in {out}; choose a new --out directory")
    out.mkdir(parents=True, exist_ok=True)
    concurrencies = [int(value) for value in args.concurrency.split(",") if value.strip()]
    if not concurrencies or any(value < 1 or value > 160 for value in concurrencies):
        raise SystemExit("--concurrency must be a comma-separated list of integers in 1..160")
    missing = [name for name in CATEGORIES if not (manifest_dir / f"{name}.json").is_file()]
    if missing:
        raise SystemExit(f"manifest directory is missing required categories: {', '.join(missing)}")
    manifest_identity = None
    manifest_documents = {}
    canonical_queries = None
    for category in CATEGORIES:
        path = manifest_dir / f"{category}.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        pins = document.get("pins") or {}
        profile = pins.get("profile")
        if profile not in PROFILE_SETTINGS:
            raise SystemExit(f"{path} does not pin a supported quantization profile")
        try:
            candidate = profile_candidate_params(profile, pins.get("candidate_count_per_segment"))
        except ValueError as exc:
            raise SystemExit(f"{path}: {exc}") from exc
        if pins.get("category") != category:
            raise SystemExit(f"{path} does not pin category {category}")
        if document.get("with_payload") is not CATEGORIES[category]["with_payload"]:
            raise SystemExit(f"{path} payload mode does not match category {category}")
        if pins.get("candidate_count_source") not in ("historical_sufficient_cap", "explicit_override"):
            raise SystemExit(f"{path} does not record the candidate cap source")
        if (pins.get("candidate_count_source") == "historical_sufficient_cap"
                and candidate["candidate_count_per_segment"] != candidate["default_candidate_count_per_segment"]):
            raise SystemExit(f"{path} labels a nondefault candidate cap as historical")
        oversampling = pins.get("oversampling")
        if not isinstance(oversampling, (int, float)) or not math.isclose(
            float(oversampling), candidate["oversampling"], rel_tol=0.0, abs_tol=1e-12
        ):
            raise SystemExit(f"{path} has inconsistent candidate count and oversampling pins")
        timed_quantization = (pins.get("timed_params") or {}).get("quantization") or {}
        if not math.isclose(float(timed_quantization.get("oversampling", -1)), candidate["oversampling"],
                            rel_tol=0.0, abs_tol=1e-12):
            raise SystemExit(f"{path} timed_params oversampling disagrees with its pins")
        bodies = document.get("request_bodies_base64") or []
        if len(bodies) != QUERY_COUNT:
            raise SystemExit(f"{path} must contain exactly {QUERY_COUNT} timed requests")
        query_digest = hashlib.sha256()
        category_queries = []
        for index, encoded in enumerate(bodies):
            body = json.loads(base64.b64decode(encoded))
            query = body.get("vector", {}).get("vector")
            if not isinstance(query, list) or len(query) != DIM:
                raise SystemExit(f"{path} request {index} does not contain a {DIM}D vector")
            try:
                query_digest.update(struct.pack(f"<{DIM}f", *(float(value) for value in query)))
            except (OverflowError, TypeError, ValueError, struct.error) as exc:
                raise SystemExit(f"{path} request {index} contains an invalid query vector") from exc
            category_queries.append(query)
            body_quantization = ((body.get("params") or {}).get("quantization") or {})
            if not math.isclose(float(body_quantization.get("oversampling", -1)), candidate["oversampling"],
                                rel_tol=0.0, abs_tol=1e-12):
                raise SystemExit(f"{path} request {index} oversampling disagrees with its pins")
        pinned_query_hash = pins.get("query_vectors_sha256_f32le")
        if query_digest.hexdigest() != pinned_query_hash:
            raise SystemExit(f"{path} query vectors do not match their SHA-256 pin")
        if canonical_queries is None:
            canonical_queries = category_queries
        elif category_queries != canonical_queries:
            raise SystemExit("all four manifests must use the same ordered query vectors")
        identity = (profile, candidate["candidate_count_per_segment"], candidate["oversampling"],
                    pins.get("query_vectors_sha256_f32le"), pins.get("candidate_count_source"))
        if manifest_identity is None:
            manifest_identity = identity
        elif identity != manifest_identity:
            raise SystemExit("all four manifests must use the same profile, cap, oversampling, and query vectors")
        manifest_documents[category] = document
    if manifest_documents["nf_false"].get("candidate_truth") != manifest_documents["nf_true"].get("candidate_truth"):
        raise SystemExit("nf_false and nf_true must share the same exact Top10 truth")
    summary = {
        "schema": "qdrant_stock_benchmark_run_summary_v1",
        "profile": manifest_identity[0],
        "candidate_count_per_segment": manifest_identity[1],
        "oversampling": manifest_identity[2],
        "candidate_count_source": manifest_identity[4],
        "run_mode": "closed-loop; B1; HTTP/1.1; Go warm-up requests complete before each timed dispatch window",
        "measured_seconds": args.seconds,
        "warmup_requests_per_run": args.warmup_requests,
        "concurrency": concurrencies,
        "gomaxprocs": args.gomaxprocs,
        "runs": [],
    }
    # The copied Go validator has a deliberately offline preflight mode. It
    # validates all 1,024 bodies, Top10 truth rows, pins and metadata digests
    # without reading the API key or contacting the endpoint.
    for category in CATEGORIES:
        manifest = manifest_dir / f"{category}.json"
        preflight_path = out / f"{category}-preflight.json"
        command = [
            str(bench.resolve()), "--manifest", str(manifest),
            "--validate-manifest-only", "--output", str(preflight_path),
        ]
        print("+ " + " ".join(command), file=sys.stderr, flush=True)
        subprocess.run(command, check=True)
        preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
        if preflight.get("status") != "VALIDATED":
            raise RuntimeError(f"offline manifest preflight failed for {category}")
    for category in CATEGORIES:
        manifest = manifest_dir / f"{category}.json"
        for concurrency in concurrencies:
            stem = f"{category}-C{concurrency}"
            report_path = out / f"{stem}-{args.seconds:g}s.json"
            report, exit_code, runner_error = run_one(args, manifest, report_path, concurrency, args.seconds)
            successful = report.get("successful_requests")
            candidate_matches = report.get("exact_candidate_truth_matches")
            payload_matches = report.get("exact_payload_contract_matches")
            metadata_matches = report.get("exact_metadata_hash_matches")
            failed = report.get("failed_requests")
            capacity_rejections = report.get("client_capacity_rejections")
            warmup_requests = report.get("warmup_requests")
            warmup_successes = report.get("warmup_successes")
            passed = (
                runner_error is None
                and exit_code == 0
                and failed == 0
                and capacity_rejections == 0
                and warmup_requests == args.warmup_requests
                and warmup_successes == warmup_requests
                and successful == candidate_matches
                and successful == payload_matches
                and (not CATEGORIES[category]["with_payload"] or successful == metadata_matches)
            )
            summary["runs"].append({
                "category": category,
                "concurrency": concurrency,
                "profile": manifest_identity[0],
                "candidate_count_per_segment": manifest_identity[1],
                "oversampling": manifest_identity[2],
                "passed": passed,
                "status": "PASSED" if passed else "COMPLETED_WITH_FAILURES",
                "go_exit_code": exit_code,
                "runner_error": runner_error,
                "report": str(report_path),
                "actual_elapsed_s": report.get("actual_elapsed_s"),
                "actual_dispatch_duration_s": report.get("actual_dispatch_duration_s"),
                "drain_duration_s": report.get("drain_duration_s"),
                "throughput_basis": report.get("throughput_basis"),
                "successful_completed_http_rps": report.get("successful_completed_http_rps"),
                "all_http_responses_per_s": report.get("all_http_responses_per_s"),
                "planned_requests": report.get("planned_requests"),
                "dispatched_requests": report.get("dispatched_requests"),
                "http_responses": report.get("http_responses"),
                "successful_requests": report.get("successful_requests"),
                "failed_requests": report.get("failed_requests"),
                "client_capacity_rejections": report.get("client_capacity_rejections"),
                "transport_timeouts": report.get("transport_timeouts"),
                "http_failure_requests": report.get("http_failure_requests"),
                "transport_failures": report.get("transport_failures"),
                "exact_candidate_truth_matches": report.get("exact_candidate_truth_matches"),
                "exact_payload_contract_matches": report.get("exact_payload_contract_matches"),
                "exact_metadata_hash_matches": report.get("exact_metadata_hash_matches"),
                "warmup_requests": report.get("warmup_requests"),
                "warmup_successes": report.get("warmup_successes"),
                "failure_counts": report.get("failure_counts"),
                "p50_ms": percentile_field(report, "successful_full_response_validated_latency_ms", 50),
                "p95_ms": percentile_field(report, "successful_full_response_validated_latency_ms", 95),
                "p99_ms": percentile_field(report, "successful_full_response_validated_latency_ms", 99),
            })
            print(json.dumps(summary["runs"][-1], sort_keys=True), flush=True)
    summary["passed"] = all(row["passed"] for row in summary["runs"])
    summary["status"] = "PASSED" if summary["passed"] else "COMPLETED_WITH_FAILURES"
    summary_path = out / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": summary["status"], "passed": summary["passed"],
                      "summary": str(summary_path), "runs": len(summary["runs"])}, indent=2))
    if not summary["passed"]:
        raise SystemExit(2)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    generate = sub.add_parser("generate", help="make one seeded normalized-FP32 gallery, full metadata, and 1,024 query vectors")
    generate.add_argument("--out", default="reproduce-data")
    generate.add_argument("--points", type=int, default=MAX_POINTS)
    generate.add_argument("--dimension", type=int, default=DIM)
    generate.add_argument("--queries", type=int, default=QUERY_COUNT)
    generate.add_argument("--seed", type=int, default=20261109)
    generate.add_argument("--batch-size", type=int, default=8192)
    generate.add_argument("--force", action="store_true")
    generate.set_defaults(func=cmd_generate)

    load = sub.add_parser("load", help="upload generated points to a stock Qdrant collection")
    load.add_argument("--data-dir", default="reproduce-data")
    load.add_argument("--endpoint", default="http://127.0.0.1:6333")
    load.add_argument("--collection", default="native120_sq8_3m")
    load.add_argument("--profile", choices=tuple(PROFILE_SETTINGS), default="sq8",
                      help="quantization config to create or require: sq8, tq2, or tq4")
    load.add_argument("--peer-endpoints", default="http://127.0.0.1:6333,http://127.0.0.1:6334,http://127.0.0.1:6335",
                      help="comma-separated HTTP endpoints for all 3 peers; used to verify each shard has one active RF1 owner")
    load.add_argument("--create", action="store_true", help="create an empty collection with 3 shards, RF1, m=0, payload_m=0, and the selected profile")
    load.add_argument("--batch-size", type=int, default=128)
    load.add_argument("--timeout", type=int, default=120)
    load.add_argument("--readiness-timeout", type=float, default=3600,
                      help="preparation-only timeout for indexing/quantization readiness; not a latency SLA")
    load.add_argument("--poll-interval", type=float, default=5,
                      help="seconds between collection readiness checks")
    load.add_argument("--api-key-env", default="QDRANT_API_KEY")
    load.set_defaults(func=cmd_load)

    prepare = sub.add_parser("prepare-manifests", help="capture native exact FP32 truth and build timed stock Go manifests")
    prepare.add_argument("--queries", default="reproduce-data/queries.npy", help=".npy, JSON/JSONL vectors, or a cached Go manifest")
    prepare.add_argument("--endpoint", default="http://127.0.0.1:6333")
    prepare.add_argument("--collection", default="native120_sq8_3m")
    prepare.add_argument("--profile", choices=tuple(PROFILE_SETTINGS), default="sq8",
                         help="quantization profile already configured on the collection")
    prepare.add_argument("--candidate-count", type=int,
                         help="override the historical sufficient per-segment candidate count (integer >= 10)")
    prepare.add_argument("--out", default="reproduce-manifests")
    prepare.add_argument("--cached-truth-dir", help="optional category JSONL from a matching exact-FP32 corpus/query fixture")
    prepare.add_argument("--timeout", type=int, default=120)
    prepare.add_argument("--api-key-env", default="QDRANT_API_KEY")
    prepare.set_defaults(func=cmd_prepare)

    run = sub.add_parser("run", help="execute warm-up and measured C1/C160 (or chosen) category passes")
    run.add_argument("--manifest-dir", default="reproduce-manifests")
    run.add_argument("--bench", default="reproduce/bench")
    run.add_argument("--out", default="reproduce-results")
    run.add_argument("--concurrency", default="1,160")
    run.add_argument("--seconds", type=float, default=60)
    run.add_argument("--warmup-requests", type=int, default=16)
    run.add_argument("--timeout", default="30s")
    run.add_argument("--gomaxprocs", type=int, default=7)
    run.add_argument("--api-key-env", default="QDRANT_API_KEY")
    run.set_defaults(func=cmd_run)

    args = parser.parse_args()
    try:
        args.func(args)
    except (ValueError, RuntimeError, OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()

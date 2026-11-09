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
import sys
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
    data_dir = Path(args.data_dir).resolve()
    dataset = json.loads((data_dir / "dataset.json").read_text(encoding="utf-8"))
    count = int(dataset["points"])
    dimension = int(dataset["dimension"])
    if dataset.get("schema") != "qdrant_stock_sq8_synthetic_dataset_v1" or count < TOPK or count > MAX_POINTS or dimension != DIM:
        raise SystemExit("dataset.json does not match the supported normalized 512D workload schema")
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
    if args.create:
        create_body = {
            "vectors": {"gallery": {"size": dimension, "distance": "Cosine"}},
            "shard_number": 3,
            "replication_factor": 1,
            "hnsw_config": {"m": 0, "payload_m": 0},
            "quantization_config": {"scalar": {"type": "int8", "quantile": 1.0, "always_ram": True}},
        }
        result = api_request(collection_url + "?wait=true", "PUT", body=create_body, api_key_env=args.api_key_env)
        print(f"collection creation: {result}", file=sys.stderr)
    collection_info = api_request(collection_url, "GET", api_key_env=args.api_key_env)
    config = (collection_info.get("result") or {}).get("config") or {}
    params = config.get("params") or {}
    vectors = params.get("vectors") or {}
    vector_config = vectors.get("gallery") if isinstance(vectors, dict) else None
    hnsw = config.get("hnsw_config") or {}
    quantization = config.get("quantization_config") or {}
    scalar = quantization.get("scalar") or {}
    expected = (
        isinstance(vector_config, dict)
        and vector_config.get("size") == dimension
        and vector_config.get("distance") == "Cosine"
        and params.get("shard_number") == 3
        and params.get("replication_factor") == 1
        and hnsw.get("m") == 0 and hnsw.get("payload_m") == 0
        and scalar.get("type") == "int8" and scalar.get("quantile") == 1.0
        and scalar.get("always_ram") is True
    )
    if not expected:
        raise SystemExit("collection config does not match named gallery/512/Cosine, 3 shards/RF1, m=0/payload_m=0, scalar int8 quantile=1 always_ram=true")
    if (collection_info.get("result") or {}).get("payload_schema"):
        raise SystemExit("collection has indexed payload fields; this workload requires payload presence without payload indexes")
    starting_points = (collection_info.get("result") or {}).get("points_count")
    if not isinstance(starting_points, int) or starting_points > count:
        raise SystemExit(f"collection starts with {starting_points!r} points; expected an empty or partial collection with at most {count}")

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
    final_info = api_request(collection_url, "GET", api_key_env=args.api_key_env)
    final_result = final_info.get("result") or {}
    if final_result.get("status") != "green" or final_result.get("points_count") != count:
        raise RuntimeError(
            f"collection did not finish green with exactly {count} points: "
            f"status={final_result.get('status')!r}, points_count={final_result.get('points_count')!r}"
        )
    if final_result.get("payload_schema"):
        raise RuntimeError("payload schema became non-empty; a payload index exists")
    endpoints = [value.strip() for value in args.peer_endpoints.split(",") if value.strip()]
    shard_owners = verify_shard_layout(endpoints, collection, expected_points=count, api_key_env=args.api_key_env)
    print(json.dumps({
        "status": "uploaded", "collection": args.collection, "points": sent,
        "endpoint": base, "payload_schema": final_result.get("payload_schema") or {},
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


def measured_body(query, category_filter, with_payload):
    body = {
        "vector": {"name": "gallery", "vector": query.tolist()},
        "limit": TOPK,
        "with_payload": with_payload,
        "with_vector": False,
        "params": {"exact": False, "quantization": {"rescore": True, "ignore": False}},
    }
    if category_filter is not None:
        body["filter"] = category_filter
    return body


def cmd_prepare(args):
    np = require_numpy()
    queries = parse_query_file(Path(args.queries).resolve())
    base = validate_base_url(args.endpoint)
    collection = quote(args.collection, safe="")
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
        bodies = [measured_body(query, spec["filter"], spec["with_payload"]) for query in queries]
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
                "query_vectors_sha256_f32le": query_hash,
                "query_source": str(Path(args.queries).resolve()),
                "truth_source": truth_source,
                "truth_jsonl_sha256": truth_sha,
                "truth_params": {"exact": True, "quantization": {"ignore": True}},
                "collection": args.collection,
                "vector_name": "gallery",
                "timed_params": {"exact": False, "quantization": {"rescore": True, "ignore": False}},
            },
        }
        target = out / f"{category}.json"
        target.write_text(json.dumps(manifest, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
        print(f"wrote {target} (truth source: {truth_source})", file=sys.stderr)
    print(json.dumps({"status": "prepared", "manifests": [str(out / f"{name}.json") for name in CATEGORIES], "query_vectors_sha256_f32le": query_hash}, indent=2))


def percentile_field(report, field, percentile):
    value = report.get(field, {})
    return value.get(f"p{percentile}_ms") if isinstance(value, dict) else None


def run_one(args, manifest: Path, output: Path, concurrency: int, seconds: float, *, allow_errors=False):
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
    completed = subprocess.run(command, check=False)
    if not output.is_file():
        raise RuntimeError(f"load generator exited {completed.returncode} without writing {output}")
    if completed.returncode and not allow_errors:
        raise RuntimeError(f"load generator exited {completed.returncode}; see {output}")
    return json.loads(output.read_text(encoding="utf-8"))


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
    summary = {
        "schema": "qdrant_stock_sq8_benchmark_run_summary_v1",
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
            report = run_one(args, manifest, report_path, concurrency, args.seconds, allow_errors=True)
            summary["runs"].append({
                "category": category,
                "concurrency": concurrency,
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
    summary_path = out / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": "complete", "summary": str(summary_path), "runs": len(summary["runs"])}, indent=2))


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
    load.add_argument("--peer-endpoints", default="http://127.0.0.1:6333,http://127.0.0.1:6334,http://127.0.0.1:6335",
                      help="comma-separated HTTP endpoints for all 3 peers; used to verify each shard has one active RF1 owner")
    load.add_argument("--create", action="store_true", help="create the collection with 3 shards, RF1, m=0, payload_m=0, scalar SQ8")
    load.add_argument("--batch-size", type=int, default=128)
    load.add_argument("--timeout", type=int, default=120)
    load.add_argument("--api-key-env", default="QDRANT_API_KEY")
    load.set_defaults(func=cmd_load)

    prepare = sub.add_parser("prepare-manifests", help="capture native exact FP32 truth and build timed SQ8 Go manifests")
    prepare.add_argument("--queries", default="reproduce-data/queries.npy", help=".npy, JSON/JSONL vectors, or a cached Go manifest")
    prepare.add_argument("--endpoint", default="http://127.0.0.1:6333")
    prepare.add_argument("--collection", default="native120_sq8_3m")
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

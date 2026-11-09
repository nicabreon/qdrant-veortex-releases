#!/usr/bin/env python3
"""Run one already-started engine arm through the shared batch-search matrix.

The wrapper validates every frozen manifest offline before sending any timed
request. It does not manage Docker, collection lifecycle, or engine switching.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
CATEGORIES = (
    "unfiltered_no_payload",
    "unfiltered_payload",
    "active_only",
    "active_position_exclude",
)

# workload.py uses the short historical names. The canonical names are also
# accepted for manifest directories prepared by the paired-run workflow.
MANIFEST_NAMES = {
    "unfiltered_no_payload": (
        "nf_false.json",
        "unfiltered_no_payload-manifest.json",
        "unfiltered_no_payload.json",
    ),
    "unfiltered_payload": (
        "nf_true.json",
        "unfiltered_payload-manifest.json",
        "unfiltered_payload.json",
    ),
    "active_only": (
        "active90_payload.json",
        "active_only-manifest.json",
        "active_only.json",
    ),
    "active_position_exclude": (
        "narrow9_payload.json",
        "active_position_exclude-manifest.json",
        "active_position_exclude.json",
    ),
}
PIN_CATEGORY_ALIASES = {
    "unfiltered_no_payload": {"unfiltered_no_payload", "nf_false"},
    "unfiltered_payload": {"unfiltered_payload", "nf_true"},
    "active_only": {"active_only", "active90_payload"},
    "active_position_exclude": {"active_position_exclude", "narrow9_payload"},
}
WITH_PAYLOAD = {
    "unfiltered_no_payload": False,
    "unfiltered_payload": True,
    "active_only": True,
    "active_position_exclude": True,
}
MATRIX_CELLS = (
    (1, 1),
    (1, 4),
    (1, 32),
    (1, 64),
    (1, 128),
    (1, 160),
    (4, 4),
    (16, 4),
    (32, 4),
    (64, 4),
)
MANIFEST_SCHEMA = "benchmark_abis_payload_b1_top10_go_manifest_v1"
VALIDATION_SCHEMA = "qdrant_search_batch_manifest_validation_v1"
RESULT_SCHEMA = "qdrant_search_batch_matrix_http_v1"


class RunnerError(Exception):
    pass


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", errors="replace")


def parse_batch_sizes(value: str) -> tuple[int, ...]:
    try:
        values = {int(piece.strip()) for piece in value.split(",") if piece.strip()}
    except ValueError as exc:
        raise argparse.ArgumentTypeError("batch sizes must be comma-separated integers") from exc
    allowed = {cell[0] for cell in MATRIX_CELLS}
    if not values or values - allowed:
        raise argparse.ArgumentTypeError("batch sizes must be selected from 1,4,16,32,64")
    return tuple(batch for batch in (1, 4, 16, 32, 64) if batch in values)


def parse_timeout(value: str) -> str:
    pattern = re.compile(r"(?:\d+(?:\.\d+)?(?:ns|us|µs|ms|s|m|h))+")
    if not pattern.fullmatch(value):
        raise argparse.ArgumentTypeError("timeout must be a positive Go duration such as 60s or 1m")
    unit_seconds = {"ns": 1e-9, "us": 1e-6, "µs": 1e-6, "ms": 1e-3, "s": 1, "m": 60, "h": 3600}
    seconds = 0.0
    for amount, unit in re.findall(r"(\d+(?:\.\d+)?)(ns|us|µs|ms|s|m|h)", value):
        seconds += float(amount) * unit_seconds[unit]
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("timeout must be positive")
    return value


def parse_cpu_list(value: str | None) -> str | None:
    if value is None:
        return None
    if not re.fullmatch(r"\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*", value):
        raise argparse.ArgumentTypeError("client CPUs must use taskset list syntax, for example 2,4-6")
    return value


def manifest_path_for(directory: Path, category: str) -> Path:
    for name in MANIFEST_NAMES[category]:
        candidate = directory / name
        if candidate.is_file():
            return candidate
    names = ", ".join(MANIFEST_NAMES[category])
    raise RunnerError(f"missing {category} manifest; expected one of: {names}")


def expected_category(document: dict[str, Any]) -> str | None:
    payload = document.get("with_payload")
    if not isinstance(payload, bool):
        return None
    body = document.get("request_bodies_base64")
    if not isinstance(body, list) or not body:
        return None
    import base64

    try:
        first = json.loads(base64.b64decode(body[0], validate=True))
    except (ValueError, TypeError, json.JSONDecodeError):
        return None
    if not isinstance(first, dict):
        return None
    filt = first.get("filter")
    if filt is None:
        return "unfiltered_payload" if payload else "unfiltered_no_payload"
    if not isinstance(filt, dict):
        return None
    must = filt.get("must", [])
    must_not = filt.get("must_not", [])
    def matches(clause: Any, key: str, value: Any) -> bool:
        if not isinstance(clause, dict):
            return False
        match = clause.get("match")
        return clause.get("key") == key and isinstance(match, dict) and match.get("value") == value

    active = any(matches(clause, "abis.active", True) for clause in must) if isinstance(must, list) else False
    position = any(matches(clause, "attributes.position", "left_index") for clause in must) if isinstance(must, list) else False
    excludes_subject = any(
        matches(clause, "abis.subject_id", "00000000-0000-4000-8000-000000000001")
        for clause in must_not
    ) if isinstance(must_not, list) else False
    if active and position and excludes_subject and payload:
        return "active_position_exclude"
    if active and not position and not must_not and payload:
        return "active_only"
    return None


def decoded_query_vectors(document: dict[str, Any], path: Path) -> list[list[Any]]:
    import base64

    bodies = document.get("request_bodies_base64")
    if not isinstance(bodies, list) or len(bodies) != 1024:
        raise RunnerError(f"{path}: expected exactly 1,024 request bodies")
    vectors: list[list[Any]] = []
    for index, encoded in enumerate(bodies):
        try:
            body = json.loads(base64.b64decode(encoded, validate=True))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            raise RunnerError(f"{path}: request body {index} is not valid base64 JSON") from exc
        if not isinstance(body, dict):
            raise RunnerError(f"{path}: request body {index} is not a JSON object")
        vector = body.get("vector")
        values = vector.get("vector") if isinstance(vector, dict) else None
        if not isinstance(values, list) or len(values) != 512:
            raise RunnerError(f"{path}: request body {index} does not contain a 512D named vector")
        vectors.append(values)
    return vectors


def inspect_manifests(directory: Path) -> tuple[dict[str, Path], dict[str, str], list[str]]:
    paths: dict[str, Path] = {}
    hashes: dict[str, str] = {}
    documents: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for category in CATEGORIES:
        try:
            path = manifest_path_for(directory, category)
            paths[category] = path
            hashes[category] = sha256_file(path)
            document = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(document, dict) or document.get("schema") != MANIFEST_SCHEMA:
                raise RunnerError(f"{path}: unexpected manifest schema")
            if document.get("query_count") != 1024 or document.get("result_limit") != 10:
                raise RunnerError(f"{path}: expected 1,024 queries and Top10")
            if document.get("with_payload") is not WITH_PAYLOAD[category]:
                raise RunnerError(f"{path}: payload mode does not match {category}")
            if expected_category(document) != category:
                raise RunnerError(f"{path}: request filter does not match {category}")
            pins = document.get("pins") or {}
            pinned_category = pins.get("category") if isinstance(pins, dict) else None
            if pinned_category is not None and (
                not isinstance(pinned_category, str)
                or pinned_category not in PIN_CATEGORY_ALIASES[category]
            ):
                raise RunnerError(f"{path}: pinned category {pinned_category!r} does not match {category}")
            endpoint = document.get("endpoint")
            if not isinstance(endpoint, str) or not endpoint:
                raise RunnerError(f"{path}: missing endpoint")
            documents[category] = document
        except (OSError, UnicodeError, json.JSONDecodeError, RunnerError) as exc:
            errors.append(str(exc))

    if len(documents) == len(CATEGORIES):
        endpoints = {document.get("endpoint") for document in documents.values()}
        if len(endpoints) != 1:
            errors.append("the four manifests must use the same endpoint and collection")
        all_vectors: dict[str, list[list[Any]]] = {}
        for category, document in documents.items():
            try:
                all_vectors[category] = decoded_query_vectors(document, paths[category])
            except RunnerError as exc:
                errors.append(str(exc))
        if len(all_vectors) == len(CATEGORIES):
            reference = all_vectors[CATEGORIES[0]]
            for category in CATEGORIES[1:]:
                if all_vectors[category] != reference:
                    errors.append(f"{category} does not use the same ordered query vectors")
                    break
        no_payload_truth = documents["unfiltered_no_payload"].get("candidate_truth")
        payload_truth = documents["unfiltered_payload"].get("candidate_truth")
        if no_payload_truth != payload_truth:
            errors.append("the two unfiltered manifests do not share identical ordered Top10 truth")
        for field in ("query_vectors_sha256_f32le", "query_sha256", "candidate_count_per_segment", "oversampling"):
            values = []
            for document in documents.values():
                pins = document.get("pins") or {}
                if isinstance(pins, dict) and field in pins:
                    values.append(pins[field])
            if values and any(value != values[0] for value in values[1:]):
                errors.append(f"manifest pins disagree on {field}")
    return paths, hashes, errors


def make_client_command(client: Path, taskset: str | None, args: list[str]) -> list[str]:
    if taskset:
        return ["taskset", "--cpu-list", taskset, str(client), *args]
    return [str(client), *args]


def run_process(command: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def report_is_valid(path: Path, expected_hash: str, expected_payload: bool) -> tuple[bool, dict[str, Any], str | None]:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, {}, f"validation report is missing or unreadable: {exc}"
    if not isinstance(report, dict):
        return False, {}, "validation report is not a JSON object"
    checks = {
        "schema": report.get("schema") == VALIDATION_SCHEMA,
        "status": report.get("status") == "VALIDATED",
        "manifest_sha256": report.get("manifest_sha256") == expected_hash,
        "query_count": report.get("query_count") == 1024,
        "result_limit": report.get("result_limit") == 10,
        "with_payload": report.get("with_payload") is expected_payload,
    }
    failed = [name for name, passed in checks.items() if not passed]
    return not failed, report, ("validation report mismatch: " + ", ".join(failed)) if failed else None


def planned_rows(batch_sizes: tuple[int, ...]) -> list[dict[str, Any]]:
    return [
        {"batch_size": batch, "concurrency": concurrency, "category": category}
        for batch, concurrency in MATRIX_CELLS if batch in batch_sizes
        for category in CATEGORIES
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest-dir", required=True, help="directory containing the four frozen B1 manifests")
    parser.add_argument("--client", default="./reproduce/bench-matrix", help="already-built shared bench-matrix executable")
    parser.add_argument("--client-source", default=str(SCRIPT_DIR / "cmd/bench-matrix/main.go"), help="Go source file whose hash will be recorded")
    parser.add_argument("--output", required=True, help="new, nonexistent output directory")
    parser.add_argument("--engine-label", required=True, choices=("native120", "veortex-v45", "veortex-v45.1"), help="label for this one already-running engine arm")
    parser.add_argument("--seconds", type=float, default=60, help="timed dispatch window per row (default: 60)")
    parser.add_argument("--warmup-requests", type=int, default=16, help="fully validated warm-up HTTP requests per row")
    parser.add_argument("--timeout", type=parse_timeout, default="60s", help="per-request timeout, including response body read")
    parser.add_argument("--gomaxprocs", type=int, default=7, help="Go runtime parallelism")
    parser.add_argument("--client-cpus", type=parse_cpu_list, help="optional taskset CPU list for the client process only")
    parser.add_argument("--batch-sizes", type=parse_batch_sizes, default=(1, 4, 16, 32, 64), help="optional comma-separated subset of the default matrix batch sizes")
    parser.add_argument("--plan-only", action="store_true", help="run offline manifest validation and save the matrix plan without API requests")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not math.isfinite(args.seconds) or args.seconds <= 0:
        raise RunnerError("--seconds must be positive and finite")
    if args.warmup_requests < 0 or args.warmup_requests > 256:
        raise RunnerError("--warmup-requests must be in 0..256")
    if args.gomaxprocs < 1 or args.gomaxprocs > 128:
        raise RunnerError("--gomaxprocs must be in 1..128")

    manifest_dir = Path(args.manifest_dir).expanduser().resolve()
    client = Path(args.client).expanduser().resolve()
    source = Path(args.client_source).expanduser().resolve()
    output = Path(os.path.abspath(os.path.expanduser(args.output)))
    if os.path.lexists(output):
        raise RunnerError(f"refusing to overwrite existing output path: {output}")
    if not manifest_dir.is_dir():
        raise RunnerError(f"manifest directory does not exist: {manifest_dir}")
    if not client.is_file() or not os.access(client, os.X_OK):
        raise RunnerError(f"client is missing or not executable: {client}")
    if not source.is_file():
        raise RunnerError(f"client source file is missing: {source}")
    if args.client_cpus and shutil.which("taskset") is None:
        raise RunnerError("--client-cpus requires taskset on PATH")

    paths, manifest_hashes, static_errors = inspect_manifests(manifest_dir)
    try:
        output.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise RunnerError(f"refusing to overwrite existing output path: {output}") from exc

    client_hash = sha256_file(client)
    source_hash = sha256_file(source)
    cells = planned_rows(args.batch_sizes)
    summary: dict[str, Any] = {
        "schema": "qdrant_search_batch_matrix_runner_v1",
        "status": "PREFLIGHT_RUNNING",
        "engine_label": args.engine_label,
        "started_utc": utc_now(),
        "finished_utc": None,
        "manifest_directory": str(manifest_dir),
        "client_path": str(client),
        "client_sha256": client_hash,
        "client_source_path": str(source),
        "client_source_sha256": source_hash,
        "client_cpus": args.client_cpus,
        "seconds": args.seconds,
        "warmup_requests": args.warmup_requests,
        "timeout": args.timeout,
        "gomaxprocs": args.gomaxprocs,
        "plan_only": args.plan_only,
        "manifest_errors": static_errors,
        "manifests": [],
        "preflights": [],
        "planned_cells": cells,
        "rows": [],
        "failures": [],
        "api_key_value_recorded": False,
    }
    if static_errors:
        summary["failures"].append({"stage": "manifest_inspection", "errors": static_errors})
    for category in CATEGORIES:
        entry: dict[str, Any] = {"category": category}
        path = paths.get(category)
        if path is not None:
            entry.update({"path": str(path), "sha256": manifest_hashes[category]})
        summary["manifests"].append(entry)

    def save() -> None:
        write_json(output / "summary.json", summary)

    save()
    preflight_env = os.environ.copy()
    preflight_env.pop("QDRANT_API_KEY", None)
    static_error_by_category = {
        category: [error for error in static_errors if category in error or (paths.get(category) and str(paths[category]) in error)]
        for category in CATEGORIES
    }
    # Run every available offline validator before the first timed row, even
    # when another category has already failed preflight.
    (output / "preflight").mkdir(parents=True, exist_ok=True)
    for category in CATEGORIES:
        path = paths.get(category)
        if path is None:
            summary["preflights"].append({"category": category, "status": "MISSING", "passed": False})
            continue
        report_path = output / "preflight" / f"{category}.json"
        stdout_path = output / "preflight" / f"{category}.stdout.txt"
        stderr_path = output / "preflight" / f"{category}.stderr.txt"
        command = make_client_command(client, args.client_cpus, [
            "--manifest", str(path), "--validate-manifest-only", "--output", str(report_path),
        ])
        try:
            completed = run_process(command, preflight_env)
            write_text(stdout_path, completed.stdout)
            write_text(stderr_path, completed.stderr)
            expected_hash = manifest_hashes[category]
            report_ok, report, report_error = report_is_valid(report_path, expected_hash, WITH_PAYLOAD[category])
            passed = completed.returncode == 0 and report_ok and not static_error_by_category[category]
            error_parts = []
            if completed.returncode != 0:
                error_parts.append(f"client exited {completed.returncode}")
            if report_error:
                error_parts.append(report_error)
            if static_error_by_category[category]:
                error_parts.extend(static_error_by_category[category])
            preflight = {
                "category": category,
                "manifest_sha256": expected_hash,
                "status": "VALIDATED" if passed else "FAILED",
                "passed": passed,
                "client_exit_code": completed.returncode,
                "report": str(report_path) if report_path.is_file() else None,
                "stdout": str(stdout_path),
                "stderr": str(stderr_path),
                "report_fields": report,
                "errors": error_parts,
            }
        except OSError as exc:
            preflight = {"category": category, "status": "FAILED", "passed": False, "errors": [str(exc)]}
        summary["preflights"].append(preflight)
        if not preflight.get("passed"):
            summary["failures"].append({"stage": "preflight", "category": category, "errors": preflight.get("errors", [])})
        save()

    if static_errors or len(summary["preflights"]) != len(CATEGORIES) or not all(row.get("passed") for row in summary["preflights"]):
        summary["status"] = "PREFLIGHT_FAILED"
        summary["finished_utc"] = utc_now()
        save()
        print(f"manifest preflight failed; no timed requests were sent (see {output / 'summary.json'})", file=sys.stderr)
        return 2

    write_json(output / "plan.json", {
        "schema": "qdrant_search_batch_matrix_plan_v1",
        "engine_label": args.engine_label,
        "client_sha256": client_hash,
        "client_source_sha256": source_hash,
        "manifests": summary["manifests"],
        "cells": cells,
        "cell_count": len(cells),
        "row_count": len(cells),
        "category_order": list(CATEGORIES),
        "timed_seconds_per_row": args.seconds,
        "warmup_requests_per_row": args.warmup_requests,
        "timeout": args.timeout,
        "gomaxprocs": args.gomaxprocs,
        "client_cpus": args.client_cpus,
        "plan_only": args.plan_only,
    })
    if args.plan_only:
        summary["status"] = "PLAN_VALIDATED"
        summary["finished_utc"] = utc_now()
        save()
        print(f"offline preflight passed; plan saved to {output / 'plan.json'}")
        return 0

    if not os.environ.get("QDRANT_API_KEY"):
        summary["status"] = "API_KEY_MISSING"
        summary["failures"].append({"stage": "startup", "error": "QDRANT_API_KEY is empty or unset; no timed requests were sent"})
        summary["finished_utc"] = utc_now()
        save()
        print("QDRANT_API_KEY is empty or unset; no timed requests were sent", file=sys.stderr)
        return 2

    timed_env = os.environ.copy()
    (output / "rows").mkdir(parents=True, exist_ok=True)
    for cell_index, cell in enumerate(cells, start=1):
        batch = cell["batch_size"]
        concurrency = cell["concurrency"]
        category = cell["category"]
        manifest = paths[category]
        stem = f"{cell_index:02d}-{category}-B{batch}-C{concurrency}"
        report_path = output / "rows" / f"{stem}.json"
        stdout_path = output / "rows" / f"{stem}.stdout.txt"
        stderr_path = output / "rows" / f"{stem}.stderr.txt"
        command = make_client_command(client, args.client_cpus, [
            "--manifest", str(manifest),
            "--output", str(report_path),
            "--mode", "closed-loop",
            "--concurrency", str(concurrency),
            "--max-inflight", str(concurrency),
            "--batch-size", str(batch),
            "--seconds", format(args.seconds, ".15g"),
            "--gomaxprocs", str(args.gomaxprocs),
            "--warmup-requests", str(args.warmup_requests),
            "--timeout", args.timeout,
            "--score-tolerance", "0.000001",
        ])
        row: dict[str, Any] = {
            **cell,
            "engine_label": args.engine_label,
            "manifest_path": str(manifest),
            "manifest_sha256": manifest_hashes[category],
            "client_sha256": client_hash,
            "client_source_sha256": source_hash,
            "report": str(report_path),
            "stdout": str(stdout_path),
            "stderr": str(stderr_path),
            "status": "RUNNING",
            "passed": False,
        }
        summary["rows"].append(row)
        save()
        try:
            completed = run_process(command, timed_env)
            write_text(stdout_path, completed.stdout)
            write_text(stderr_path, completed.stderr)
            try:
                report = json.loads(report_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                report = None
            valid_report = isinstance(report, dict)
            checks = {
                "schema": valid_report and report.get("schema") == RESULT_SCHEMA,
                "status": valid_report and report.get("status") == "COMPLETED",
                "passed": valid_report and report.get("passed") is True,
                "manifest_sha256": valid_report and report.get("manifest_sha256") == manifest_hashes[category],
                "executable_sha256": valid_report and report.get("executable_sha256") == client_hash,
                "batch_size": valid_report and report.get("batch_size") == batch,
                "concurrency": valid_report and report.get("concurrency") == concurrency,
                "max_inflight": valid_report and report.get("max_inflight") == concurrency,
                "warmup": valid_report and report.get("warmup_configured_requests") == args.warmup_requests and report.get("warmup_successes") == args.warmup_requests,
                "credentials": valid_report and report.get("credentials_included_in_report") is False,
            }
            failed_checks = [name for name, passed in checks.items() if not passed]
            row["client_exit_code"] = completed.returncode
            row["status"] = "PASSED" if completed.returncode == 0 and not failed_checks else "FAILED"
            row["passed"] = row["status"] == "PASSED"
            row["validation_errors"] = failed_checks
            if valid_report:
                row["report_status"] = report.get("status")
                row["report_metrics"] = {
                    key: report.get(key) for key in (
                        "actual_elapsed_s", "actual_dispatch_duration_s", "drain_duration_s",
                        "successful_requests", "failed_requests", "successful_queries", "failed_queries",
                        "successful_http_rps", "query_qps", "full_response_validated_latency_ms",
                        "server_json_time_ms", "connection_acquire_ms", "http_status_counts",
                        "response_protocol_counts", "failure_counts",
                    )
                }
            else:
                row["validation_errors"].append("timed row report is missing or unreadable")
            if not row["passed"]:
                summary["failures"].append({
                    "stage": "timed_row", "category": category, "batch_size": batch,
                    "concurrency": concurrency, "errors": row["validation_errors"],
                })
        except OSError as exc:
            row["status"] = "FAILED_TO_START"
            row["validation_errors"] = [str(exc)]
            write_text(stderr_path, str(exc) + "\n")
            summary["failures"].append({
                "stage": "timed_row", "category": category, "batch_size": batch,
                "concurrency": concurrency, "errors": [str(exc)],
            })
        save()
        print(f"[{cell_index}/{len(cells)}] {category} B{batch} C{concurrency}: {row['status']}", flush=True)

    summary["finished_utc"] = utc_now()
    summary["status"] = "COMPLETED" if not summary["failures"] else "COMPLETED_WITH_FAILURES"
    save()
    passed_count = sum(1 for row in summary["rows"] if row.get("passed"))
    print(f"one-arm run {summary['status']}: {passed_count}/{len(summary['rows'])} rows passed; summary at {output / 'summary.json'}")
    return 0 if summary["status"] == "COMPLETED" else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (RunnerError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)

#!/usr/bin/env python3
"""Render the completed B1 shared-CPU comparison from its curated JSON only."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Patch, Rectangle
from matplotlib.lines import Line2D
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "benchmarks/ring-b1-c64-c128-20261110.json"
POLICY_SOURCE = ROOT / "benchmarks/cpu-policy-1-vs-3-20261110.json"
OUT = ROOT / "assets/benchmarks"
STEM = "cpu-fairness-b1-latest-20261110"
POLICY_STEM = "cpu-fairness-b1-policy-latest-20261110"
CATEGORIES = (
    ("unfiltered_no_payload", "No filter · no payload"),
    ("unfiltered_payload", "No filter · payload"),
    ("active_only", "Active-only filter (~90%)"),
    ("active_position_exclude", "Active + position exclude (~9%)"),
)
CONCURRENCIES = (64, 128)
BACKENDS = (
    ("native", "Native Qdrant 1.20", "Native", "earlier three-CPU run · not rerun"),
    ("avx512vnni", "Veortex AVX-512 VNNI", "AVX-512 VNNI", "fresh candidate measurement"),
    ("auto", "Veortex Auto", "Auto", "fresh candidate measurement"),
)
POLICY_MODES = (
    ("Native Qdrant 1.20", "Native", "native"),
    ("Our Veortex V45.1", "AVX-512 VNNI", "avx512vnni"),
    ("Our Veortex V45.1", "Auto", "auto"),
)

# Match the established CPU fairness figure palette.
NATIVE = "#31659b"
AVX = "#cb641b"
AUTO = "#e39b63"
TEXT = "#152b43"
MUTED = "#52677c"
GRID = "#dce5ee"
BG = "#f5f8fc"
WHITE = "#ffffff"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9,
    "text.color": TEXT, "axes.labelcolor": MUTED, "axes.titlecolor": TEXT,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.edgecolor": GRID,
    "svg.fonttype": "none", "svg.hashsalt": "qdrant-veortex-cpu-fairness-b1-20261110",
})


class RefuseInput(ValueError):
    pass


def need(condition: bool, message: str) -> None:
    if not condition:
        raise RefuseInput(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_svg_trailing_whitespace(path: Path) -> None:
    """Strip spaces and tabs at line ends while preserving SVG bytes otherwise."""
    data = path.read_bytes()
    normalized_lines = []
    for line in data.splitlines(keepends=True):
        if line.endswith(b"\r\n"):
            body, ending = line[:-2], b"\r\n"
        elif line.endswith(b"\n") or line.endswith(b"\r"):
            body, ending = line[:-1], line[-1:]
        else:
            body, ending = line, b""
        normalized_lines.append(body.rstrip(b" \t") + ending)
    path.write_bytes(b"".join(normalized_lines))


def finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in "0123456789abcdef" for ch in value.lower())


def load_and_validate() -> tuple[dict[str, Any], dict[tuple[str, int, str], dict[str, Any]], str]:
    try:
        raw = SOURCE.read_bytes()
        document = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RefuseInput(f"curated B1 comparison JSON unavailable or invalid: {exc}") from exc

    need(isinstance(document.get("schema"), str), "curated JSON schema field is missing")
    validation = document.get("validation") or {}
    need(validation.get("campaign_status") == "MEASUREMENTS_COMPLETE_RECORDED_SCOPE",
         "B1 campaign is not complete")
    need(validation.get("expected_rows") == validation.get("recorded_rows") == validation.get("accepted_rows") == 16
         and validation.get("rejected_rows") == 0, "B1 report must contain exactly 16 accepted current rows")

    contract = document.get("contract") or {}
    cells = {(cell.get("batch_size"), cell.get("concurrency")) for cell in contract.get("cells", [])}
    need((contract.get("nodes"), contract.get("cpus_per_node"), contract.get("per_thread_pinning"),
          contract.get("topk_per_query")) == (3, 3, False, 10),
         "CPU, no-pinning, or Top10 contract differs")
    need(cells == {(1, 64), (1, 128)} and contract.get("backends") == ["avx512vnni", "auto"]
         and contract.get("categories") == [category for category, _ in CATEGORIES]
         and contract.get("metadata_present_all_categories") is True,
         "B1 backend/category/concurrency/metadata matrix differs")

    accuracy = document.get("validation", {}).get("accuracy_passes", [])
    expected_accuracy = {(backend, category) for backend in ("avx512vnni", "auto")
                         for category, _ in CATEGORIES}
    acc_index = {(entry.get("backend"), entry.get("category")): entry for entry in accuracy}
    need(len(accuracy) == 8 and set(acc_index) == expected_accuracy and all(
        acc_index[key].get("passed") == 1024 and acc_index[key].get("failed") == 0
        for key in expected_accuracy), "all eight independent 1,024-query accuracy checks must pass")

    current = document.get("rows", [])
    expected = {(backend, category, 1, concurrency) for backend in ("avx512vnni", "auto")
                for category, _ in CATEGORIES for concurrency in CONCURRENCIES}
    selected: dict[tuple[str, int, str], dict[str, Any]] = {}
    for row in current:
        key = (row.get("backend"), row.get("batch_size"), row.get("category"), row.get("concurrency"))
        need(key[0] in ("avx512vnni", "auto") and key[2] in dict(CATEGORIES)
             and (key[1], key[3]) in cells, f"current row is outside B1 matrix: {key}")
        index = (key[2], key[3], key[0])
        need(index not in selected, f"duplicate current B1 cell: {index}")
        need(row.get("measurement_accepted") is True, f"current B1 row was not accepted: {index}")
        metrics = row.get("metrics") or {}
        for field in ("http_rps", "query_qps", "p95_ms", "p99_ms"):
            need(finite(metrics.get(field)) and metrics[field] > 0,
                 f"current cell lacks positive {field}: {index}")
        need(math.isclose(metrics["http_rps"], metrics["query_qps"], rel_tol=1e-9, abs_tol=1e-9),
             f"B1 HTTP RPS and query/s differ: {index}")
        selected[index] = row
    need(len(current) == 16 and len(selected) == 16 and
         {(backend, category, batch, concurrency) for (category, concurrency, backend) in selected
          for batch in (1,)} == expected,
         "current rows do not cover both Veortex backends × four categories × C64/C128")

    native = document.get("historical_native_reference", [])
    expected_native = {(category, 1, concurrency) for category, _ in CATEGORIES for concurrency in CONCURRENCIES}
    native_index = {}
    for row in native:
        key = (row.get("category"), row.get("batch_size"), row.get("concurrency"))
        need(key in expected_native and key not in native_index, f"native reference outside or duplicates B1 matrix: {key}")
        need(row.get("measurement_accepted") is True and "not rerun" in row.get("scope", "").lower(),
             f"Native row is not clearly labeled as prior-run reference: {key}")
        for field in ("http_rps", "query_qps", "p95_ms", "p99_ms"):
            need(finite(row.get(field)) and row[field] > 0, f"native reference lacks {field}: {key}")
        need(math.isclose(row["http_rps"], row["query_qps"], rel_tol=1e-9, abs_tol=1e-9),
             f"Native B1 HTTP RPS and query/s differ: {key}")
        native_index[key] = row
    need(len(native) == 8 and set(native_index) == expected_native,
         "all eight earlier three-CPU Native B1 references are required")

    engines = document.get("engines") or {}
    current_engine = (engines.get("ring_b1_veortex") or engines.get("dynamic_ring_veortex")
                      or engines.get("veortex") or {})
    native_engine = engines.get("prior_native") or engines.get("native") or {}
    need(valid_sha256(current_engine.get("sha256")) and current_engine.get("source_commit"),
         "fresh Veortex candidate source/binary identity is missing")
    need(valid_sha256(native_engine.get("sha256")) and native_engine.get("source_commit"),
         "historical Native source/binary identity is missing")

    for category, _ in CATEGORIES:
        for concurrency in CONCURRENCIES:
            selected[(category, concurrency, "native")] = native_index[(category, 1, concurrency)]
    return document, selected, hashlib.sha256(raw).hexdigest()


def mode_value(row: dict[str, Any], backend: str, field: str) -> float:
    if backend == "native":
        return float(row[field])
    return float(row["metrics"][field])


def draw_allocation_band(fig: plt.Figure) -> None:
    fig.text(.045, .868, "CPU ALLOCATION PER NODE · BOTH ARMS · 3 vCPU · NO PER-THREAD PINNING",
             ha="left", va="center", fontsize=9.2, weight="bold", color=MUTED)
    labels = ("Native", "Veortex")
    left_label, start, width, gap = .045, .16, .25, .018
    for row_index, label in enumerate(labels):
        y = .788 - row_index * .063
        fig.text(left_label, y + .022, label.upper(), ha="left", va="center",
                 fontsize=8.3, weight="bold", color=NATIVE if row_index == 0 else AVX)
        for cpu in range(3):
            x = start + cpu * (width + gap)
            fig.patches.append(FancyBboxPatch(
                (x, y), width, .044, transform=fig.transFigure,
                boxstyle="round,pad=0.003,rounding_size=0.007",
                facecolor="#e5eef7" if row_index == 0 else "#faeee5",
                edgecolor=NATIVE if row_index == 0 else AVX, linewidth=.75))
            fig.text(x + width / 2, y + .022, f"CPU {cpu + 1} · shared", ha="center", va="center",
                     fontsize=8, color=TEXT)


def draw_panel(fig: plt.Figure, bounds: tuple[float, float, float, float], category: str,
               category_label: str, concurrency: int,
               selected: dict[tuple[str, int, str], dict[str, Any]], x_limits: tuple[float, float],
               ticks: list[float]) -> None:
    x, y, width, height = bounds
    fig.patches.append(Rectangle((x, y), width, height, transform=fig.transFigure,
                                 facecolor=WHITE, edgecolor=GRID, linewidth=.8, zorder=-10))
    ax = fig.add_axes((x + .035, y + .028, width - .05, height - .052), facecolor=WHITE)
    ax.set_title(f"{category_label} · B1/C{concurrency}", loc="left", fontsize=10,
                 color=TEXT, weight="bold", pad=7)
    modes = (("native", "Native", NATIVE, ""),
             ("avx512vnni", "AVX-512 VNNI", AVX, ""),
             ("auto", "Auto", AUTO, "//"))
    positions = (2, 1, 0)
    for (backend, _label, color, hatch), position in zip(modes, positions):
        row = selected[(category, concurrency, backend)]
        rps = mode_value(row, backend, "http_rps")
        ax.barh(position, rps, height=.55, color=color, edgecolor=WHITE,
                linewidth=.55, hatch=hatch, zorder=3)
        ax.annotate(f"{rps:,.1f}", xy=(rps, position), xytext=(4, 0), textcoords="offset points",
                    ha="left", va="center", fontsize=9, color=TEXT, clip_on=False)
    ax.set_xscale("log")
    ax.set_xlim(*x_limits)
    ax.set_xticks(ticks, [f"{tick:,.0f}" for tick in ticks])
    ax.tick_params(axis="x", labelsize=8.5, length=0, pad=3)
    ax.set_yticks(positions, ["Native", "AVX-512", "Auto"])
    ax.set_ylim(-.52, 2.52)
    ax.tick_params(axis="y", labelsize=9, length=0, pad=4)
    ax.set_axisbelow(True)
    ax.grid(axis="x", color=GRID, linewidth=.65)
    ax.grid(axis="y", visible=False)
    for name in ("top", "right", "left"):
        ax.spines[name].set_visible(False)


def plotted_rows(selected: dict[tuple[str, int, str], dict[str, Any]], input_sha: str) -> list[dict[str, Any]]:
    output = []
    for category, category_label in CATEGORIES:
        for concurrency in CONCURRENCIES:
            for backend, label, _short, scope in BACKENDS:
                row = selected[(category, concurrency, backend)]
                output.append({
                    "category": category, "category_label": category_label, "batch_size": 1,
                    "concurrency": concurrency, "backend": backend, "engine_label": label,
                    "source_scope": scope,
                    "http_rps": mode_value(row, backend, "http_rps"),
                    "query_qps": mode_value(row, backend, "query_qps"),
                    "p95_ms": mode_value(row, backend, "p95_ms"),
                    "p99_ms": mode_value(row, backend, "p99_ms"),
                    "source_commit": "",
                    "engine_sha256": "",
                    "source_json_sha256": input_sha,
                })
    return output


def render(document: dict[str, Any], selected: dict[tuple[str, int, str], dict[str, Any]], input_sha: str) -> None:
    values = [mode_value(row, backend, "http_rps") for (category, concurrency, backend), row in selected.items()]
    minimum = min(values)
    maximum = max(values)
    low = min(10.0, 10 ** math.floor(math.log10(minimum)))
    high = max(100.0, maximum * 1.8)
    ticks = [float(10 ** power) for power in range(math.floor(math.log10(low)),
                                                     math.ceil(math.log10(high)) + 1)
             if low <= 10 ** power <= high]
    if not ticks:
        ticks = [10.0]

    fig = plt.figure(figsize=(12.8, 16), facecolor=BG)
    fig.text(.045, .968, "B1 shared-CPU results across filter categories",
             ha="left", va="top", fontsize=20, weight="bold", color=TEXT)
    fig.text(.046, .927,
             "Cluster HTTP RPS · B1 means HTTP RPS = query/s · all eight panels use the same logarithmic scale",
             ha="left", va="top", fontsize=11, color=MUTED)
    fig.text(.046, .895,
             "3M × 512D SQ8 flat · 3 nodes · Top10 · fixed 1,024-query corpus",
             ha="left", va="top", fontsize=9.2, color=MUTED)
    draw_allocation_band(fig)

    handles = [
        Patch(facecolor=NATIVE, label="Native Qdrant 1.20 · earlier three-CPU run, not rerun"),
        Patch(facecolor=AVX, label="Veortex AVX-512 VNNI · fresh"),
        Patch(facecolor=AUTO, hatch="//", label="Veortex Auto · fresh"),
    ]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(.045, .704), ncol=3,
               frameon=False, fontsize=8.6, columnspacing=1.5, handlelength=1.3)

    left, right, gap_x = .045, .955, .025
    panel_width = (right - left - gap_x) / 2
    panel_height = .12
    y_positions = (.535, .399, .263, .127)
    for row_index, (category, label) in enumerate(CATEGORIES):
        for column, concurrency in enumerate(CONCURRENCIES):
            bounds = (left + column * (panel_width + gap_x), y_positions[row_index], panel_width, panel_height)
            draw_panel(fig, bounds, category, label, concurrency, selected, (low, high), ticks)

    fig.text(.045, .096,
             "Native values are earlier three-CPU references and were not rerun; both Veortex tiers are fresh candidate measurements.",
             ha="left", va="center", fontsize=8.8, color=MUTED)
    fig.text(.045, .070,
             "All profiles expose three shared CPUs per node with no per-thread pinning. Bars are end-to-end HTTP throughput; p95/p99 are in the report.",
             ha="left", va="center", fontsize=8.5, color=MUTED)
    fig.text(.045, .043,
             "Selected-load comparison, not maximum capacity, scan-only, or causal core scaling; compiler flags are unmatched.",
             ha="left", va="center", fontsize=8.3, color=MUTED)

    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{STEM}.png", dpi=180, facecolor=BG,
                metadata={"Software": "Matplotlib; curated B1 CPU comparison JSON"})
    svg_path = OUT / f"{STEM}.svg"
    fig.savefig(svg_path, facecolor=BG, metadata={"Date": None})
    normalize_svg_trailing_whitespace(svg_path)
    plt.close(fig)

    rows = plotted_rows(selected, input_sha)
    engines = document.get("engines") or {}
    current_engine = (engines.get("ring_b1_veortex") or engines.get("dynamic_ring_veortex")
                      or engines.get("veortex") or {})
    native_engine = engines.get("prior_native") or engines.get("native") or {}
    for row in rows:
        source = native_engine if row["backend"] == "native" else current_engine
        row["source_commit"] = source.get("source_commit", "")
        row["engine_sha256"] = source.get("sha256", "")
    csv_path = OUT / f"{STEM}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    contract = document["contract"]
    validation = document["validation"]
    script = Path(__file__).resolve()
    current_engine = (engines.get("ring_b1_veortex") or engines.get("dynamic_ring_veortex")
                      or engines.get("veortex") or {})
    native_engine = engines.get("prior_native") or engines.get("native") or {}
    manifest = {
        "schema": "cpu_fairness_b1_figure_manifest_v1",
        "new_benchmarks_run_by_renderer": False,
        "source_json": SOURCE.relative_to(ROOT).as_posix(),
        "source_json_sha256": input_sha,
        "generator": script.relative_to(ROOT).as_posix(),
        "generator_sha256": sha256(script),
        "campaign": {
            "campaign_id": document.get("campaign_id"),
            "status": validation["campaign_status"],
            "current_expected_rows": validation["expected_rows"],
            "current_recorded_rows": validation["recorded_rows"],
            "current_accepted_rows": validation["accepted_rows"],
            "historical_native_reference_rows": 8,
            "plotted_bars": len(rows),
            "batch_size": 1,
            "concurrencies": list(CONCURRENCIES),
            "categories": [category for category, _ in CATEGORIES],
            "backends": ["native earlier three-CPU reference, not rerun", "avx512vnni fresh", "auto fresh"],
            "accuracy_checks": validation["accuracy_passes"],
        },
        "engine_sources": {
            "historical_native_reference": {
                "source_commit": native_engine.get("source_commit"),
                "engine_sha256": native_engine.get("sha256"),
                "scope": "earlier three-CPU Native rows; not rerun",
            },
            "fresh_veortex_candidate": {
                "source_commit": current_engine.get("source_commit"),
                "engine_sha256": current_engine.get("sha256"),
                "backends": ["avx512vnni", "auto"],
            },
        },
        "cpu_profile": {
            "nodes": contract["nodes"],
            "cpus_per_node": contract["cpus_per_node"],
            "shared_masks": contract.get("shared_masks"),
            "per_thread_pinning": contract["per_thread_pinning"],
        },
        "plot": {
            "metric": "cluster successful HTTP requests per second",
            "batch_size": 1,
            "query_qps_equals_http_rps": True,
            "scale": "global shared logarithmic axis",
            "annotation": "bar-end labels show actual HTTP RPS",
            "p95_p99": "not plotted; retained in companion CSV and benchmark report",
            "interpretation": "Fresh Veortex candidate measurements beside earlier three-CPU Native references; Native was not rerun. Selected end-to-end loads, not maximum capacity, scan-only throughput, or causal core scaling. Compiler flags remain unmatched.",
        },
        "renderer": {"matplotlib": matplotlib.__version__, "numpy": np.__version__},
        "palette": {"native": NATIVE, "veortex_avx512vnni": AVX, "veortex_auto": AUTO,
                    "text": TEXT, "muted": MUTED, "grid": GRID, "background": BG},
        "output_sha256": {
            f"{STEM}.png": sha256(OUT / f"{STEM}.png"),
            f"{STEM}.svg": sha256(OUT / f"{STEM}.svg"),
            f"{STEM}.csv": sha256(csv_path),
        },
    }
    manifest_path = OUT / f"{STEM}.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "rendered", "source": str(SOURCE), "output_directory": str(OUT),
                      "current_rows": 16, "native_reference_rows": 8, "plotted_bars": len(rows)}, indent=2))


def load_policy_pairs(
    b1_document: dict[str, Any],
    selected: dict[tuple[str, int, str], dict[str, Any]],
) -> tuple[dict[str, Any], dict[tuple[str, str], dict[str, Any]], str]:
    try:
        raw = POLICY_SOURCE.read_bytes()
        policy = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RefuseInput(f"curated 1-vs-3 policy JSON unavailable or invalid: {exc}") from exc

    need(policy.get("schema") == "three_cpu_policy_comparison_v1"
         and policy.get("current_status") == "MEASUREMENTS_COMPLETE_RECORDED_SCOPE"
         and policy.get("current_expected_rows") == policy.get("current_recorded_rows")
         == policy.get("current_accepted_rows") == 48,
         "the historical CPU-policy comparison is incomplete")
    comparisons = policy.get("comparisons", [])
    expected = {(category, mode) for category, _ in CATEGORIES
                for _system, mode, _backend in POLICY_MODES}
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for row in comparisons:
        if row.get("batch_size") != 1 or row.get("concurrency") != 128:
            continue
        key = (row.get("category"), row.get("mode"))
        if key not in expected:
            continue
        need(row.get("scope") == "primary", f"policy cell is not primary scope: {key}")
        need(key not in index, f"duplicate historical policy cell: {key}")
        need(row.get("system") == next(system for system, mode, _backend in POLICY_MODES if mode == key[1]),
             f"policy mode/system mismatch: {key}")
        need(row.get("old_accuracy_passes") == 1024 and row.get("new_accuracy_passes") == 1024,
             f"policy cell lacks complete accuracy checks: {key}")
        for error_set in (row.get("old_timed_errors"), row.get("new_timed_errors")):
            need(isinstance(error_set, dict) and all(value == 0 for value in error_set.values()),
                 f"policy cell has timed errors or incomplete error evidence: {key}")
        for side in ("old_metrics", "new_metrics"):
            metrics = row.get(side) or {}
            for field in ("http_rps", "query_qps", "p95_ms", "p99_ms"):
                need(finite(metrics.get(field)) and metrics[field] > 0,
                     f"policy cell lacks {side}.{field}: {key}")
            need(math.isclose(metrics["http_rps"], metrics["query_qps"], rel_tol=1e-9, abs_tol=1e-9),
                 f"policy cell RPS and query/s differ: {key}")
        need(row.get("old_build_sha256") and row.get("new_build_sha256"),
             f"policy cell lacks binary identities: {key}")
        index[key] = row
    need(len(index) == 12 and set(index) == expected,
         "policy report must provide 12 exact B1/C128 category/mode pairs")

    engines = b1_document.get("engines") or {}
    native_engine = engines.get("prior_native") or engines.get("native") or {}
    current_engine = engines.get("ring_b1_veortex") or engines.get("dynamic_ring_veortex") or engines.get("veortex") or {}
    for category, _ in CATEGORIES:
        for system, mode, backend in POLICY_MODES:
            row = index[(category, mode)]
            old_build = row["old_build_sha256"]
            if backend == "native":
                current = selected[(category, 128, "native")]
                current_build = native_engine.get("sha256")
                need(old_build == current_build,
                     "Native prior policy baseline and earlier three-CPU reference must use the same binary")
            else:
                current = selected[(category, 128, backend)]
                current_build = current_engine.get("sha256")
            new_values = current if backend == "native" else current.get("metrics", {})
            row["_latest_metrics"] = {field: new_values[field] for field in ("http_rps", "query_qps", "p95_ms", "p99_ms")}
            row["_latest_build_sha256"] = current_build
            row["_latest_source_commit"] = native_engine.get("source_commit") if backend == "native" else current_engine.get("source_commit")
            need(isinstance(current_build, str) and len(current_build) == 64,
                 f"latest candidate binary identity is missing for {system}/{mode}")
    return policy, index, hashlib.sha256(raw).hexdigest()


def allocation_table(fig: plt.Figure) -> None:
    x0, label_w, old_x, old_w, new_x, new_w = .045, .15, .205, .465, .685, .27
    fig.text(x0, .866, "POLICY", ha="left", va="center", fontsize=8, weight="bold", color=MUTED)
    fig.text(old_x, .866, "EARLIER 1+2 POLICY · 3 vCPU/NODE", ha="left", va="center",
             fontsize=8, weight="bold", color=MUTED)
    fig.text(new_x, .866, "CURRENT 3-SHARED POLICY · 3 vCPU/NODE", ha="left", va="center",
             fontsize=7.8, weight="bold", color=MUTED)
    rows = (
        ("Native", "1 full-search CPU + 2 service CPUs", "All 3 CPUs shared by every phase; no affinity", NATIVE),
        ("Veortex", "1 scan CPU + 2-CPU shared support pool: TopK / rerank / payload / service",
         "All 3 CPUs shared by every phase; no affinity", AVX),
    )
    for i, (label, old_text, new_text, color) in enumerate(rows):
        y = .814 - i * .063
        for x, width, fill in ((old_x, old_w, "#e8eff6"), (new_x, new_w, "#f7eee7")):
            fig.patches.append(FancyBboxPatch(
                (x, y - .019), width, .042, transform=fig.transFigure,
                boxstyle="round,pad=0.003,rounding_size=0.006", facecolor=fill,
                edgecolor=color, linewidth=.7))
        fig.text(x0, y + .001, label, ha="left", va="center", fontsize=8.4, weight="bold", color=color)
        fig.text(old_x + .008, y + .001, old_text, ha="left", va="center", fontsize=7.7, color=TEXT)
        fig.text(new_x + .008, y + .001, new_text, ha="left", va="center", fontsize=7.1, color=TEXT)


def policy_rows(policy: dict[str, Any], index: dict[tuple[str, str], dict[str, Any]],
                policy_sha: str, b1_sha: str) -> list[dict[str, Any]]:
    rows = []
    for category, category_label in CATEGORIES:
        for system, mode, backend in POLICY_MODES:
            record = index[(category, mode)]
            old = record["old_metrics"]
            new = record["_latest_metrics"]
            rows.append({
                "category": category, "category_label": category_label,
                "batch_size": 1, "concurrency": 128, "system": system,
                "mode": mode, "current_backend": backend,
                "old_policy": "one search/scan CPU + two support CPUs; 3 vCPU total",
                "new_policy": "three shared CPUs per node; no per-thread affinity",
                "old_http_rps": old["http_rps"], "new_http_rps": new["http_rps"],
                "http_rps_change_percent": 100 * (new["http_rps"] / old["http_rps"] - 1),
                "old_query_qps": old["query_qps"], "new_query_qps": new["query_qps"],
                "old_p95_ms": old["p95_ms"], "new_p95_ms": new["p95_ms"],
                "old_p99_ms": old["p99_ms"], "new_p99_ms": new["p99_ms"],
                "old_build_sha256": record["old_build_sha256"],
                "new_build_sha256": record["_latest_build_sha256"],
                "latest_source_commit": record["_latest_source_commit"],
                "old_source": record.get("old_source"),
                "policy_json_sha256": policy_sha, "latest_b1_json_sha256": b1_sha,
            })
    return rows


def render_policy_figure(policy: dict[str, Any], index: dict[tuple[str, str], dict[str, Any]],
                         policy_sha: str, b1_document: dict[str, Any], b1_sha: str) -> None:
    rows = policy_rows(policy, index, policy_sha, b1_sha)
    values = [item[key] for item in rows for key in ("old_http_rps", "new_http_rps")]
    low = 10 ** math.floor(math.log10(min(values)))
    high = 10 ** math.ceil(math.log10(max(values) * 1.35))
    ticks = [float(10 ** p) for p in range(math.floor(math.log10(low)), math.ceil(math.log10(high)) + 1)
             if low <= 10 ** p <= high]

    fig = plt.figure(figsize=(12.8, 12.2), facecolor=BG)
    fig.text(.045, .968, "One search/scan CPU + two support CPUs → three shared CPUs",
             ha="left", va="top", fontsize=19, weight="bold", color=TEXT)
    fig.text(.046, .931,
             "B1/C128 cluster HTTP RPS · both policies budget 3 vCPU/node · all four panels share one log scale",
             ha="left", va="top", fontsize=10.7, color=MUTED)
    fig.text(.046, .901,
             "3M × 512D SQ8 flat · 3 nodes · Top10 · four filter/payload categories · 1,024-query accuracy corpus",
             ha="left", va="top", fontsize=8.8, color=MUTED)
    allocation_table(fig)

    fig.legend(handles=[
        Line2D([0], [0], color=MUTED, marker="o", markersize=5, linestyle="-", label="Earlier 1+2 policy"),
        Line2D([0], [0], color=MUTED, marker="D", markerfacecolor=WHITE, markersize=5, linestyle="-",
               label="Current 3-shared policy"),
        Patch(facecolor=NATIVE, label="Native Qdrant 1.20"),
        Patch(facecolor=AVX, label="Veortex AVX-512 VNNI"),
        Patch(facecolor=AUTO, hatch="//", label="Veortex Auto"),
        Line2D([0], [0], color="#b43737", linewidth=2, label="Throughput regression"),
    ], loc="upper left", bbox_to_anchor=(.045, .687), ncol=3, frameon=False,
       fontsize=8, columnspacing=1.25, handlelength=1.4)

    left, right, gap_x = .045, .955, .025
    panel_width = (right - left - gap_x) / 2
    panel_height = .255
    bounds_y = (.389, .111)
    for category_index, (category, label) in enumerate(CATEGORIES):
        col, row = category_index % 2, category_index // 2
        x = left + col * (panel_width + gap_x)
        y = bounds_y[row]
        width = panel_width
        fig.patches.append(Rectangle((x, y), width, panel_height, transform=fig.transFigure,
                                     facecolor=WHITE, edgecolor=GRID, linewidth=.8, zorder=-10))
        ax = fig.add_axes((x + .045, y + .043, width - .061, panel_height - .073), facecolor=WHITE)
        ax.set_title(label, loc="left", fontsize=9.7, color=TEXT, weight="bold", pad=6)
        for mode_index, (_system, mode, backend) in enumerate(POLICY_MODES):
            item = index[(category, mode)]
            old = float(item["old_metrics"]["http_rps"])
            new = float(item["_latest_metrics"]["http_rps"])
            change = 100 * (new / old - 1)
            y_pos = 2 - mode_index
            color = NATIVE if backend == "native" else (AVX if backend == "avx512vnni" else AUTO)
            segment_color = "#b43737" if change < 0 else color
            ax.plot([old, new], [y_pos, y_pos], color=segment_color, linewidth=1.7, zorder=2)
            ax.scatter([old], [y_pos], s=28, marker="o", c=[color], edgecolors=WHITE,
                       linewidths=.6, zorder=3)
            ax.scatter([new], [y_pos], s=32, marker="D", facecolors=WHITE,
                       edgecolors="#b43737" if change < 0 else color, linewidths=1.35, zorder=4)
            ax.annotate(f"{old:,.1f}", (old, y_pos), xytext=(-3, 7), textcoords="offset points",
                        ha="right", va="bottom", fontsize=7.2, color=MUTED, clip_on=False)
            ax.annotate(f"{new:,.1f}", (new, y_pos), xytext=(3, -8), textcoords="offset points",
                        ha="left", va="top", fontsize=7.2,
                        color="#b43737" if change < 0 else TEXT, clip_on=False)
            mid = math.sqrt(old * new)
            ax.annotate(f"{change:+.1f}%", (mid, y_pos), xytext=(0, 13), textcoords="offset points",
                        ha="center", va="bottom", fontsize=7.1,
                        color="#b43737" if change < 0 else color, weight="bold", clip_on=False)
        ax.set_xscale("log")
        ax.set_xlim(low, high)
        ax.set_xticks(ticks, [f"{tick:,.0f}" for tick in ticks])
        ax.tick_params(axis="x", labelsize=7.8, length=0, pad=3)
        ax.set_yticks([2, 1, 0], ["Native", "AVX-512 VNNI", "Auto"])
        ax.set_ylim(-.48, 2.48)
        ax.tick_params(axis="y", labelsize=8.2, length=0, pad=4)
        ax.grid(axis="x", color=GRID, linewidth=.65)
        ax.set_axisbelow(True)
        for name in ("top", "right", "left"):
            ax.spines[name].set_visible(False)

    builds = policy.get("builds", {})
    historical_veortex = builds.get("historical_veortex_v45_1")
    current_engine = (b1_document.get("engines") or {}).get("ring_b1_veortex") or {}
    fig.text(.045, .075,
             "Native current values are earlier three-shared-CPU references, not reruns. Veortex current values are fresh B1/C128 measurements.",
             ha="left", va="center", fontsize=8.1, color=MUTED)
    fig.text(.045, .048,
             f"Overall policy comparison, not causal core scaling; Veortex ELF changed ({str(historical_veortex)[:12]} → {str(current_engine.get('sha256'))[:12]}), B1 kernel unchanged. Compiler flags unmatched.",
             ha="left", va="center", fontsize=7.9, color=MUTED)

    OUT.mkdir(parents=True, exist_ok=True)
    png = OUT / f"{POLICY_STEM}.png"
    svg = OUT / f"{POLICY_STEM}.svg"
    csv_path = OUT / f"{POLICY_STEM}.csv"
    fig.savefig(png, dpi=180, facecolor=BG, metadata={"Software": "Matplotlib; two curated CPU-policy JSON inputs"})
    fig.savefig(svg, facecolor=BG, metadata={"Date": None})
    normalize_svg_trailing_whitespace(svg)
    plt.close(fig)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    script = Path(__file__).resolve()
    engine_data = b1_document.get("engines") or {}
    native_engine = engine_data.get("prior_native") or engine_data.get("native") or {}
    candidate = engine_data.get("ring_b1_veortex") or engine_data.get("dynamic_ring_veortex") or engine_data.get("veortex") or {}
    manifest = {
        "schema": "cpu_fairness_b1_policy_figure_manifest_v1",
        "new_benchmarks_run_by_renderer": False,
        "inputs": {
            "historical_policy_report": {"path": POLICY_SOURCE.relative_to(ROOT).as_posix(),
                                         "sha256": policy_sha},
            "latest_b1_report": {"path": SOURCE.relative_to(ROOT).as_posix(), "sha256": b1_sha},
        },
        "generator": {"path": script.relative_to(ROOT).as_posix(), "sha256": sha256(script)},
        "plotted_pairs": 12,
        "matrix": {"batch_size": 1, "concurrency": 128,
                   "categories": [cat for cat, _ in CATEGORIES],
                   "modes": [mode for _system, mode, _backend in POLICY_MODES]},
        "cpu_allocation": {
            "total_budget_each_policy": "3 vCPU per node",
            "old_native": "1 full-search CPU + 2 service CPUs",
            "old_veortex": "1 scan CPU + 2-CPU shared support pool for TopK/rerank/payload/service",
            "new_policy": "all three CPUs shared by all phases; no per-thread affinity",
        },
        "scope": {
            "comparison_type": "overall CPU policy comparison; not pure core scaling",
            "native_current": "earlier three-shared-CPU reference, not rerun",
            "veortex_current": "fresh B1/C128 measurements",
            "veortex_old_build_sha256": historical_veortex,
            "veortex_current_build_sha256": candidate.get("sha256"),
            "b1_kernel_path": "unchanged in current candidate; Veortex ELF differs from historical baseline",
            "compiler_flags": "unmatched",
            "old_process_cpu_aggregate": "not available; role/affinity observer only",
        },
        "plot": {"metric": "cluster successful HTTP requests per second",
                 "axis": "one global logarithmic scale", "labels": "both endpoint RPS and percent change",
                 "regressions": "red connector and new marker outline"},
        "engine_sources": {"native_reference": {"source_commit": native_engine.get("source_commit"),
                                                   "sha256": native_engine.get("sha256")},
                           "current_veortex": {"source_commit": candidate.get("source_commit"),
                                               "sha256": candidate.get("sha256")}},
        "renderer": {"matplotlib": matplotlib.__version__, "numpy": np.__version__},
        "output_sha256": {png.name: sha256(png), svg.name: sha256(svg), csv_path.name: sha256(csv_path)},
    }
    manifest_path = OUT / f"{POLICY_STEM}.manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "rendered", "policy_pairs": len(rows),
                      "policy_png": str(png), "policy_manifest": str(manifest_path)}, indent=2))


def main() -> None:
    document, selected, input_sha = load_and_validate()
    policy, policy_index, policy_sha = load_policy_pairs(document, selected)
    render(document, selected, input_sha)
    render_policy_figure(policy, policy_index, policy_sha, document, input_sha)


if __name__ == "__main__":
    try:
        main()
    except RefuseInput as error:
        raise SystemExit(f"Refusing to render: {error}") from None

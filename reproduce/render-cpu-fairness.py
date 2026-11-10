#!/usr/bin/env python3
"""Render the CPU-policy comparison from its completed public JSON only."""

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
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, Rectangle
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "benchmarks/cpu-policy-1-vs-3-20261110.json"
OUT = ROOT / "assets/benchmarks"
STEM = "cpu-fairness-20261110"
CATEGORIES = (
    ("unfiltered_no_payload", "No filter · no payload"),
    ("unfiltered_payload", "No filter · payload"),
    ("active_only", "Active-only filter (~90%)"),
    ("active_position_exclude", "Active + position exclude (~9%)"),
)
MODES = (
    ("Native Qdrant 1.20", "Native", "Native", "native"),
    ("Our Veortex V45.1", "AVX-512 VNNI", "Veortex AVX-512 VNNI", "veortex"),
    ("Our Veortex V45.1", "Auto", "Veortex Auto", "veortex"),
)
EXPECTED_BUILDS = {
    "native": "5081acd073ef29701415dc2d1655d98750be8c08008541febc20cf2935800f2f",
    "veortex": "90d54aeabbaa17350b94161f6a7926528b13452b0b50296f0bc45fc0e96969e0",
}

# Keep the established chart palette and typography.
NATIVE = "#31659b"
OUR = "#cb641b"
TEXT = "#152b43"
MUTED = "#52677c"
GRID = "#dce5ee"
BG = "#f5f8fc"
WHITE = "#ffffff"
NATIVE_PALE = "#e5eef7"
OUR_PALE = "#faeee5"
REGRESSION = "#ad3d3b"
REGRESSION_PALE = "#f9e8e7"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 10,
    "text.color": TEXT, "axes.labelcolor": MUTED, "axes.titlecolor": TEXT,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.edgecolor": GRID,
    "svg.fonttype": "none", "svg.hashsalt": "qdrant-veortex-cpu-fairness-20261110",
})


class RefuseInput(ValueError):
    pass


def need(condition: bool, message: str) -> None:
    if not condition:
        raise RefuseInput(message)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def load_and_validate() -> tuple[dict[str, Any], dict[tuple[str, str], dict[str, Any]]]:
    try:
        document = json.loads(SOURCE.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RefuseInput(f"comparison JSON unavailable or invalid: {exc}") from exc

    need(document.get("schema") == "three_cpu_policy_comparison_v1", "unexpected comparison schema")
    need(document.get("current_status") == "MEASUREMENTS_COMPLETE_RECORDED_SCOPE", "current campaign is not complete")
    need(document.get("current_expected_rows") == 48 and document.get("current_recorded_rows") == 48,
         "curated campaign does not contain all 48 rows")
    need(document.get("current_accepted_rows") == 48, "curated campaign does not have 48 accepted rows")
    comparisons = document.get("comparisons")
    need(isinstance(comparisons, list) and len(comparisons) == 24, "expected all 24 accepted comparisons")
    scope_counts = {scope: sum(row.get("scope") == scope for row in comparisons) for scope in ("primary", "supplemental")}
    need(scope_counts == {"primary": 20, "supplemental": 4}, f"unexpected comparison scopes: {scope_counts}")

    expected_keys = {(system, mode, category) for system, mode, _, _ in MODES for category, _ in CATEGORIES}
    selected: dict[tuple[str, str], dict[str, Any]] = {}
    for row in comparisons:
        if row.get("scope") != "primary" or row.get("batch_size") != 1 or row.get("concurrency") != 128:
            continue
        key = (row.get("system"), row.get("mode"), row.get("category"))
        need(key not in selected, f"duplicate B1/C128 comparison: {key}")
        selected[key] = row
    need(set(selected) == expected_keys, "B1/C128 comparison does not contain exactly the expected 12 pairs")

    for system, mode, _, owner in MODES:
        for category, _ in CATEGORIES:
            row = selected[system, mode, category]
            label = f"{system}/{mode}/{category}"
            need(row.get("old_build_sha256") == row.get("new_build_sha256") == EXPECTED_BUILDS[owner],
                 f"source binary differs across old/new pair: {label}")
            need(row.get("old_accuracy_passes") == row.get("new_accuracy_passes") == 1024,
                 f"initial accuracy gate failed: {label}")
            need(row.get("old_exact_matches") == row.get("old_successful_queries")
                 and row.get("new_exact_matches") == row.get("new_successful_queries"),
                 f"timed Top10 exact-match counts differ from successful queries: {label}")
            for side in ("old", "new"):
                errors = row.get(f"{side}_timed_errors")
                need(isinstance(errors, dict) and all(value == 0 for value in errors.values()),
                     f"timed errors are nonzero or missing: {label}/{side}")
            for metric in ("http_rps", "p95_ms", "p99_ms"):
                need(finite(row.get("old_metrics", {}).get(metric)) and finite(row.get("new_metrics", {}).get(metric)),
                     f"missing plotted metric {metric}: {label}")
            ratios = row.get("new_over_old_ratios", {})
            calculated = row["new_metrics"]["http_rps"] / row["old_metrics"]["http_rps"]
            need(finite(ratios.get("http_rps")) and math.isclose(ratios["http_rps"], calculated, rel_tol=1e-10),
                 f"RPS ratio mismatch: {label}")
            need(row.get("new_process_cpu_cores_per_node") and len(row["new_process_cpu_cores_per_node"]) == 3
                 and all(finite(value) and value > 0 for value in row["new_process_cpu_cores_per_node"]),
                 f"current whole-process CPU evidence is missing: {label}")
    return document, selected


def draw_cell(ax: plt.Axes, x: float, y: float, width: float, height: float,
              label: str, face: str, edge: str, fontsize: float = 8.2) -> None:
    ax.add_patch(FancyBboxPatch((x, y), width, height,
                                boxstyle="round,pad=0.006,rounding_size=0.012",
                                facecolor=face, edgecolor=edge, linewidth=0.8))
    ax.text(x + width / 2, y + height / 2, label, ha="center", va="center",
            fontsize=fontsize, color=TEXT, weight="medium", linespacing=1.05)


def draw_card(fig: plt.Figure, bounds: tuple[float, float, float, float], title: str,
              old_kind: str) -> None:
    ax = fig.add_axes(bounds)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.add_patch(FancyBboxPatch((0, 0), 1, 1,
                                boxstyle="round,pad=0.012,rounding_size=0.025",
                                facecolor=WHITE, edgecolor=GRID, linewidth=1.1))
    ax.text(.045, .88, title, ha="left", va="center", fontsize=10.2, weight="bold", color=TEXT)
    if old_kind == "native":
        draw_cell(ax, .045, .39, .29, .33, "CPU 1\nFull search", NATIVE_PALE, NATIVE)
        draw_cell(ax, .355, .39, .29, .33, "CPU 2\nService", "#eef2f6", MUTED)
        draw_cell(ax, .665, .39, .29, .33, "CPU 3\nService", "#eef2f6", MUTED)
        ax.text(.045, .18, "1 pinned search CPU + 2 support CPUs", ha="left", fontsize=8.6, color=MUTED)
        ax.text(.045, .065, "3 vCPU per container, per node", ha="left", fontsize=8.1, color=MUTED)
    elif old_kind == "veortex":
        draw_cell(ax, .045, .39, .29, .33, "CPU 1\nScan", OUR_PALE, OUR)
        draw_cell(ax, .355, .39, .29, .33, "CPU 2\nShared support pool", OUR_PALE, OUR)
        draw_cell(ax, .665, .39, .29, .33, "CPU 3\nShared support pool", OUR_PALE, OUR)
        ax.text(.045, .18, "1 pinned scan CPU + 2 support CPUs", ha="left", fontsize=8.6, color=MUTED)
        ax.text(.045, .065, "Both shared TopK/rerank/payload/service work", ha="left", fontsize=7.8, color=MUTED)
    else:
        ax.text(.045, .69, "NATIVE", ha="left", va="center", fontsize=7.6, weight="bold", color=NATIVE)
        ax.text(.045, .32, "VEORTEX", ha="left", va="center", fontsize=7.6, weight="bold", color=OUR)
        for index in range(3):
            x = .28 + index * .225
            draw_cell(ax, x, .57, .205, .23, "Shared", NATIVE_PALE, NATIVE, fontsize=7.5)
            draw_cell(ax, x, .20, .205, .23, "Shared", OUR_PALE, OUR, fontsize=7.5)
        ax.text(.045, .045, "3 vCPU/container/node · all phases share mask · no thread pinning",
                ha="left", va="center", fontsize=7.6, color=MUTED)


def category_panel(fig: plt.Figure, bounds: tuple[float, float, float, float],
                   category: str, category_label: str,
                   selected: dict[tuple[str, str], dict[str, Any]]) -> None:
    x, y, w, h = bounds
    fig.patches.append(Rectangle((x, y), w, h, transform=fig.transFigure,
                                 facecolor=WHITE, edgecolor=GRID, linewidth=.8, zorder=-10))
    fig.text(x + .018, y + h - .035, category_label, ha="left", va="center",
             fontsize=11.2, weight="bold", color=TEXT)
    plot_bounds = (x + .035, y + .045, w * .57, h - .10)
    value_bounds = (x + w * .63, y + .045, w * .34, h - .10)
    ax = fig.add_axes(plot_bounds, facecolor=WHITE)
    value_ax = fig.add_axes(value_bounds, facecolor=WHITE)
    value_ax.set_xlim(0, 1)
    value_ax.set_ylim(-.55, 2.55)
    value_ax.axis("off")
    y_positions = {"Native": 2, "AVX-512 VNNI": 1, "Auto": 0}
    color_by_mode = {"Native": NATIVE, "AVX-512 VNNI": OUR, "Auto": OUR}
    for system, mode, label, _ in MODES:
        row = selected[system, mode, category]
        pos = y_positions[mode]
        old = row["old_metrics"]["http_rps"]
        new = row["new_metrics"]["http_rps"]
        change = (new / old - 1) * 100
        color = color_by_mode[mode]
        if mode == "Auto" and change < 0:
            ax.axhspan(pos - .34, pos + .34, color=REGRESSION_PALE, zorder=0)
        ax.plot([old, new], [pos, pos], color=color, alpha=.62, linewidth=2.0, zorder=2)
        ax.scatter([old], [pos], marker="o", s=39, facecolors=WHITE,
                   edgecolors=color, linewidths=1.7, zorder=3)
        ax.scatter([new], [pos], marker="D", s=38, color=color, edgecolors=WHITE,
                   linewidths=.5, zorder=4)
        text_color = REGRESSION if mode == "Auto" and change < 0 else color
        value_ax.text(.015, pos, f"{old:,.2f} → {new:,.2f}  ({change:+.1f}%)",
                      ha="left", va="center", fontsize=8.6, weight="medium", color=text_color)
    ax.set_xscale("log")
    ax.set_xlim(10, 6500)
    ax.set_ylim(-.55, 2.55)
    ax.set_yticks([2, 1, 0], ["Native", "AVX-512 VNNI", "Auto"])
    ax.tick_params(axis="y", length=0, pad=5, labelsize=8.8)
    for tick, mode in zip(ax.get_yticklabels(), ("Native", "AVX-512 VNNI", "Auto")):
        tick.set_color(color_by_mode[mode])
    ax.set_xticks([10, 100, 1000, 5000], ["10", "100", "1,000", "5,000"])
    ax.tick_params(axis="x", which="major", length=0, pad=4, labelsize=7.8)
    ax.set_axisbelow(True)
    ax.grid(axis="x", color=GRID, linewidth=.65)
    ax.grid(axis="y", visible=False)
    for name in ("top", "right", "left"):
        ax.spines[name].set_visible(False)


def plotted_rows(selected: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for category, category_label in CATEGORIES:
        for system, mode, mode_label, owner in MODES:
            row = selected[system, mode, category]
            old, new = row["old_metrics"]["http_rps"], row["new_metrics"]["http_rps"]
            output.append({
                "category": category, "category_label": category_label,
                "system": system, "mode": mode_label, "batch_size": 1, "concurrency": 128,
                "old_http_rps": old, "new_http_rps": new,
                "change_percent_new_over_old": (new / old - 1) * 100,
                "ratio_new_over_old": new / old,
                "old_build_sha256": row["old_build_sha256"],
                "new_build_sha256": row["new_build_sha256"],
                "old_source": row["old_source"], "new_source": row["new_source"],
                "old_manifest_sha256": row["old_manifest_sha256"],
                "new_manifest_sha256": row["new_manifest_sha256"],
                "new_cpu_equivalents_node0": row["new_process_cpu_cores_per_node"][0],
                "new_cpu_equivalents_node1": row["new_process_cpu_cores_per_node"][1],
                "new_cpu_equivalents_node2": row["new_process_cpu_cores_per_node"][2],
                "historical_cpu_aggregate": "unavailable; historical observer recorded role/affinity evidence only",
            })
    return output


def render(document: dict[str, Any], selected: dict[tuple[str, str], dict[str, Any]]) -> None:
    fig = plt.figure(figsize=(16.4, 10.2), facecolor=BG)
    fig.text(.045, .962, "One pinned search/scan CPU + two support CPUs vs three shared CPUs",
             ha="left", va="top", fontsize=21, weight="bold", color=TEXT)
    fig.text(.046, .922,
             "B1/C128 end-to-end HTTP RPS · 3 vCPU per container/node in both profiles · exact old/new binaries per arm",
             ha="left", va="top", fontsize=11.5, color=MUTED)

    # Top CPU allocation explainer.
    fig.text(.05, .884, "CPU ALLOCATION PER NODE", ha="left", va="center",
             fontsize=9.3, weight="bold", color=MUTED)
    draw_card(fig, (.05, .655, .285, .205), "HISTORICAL · NATIVE", "native")
    draw_card(fig, (.358, .655, .285, .205), "HISTORICAL · VEORTEX V45.1", "veortex")
    draw_card(fig, (.666, .655, .285, .205), "CURRENT · BOTH ENGINES", "shared")
    fig.text(.05, .632,
             "Old total budget is three vCPUs for both containers; Veortex support CPUs also ran TopK, FP32 reranking, and payload work.",
             ha="left", va="center", fontsize=8.8, color=MUTED)

    # Bottom: four category panels on one shared logarithmic RPS scale.
    fig.text(.05, .599, "B1/C128 HTTP RPS BY CATEGORY · SUCCESSFUL REQUESTS/S · SHARED LOG SCALE (10–6,500)", ha="left", va="center",
             fontsize=9.3, weight="bold", color=MUTED)
    handles = [
        Line2D([], [], marker="o", linestyle="none", markerfacecolor=WHITE,
               markeredgecolor=MUTED, markeredgewidth=1.4, label="Historical pinned profile"),
        Line2D([], [], marker="D", linestyle="none", markerfacecolor=MUTED,
               markeredgecolor=WHITE, label="Current shared-three-CPU profile"),
        Line2D([], [], color=NATIVE, lw=2.2, label="Native Qdrant 1.20"),
        Line2D([], [], color=OUR, lw=2.2, label="Our Veortex (AVX-512 VNNI / Auto)"),
    ]
    fig.legend(handles=handles, loc="upper right", bbox_to_anchor=(.955, .611),
               frameon=False, ncol=2, fontsize=8.6, columnspacing=1.3,
               handletextpad=.45, borderaxespad=0)
    panel_bounds = (
        (.05, .365, .435, .205), (.515, .365, .435, .205),
        (.05, .115, .435, .205), (.515, .115, .435, .205),
    )
    for bounds, (category, label) in zip(panel_bounds, CATEGORIES):
        category_panel(fig, bounds, category, label, selected)

    fig.text(.05, .080,
             "Red highlights mark the two Veortex Auto regressions. Native/AVX-512 VNNI/Auto all share the same B1/C128 workload within each category.",
             ha="left", va="center", fontsize=8.6, color=MUTED)
    fig.text(.05, .052,
             "Overall CPU-policy comparison, not pure core scaling: old phase placement and TopK scheduling differ; Veortex queue budget changed (640 MiB → 2 GiB); client and run time/order differ.",
             ha="left", va="center", fontsize=8.1, color=MUTED)
    fig.text(.05, .027,
             "No scan-only CPU-time metric was collected. Old/new containers each had 3 vCPU/node; old support CPUs did compute work. Compiler flags are unmatched.",
             ha="left", va="center", fontsize=8.1, color=MUTED)
    fig.savefig(OUT / f"{STEM}.png", dpi=180, facecolor=BG,
                metadata={"Software": "Matplotlib; completed CPU-policy JSON"})
    fig.savefig(OUT / f"{STEM}.svg", facecolor=BG, metadata={"Date": None})
    plt.close(fig)

    rows = plotted_rows(selected)
    csv_path = OUT / f"{STEM}.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    script_path = Path(__file__).resolve()
    manifest = {
        "schema": "cpu_fairness_figure_manifest_v1",
        "new_benchmarks_run": False,
        "source_json": SOURCE.relative_to(ROOT).as_posix(),
        "source_json_sha256": sha256(SOURCE),
        "generator": script_path.relative_to(ROOT).as_posix(),
        "generator_sha256": sha256(script_path),
        "completed_campaign": {
            "status": document["current_status"],
            "expected_rows": document["current_expected_rows"],
            "recorded_rows": document["current_recorded_rows"],
            "accepted_rows": document["current_accepted_rows"],
            "comparison_rows": 24,
            "plotted_pairs": len(rows),
            "batch_size": 1,
            "concurrency": 128,
        },
        "plot": {
            "metric": "successful HTTP requests per second",
            "scale": "shared logarithmic axis from 10 to 6500 RPS",
            "change_percent": "(current shared-three-CPU RPS / historical pinned-profile RPS - 1) * 100",
            "highlighted_regressions": ["Veortex Auto active_only", "Veortex Auto active_position_exclude"],
            "interpretation": "End-to-end CPU-policy comparison; not pure cores scaling. Both old and new containers had three vCPUs per node. No scan-only CPU-time metric was collected.",
        },
        "allocation_labels": {
            "historical_native": "3 vCPU/node: one CPU pinned for full search plus two support/service CPUs",
            "historical_veortex": "3 vCPU/node: one CPU pinned for scan plus two support CPUs that also performed TopK, FP32 reranking, and payload work",
            "current_both": "3 vCPU/node shared full mask for all phases; no per-thread pinning",
        },
        "renderer": {"matplotlib": matplotlib.__version__, "numpy": np.__version__},
        "palette": {"native": NATIVE, "veortex": OUR, "text": TEXT, "muted": MUTED, "grid": GRID, "background": BG},
        "output_sha256": {
            f"{STEM}.png": sha256(OUT / f"{STEM}.png"),
            f"{STEM}.svg": sha256(OUT / f"{STEM}.svg"),
            f"{STEM}.csv": sha256(csv_path),
        },
    }
    (OUT / f"{STEM}.manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "rendered", "source": str(SOURCE), "output_directory": str(OUT),
                      "comparison_rows": 24, "plotted_pairs": len(rows),
                      "new_over_old_rps_changes": [round(row["change_percent_new_over_old"], 2) for row in rows]}, indent=2))


def main() -> None:
    document, selected = load_and_validate()
    OUT.mkdir(parents=True, exist_ok=True)
    render(document, selected)


if __name__ == "__main__":
    try:
        main()
    except RefuseInput as error:
        raise SystemExit(f"Refusing to render: {error}") from None

#!/usr/bin/env python3
"""Render recorded measurements; never starts Qdrant or sends benchmark requests."""

import csv
import hashlib
import io
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/benchmarks"
PRIMARY = ROOT / "benchmarks/h2h-sq8-batch-20261109.json"
REMEDIATION = ROOT / "benchmarks/h2h-sq8-admission-remediation-20261109.json"
CATEGORIES = [
    ("unfiltered_no_payload", "No filter\nNo payload"),
    ("unfiltered_payload", "No filter\nPayload returned"),
    ("active_only", "Active filter (~90%)\nPayload returned"),
    ("active_position_exclude", "Active + position + exclusion (~9%)\nPayload returned"),
]
NATIVE, OUR, TEXT, MUTED, GRID, BG = (
    "#31659b", "#cb641b", "#152b43", "#52677c", "#dce5ee", "#f5f8fc"
)
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 11,
    "text.color": TEXT, "axes.labelcolor": MUTED, "axes.titlecolor": TEXT,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.edgecolor": GRID,
    "svg.fonttype": "none", "svg.hashsalt": "qdrant-veortex-sq8-20261109",
})


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_evidence(path):
    data = json.loads(path.read_text())
    expected = {"points": 3000000, "dimension": 512, "quantization": "SQ8",
                "topk_per_query": 10, "nodes": 3, "cpus_per_node": 3,
                "compute_cpus_per_node": 1, "support_cpus_per_node": 2, "hnsw": False}
    for key, value in expected.items():
        assert data["contract"][key] == value, (path, key)
    return data


primary, remediation = read_evidence(PRIMARY), read_evidence(REMEDIATION)
SOURCE_HASHES = {p: digest(p) for p in (PRIMARY, REMEDIATION)}
assert primary["client"]["binary_sha256"] == remediation["client"]["binary_sha256"]
assert remediation["remediation"]["memory_cap_bytes"] == 640 * 1024**2
assert remediation["remediation"]["compiled_configurable_ceiling_bytes"] == 2048 * 1024**2
index = {(r["engine"], r["category"], r["batch_size"], r["concurrency"]): r
         for r in primary["rows"]}
remediated = {r["category"]: r for r in remediation["rows"]}
assert len(index) == 80 and len(remediated) == 4
selected = {}


def row(engine, category, batch, concurrency):
    is_remediation = engine == "veortex" and batch == 64 and concurrency == 4
    r = remediated[category] if is_remediation else index[engine, category, batch, concurrency]
    assert r["measurement_accepted"] and r["quality_valid"] and r["intended_route_valid"]
    assert r["cpu_observer_status"] == "PASSED"
    assert r["failed_requests"] == r["http_429_count"] == r["correctness_failed_requests"] == 0
    assert r["exact_query_truth_matches"] == r["successful_queries"]
    assert abs(r["query_qps"] - batch * r["successful_http_rps"]) < 1e-8
    assert abs(r["successful_http_rps"] - r["successful_requests"] / r["actual_elapsed_s"]) < 1e-8
    source = REMEDIATION if is_remediation else PRIMARY
    version = "V45.1 remediation" if is_remediation else ("V45" if engine == "veortex" else "native 1.20.0")
    selected[engine, category, batch, concurrency] = {
        "engine": engine, "build": version, "category": category,
        "batch_size": batch, "concurrency": concurrency,
        **{k: r[k] for k in ("successful_http_rps", "query_qps", "p50_ms", "p95_ms", "p99_ms",
                            "successful_requests", "successful_queries", "failed_requests", "actual_elapsed_s")},
        "source_file": source.relative_to(ROOT).as_posix(), "source_row_ordinal": r["ordinal"],
        "source_sha256": SOURCE_HASHES[source], "remediation": is_remediation,
    }
    return r


def clean_axis(ax):
    for name in ("top", "right", "left"):
        ax.spines[name].set_visible(False)
    ax.tick_params(axis="both", length=0, pad=8)
    ax.set_axisbelow(True)
    ax.grid(axis="x", color=GRID, linewidth=0.7)


def save(fig, stem):
    for suffix in ("png", "svg"):
        metadata = {"Software": "Matplotlib; recorded benchmark JSON"} if suffix == "png" else {"Date": None}
        destination = OUT / f"{stem}.{suffix}"
        fig.savefig(destination, dpi=170, facecolor=fig.get_facecolor(), metadata=metadata)
        if suffix == "svg":
            destination.write_text("\n".join(line.rstrip() for line in destination.read_text().splitlines()) + "\n")
    plt.close(fig)


def overview():
    fig = plt.figure(figsize=(18, 11), facecolor=BG)
    fig.text(.055, .947, "Qdrant 1.20 vs Qdrant + Veortex", size=27, weight="bold")
    fig.text(.055, .907, "Recorded SQ8 flat-search comparison  |  3 million vectors x 512D  |  ordered Top10", size=14, color=MUTED)
    fig.text(.055, .864, "B1 / C128", size=17, weight="bold")
    fig.text(.178, .864, "1 query per HTTP request; 128 concurrent requests; cluster-wide results", size=12, color=MUTED)
    fig.legend(handles=[Line2D([], [], lw=9, color=NATIVE, label="Native 1.20.0"),
                        Line2D([], [], lw=9, color=OUR, label="Our Veortex V45")],
               loc="upper right", bbox_to_anchor=(.965, .847), frameon=False, ncol=2)
    panels = [(.255, .305, "Throughput", "successful HTTP requests/s", "successful_http_rps"),
              (.605, .165, "p95 latency", "ms, log scale; lower is better", "p95_ms"),
              (.815, .165, "p99 latency", "ms, log scale; lower is better", "p99_ms")]
    y = np.arange(4)
    for left, width, title, xlabel, key in panels:
        ax = fig.add_axes([left, .325, width, .44], facecolor=BG)
        for i in range(4):
            if i % 2 == 0:
                ax.axhspan(i-.45, i+.45, color="#eaf0f7", zorder=0)
        for engine, offset, color in (("native", -.17, NATIVE), ("veortex", .17, OUR)):
            values = [row(engine, cat, 1, 128)[key] for cat, _ in CATEGORIES]
            if key == "successful_http_rps":
                ax.barh(y+offset, values, height=.25, color=color, zorder=3)
            else:
                ax.scatter(values, y+offset, s=62, color=color, zorder=3)
            for pos, value in zip(y+offset, values):
                ax.annotate(f"{value:,.2f}", (value, pos), xytext=(6, 0),
                            textcoords="offset points", va="center", fontsize=10.5, color=color)
        ax.set_ylim(3.6, -.6)
        ax.set_yticks(y)
        ax.set_yticklabels([label for _, label in CATEGORIES] if key == "successful_http_rps" else [""]*4,
                           fontsize=12)
        if key == "successful_http_rps":
            ax.set_xlim(0, 3100)
            ax.set_xticks([0, 1000, 2000, 3000])
            ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
        else:
            ax.set_xscale("log")
            ax.set_xlim(40, 65000)
            ax.set_xticks([100, 1000, 10000], ["100", "1,000", "10,000"])
            ax.tick_params(axis="x", which="minor", bottom=False)
        clean_axis(ax)
        ax.set_title(title, loc="left", pad=17, fontsize=15, weight="bold")
        ax.set_xlabel(xlabel, labelpad=12, fontsize=10.5)
    fig.text(.055, .26, "C1 context: native is faster on these isolated-request rows", size=13, weight="bold")
    for i, (cat, _) in enumerate(CATEGORIES):
        n, v = row("native", cat, 1, 1), row("veortex", cat, 1, 1)
        fig.text(.055+i*.235, .227, ["No filter / no payload", "Payload only", "Active ~90% + payload", "Narrow ~9% + payload"][i],
                 size=10.5, color=MUTED)
        fig.text(.055+i*.235, .201, f"{n['successful_http_rps']:.2f} native  /  {v['successful_http_rps']:.2f} Our RPS", size=11)
    fig.text(.055, .145, "3 Docker nodes on one VM | 3 vCPUs/node: 1 compute + 2 support | metadata present in every case", size=11, color=MUTED)
    fig.text(.055, .116, "All displayed requests succeeded; ordered Top10 IDs matched exact FP32 truth (scores within 1e-6).", size=11, color=MUTED)
    fig.text(.055, .087, "60 s dispatch + drain; latency includes full response. C128 is loaded latency, not isolated-query latency or maximum capacity.", size=10, color=MUTED)
    fig.text(.055, .059, "End-to-end comparison: support-stage placement differs; compiler flags are unmatched. Synthetic Gaussian corpus; one campaign.", size=10, color=MUTED)
    fig.text(.055, .028, "Evidence: h2h-sq8-batch-20261109.json  |  github.com/nicabreon/qdrant-veortex-releases", size=10, color=MUTED)
    save(fig, "sq8-b1-c128-comparison")


def sweeps():
    fig, axes = plt.subplots(2, 4, figsize=(21, 12), facecolor=BG)
    fig.subplots_adjust(left=.065, right=.975, bottom=.22, top=.79, wspace=.26, hspace=.63)
    fig.text(.055, .95, "Concurrency and batching: all four request categories", size=26, weight="bold")
    fig.text(.055, .913, "SQ8 flat search | 3M x 512D | Top10 | 3 nodes x 3 vCPUs | 1 compute CPU + 2 support CPUs per node", size=13, color=MUTED)
    handles = [Line2D([], [], color=NATIVE, marker="o", lw=2.4, label="Native 1.20.0"),
               Line2D([], [], color=OUR, marker="o", lw=2.4, label="Our Veortex V45"),
               Line2D([], [], color=OUR, marker="D", markersize=8, linestyle="none", label="Our V45.1: B64 remediation")]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(.05, .894), ncol=3, frameon=False, fontsize=12)
    fig.text(.055, .845, "B1: concurrency sweep  /  successful HTTP requests per second", size=14, weight="bold")
    fig.text(.055, .45, "C4: explicit-batch sweep  /  validated queries per second (not HTTP requests/s)", size=14, weight="bold")
    for col, (category, label) in enumerate(CATEGORIES):
        ax = axes[0, col]
        concurrency = [1, 4, 32, 64, 128, 160]
        for engine, color in (("native", NATIVE), ("veortex", OUR)):
            values = [row(engine, category, 1, c)["successful_http_rps"] for c in concurrency]
            ax.plot(range(6), values, "o-", color=color, lw=2.3, ms=5)
            ax.annotate(f"{values[-1]:,.1f}", (5, values[-1]), xytext=(-4, 9),
                        textcoords="offset points", ha="right", color=color, fontsize=10, weight="bold")
        ax.set_title(label, fontsize=11.5, weight="bold", pad=12)
        ax.set_xticks(range(6), concurrency)
        ax.set_xlabel("Concurrent HTTP requests, C", fontsize=10)
        ax = axes[1, col]
        batches = [1, 4, 16, 32, 64]
        native = [row("native", category, b, 4)["query_qps"] for b in batches]
        old = [row("veortex", category, b, 4)["query_qps"] for b in batches[:-1]]
        candidate = row("veortex", category, 64, 4)
        ax.plot(range(5), native, "o-", color=NATIVE, lw=2.3, ms=5)
        ax.plot(range(4), old, "o-", color=OUR, lw=2.3, ms=5)
        ax.scatter([4], [candidate["query_qps"]], marker="D", s=90, color=OUR, zorder=5)
        ax.annotate(f"{candidate['query_qps']:,.1f} query/s", (4, candidate["query_qps"]),
                    xytext=(-4, 14), textcoords="offset points", ha="right", color=OUR, fontsize=10, weight="bold")
        ax.text(.03, .82, f"B64: {candidate['successful_http_rps']:.2f} HTTP req/s (remediated)",
                transform=ax.transAxes, color=OUR, fontsize=9.2)
        ax.annotate(f"{native[-1]:,.1f}", (4, native[-1]), xytext=(-4, 9),
                    textcoords="offset points", ha="right", color=NATIVE, fontsize=10, weight="bold")
        ax.set_xticks(range(5), batches)
        ax.set_xlabel("Queries per HTTP request, B", fontsize=10)
        for ax in axes[:, col]:
            ax.set_facecolor(BG)
            ax.set_xlim(-.25, 5.35 if ax is axes[0, col] else 4.4)
            ax.set_ylim(0, 3400)
            ax.set_yticks([0, 1000, 2000, 3000])
            ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:,.0f}"))
            clean_axis(ax)
            ax.grid(axis="y", color=GRID, linewidth=.7)
            ax.grid(axis="x", visible=False)
    fig.text(.055, .156, "B64 diamonds: separate V45.1 admission-remediation follow-up, 640 MiB queue cap. Native B64 baseline reused, not rerun.", size=12, color=MUTED)
    fig.text(.055, .126, "Other points: primary V45 campaign. Every displayed measurement passed with zero request failures and ordered Top10 IDs matching FP32.", size=11, color=MUTED)
    fig.text(.055, .096, "B = queries/request; C = in-flight HTTP requests. At B1, query/s = HTTP RPS. For a batch, query/s = B x HTTP RPS.", size=11, color=MUTED)
    fig.text(.055, .066, "Discrete settings use categorical spacing; lines guide the eye. 60 s dispatch + drain. Finite observations, not maximum capacity or long-run stability.", size=10.5, color=MUTED)
    fig.text(.055, .036, "Different support-stage placement; unmatched compiler flags. Sources: primary matrix + admission-remediation JSON (2026-11-09).", size=10.5, color=MUTED)
    save(fig, "sq8-concurrency-and-batch")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    overview()
    sweeps()
    assert len(selected) == 80
    assert sum(r["remediation"] for r in selected.values()) == 4
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=next(iter(selected.values())).keys(), lineterminator="\n")
    writer.writeheader()
    writer.writerows(sorted(selected.values(), key=lambda r: (r["category"], r["batch_size"], r["concurrency"], r["engine"])))
    (OUT / "chart-data-20261109.csv").write_text(output.getvalue())
    manifest = {
        "schema": "recorded_sq8_chart_selection_v1", "new_benchmarks_run": False,
        "source_sha256": {p.relative_to(ROOT).as_posix(): digest(p) for p in (PRIMARY, REMEDIATION)},
        "selected_measurements": len(selected), "remediated_measurements": 4,
        "selection": "Primary matrix except all four Our B64/C4 cells use successful V45.1 remediation; Native remains primary",
        "all_selected_rows_accepted": True, "all_selected_failed_request_counts_zero": True,
        "units": {"overview": "B1/C128 successful HTTP RPS and full-response p95/p99 milliseconds",
                  "sweeps_upper": "B1 successful HTTP RPS", "sweeps_lower": "C4 validated queries/s"},
        "renderer": {"matplotlib": matplotlib.__version__, "numpy": np.__version__},
        "output_sha256": {p.name: digest(p) for p in sorted(OUT.iterdir()) if p.suffix in (".png", ".svg", ".csv")},
    }
    (OUT / "chart-manifest-20261109.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"status": "rendered", "directory": str(OUT), "accepted_measurements": len(selected), "remediation_measurements": 4}))


if __name__ == "__main__":
    main()

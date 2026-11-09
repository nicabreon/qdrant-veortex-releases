#!/usr/bin/env python3
"""Draw the conceptual ring flow; does not execute or benchmark the engine."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "assets/architecture"
BG, INK, MUTED = "#f5f8fc", "#152b43", "#52677c"
BLUE, ORANGE, GREEN = "#31659b", "#cb641b", "#247a60"
plt.rcParams.update({"font.family": "DejaVu Sans", "svg.fonttype": "none",
                     "svg.hashsalt": "veortex-ring-flow-v1"})
fig, ax = plt.subplots(figsize=(18.4, 12.4), facecolor=BG)
fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
ax.set(xlim=(0, 18.4), ylim=(0, 12.4))
ax.axis("off")


def text(x, y, value, size=12, color=INK, weight="normal", ha="left", va="center"):
    return ax.text(x, y, value, fontsize=size, color=color, weight=weight,
                   ha=ha, va=va, linespacing=1.45, zorder=5)


def box(x, y, w, h, fill, edge="#dce5ee", radius=.12, lw=1):
    p = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={radius}",
                      facecolor=fill, edgecolor=edge, linewidth=lw, zorder=1)
    ax.add_patch(p)
    return p


def arrow(start, end, color=MUTED, style="-|>", curve=0, lw=1.7):
    p = FancyArrowPatch(start, end, arrowstyle=style, mutation_scale=14,
                        linewidth=lw, color=color, zorder=3,
                        connectionstyle=f"arc3,rad={curve}")
    ax.add_patch(p)


def card(x, y, w, h, title, subtitle="", color=BLUE):
    box(x, y, w, h, "#ffffff", edge="#d8e3ee")
    text(x+w/2, y+h*.65 if subtitle else y+h/2, title, 12, color, "bold", "center")
    if subtitle:
        text(x+w/2, y+h*.30, subtitle, 10.3, MUTED, ha="center")


text(.65, 11.74, "Continuous batching across independent requests", 27, weight="bold")
text(.65, 11.18, "A per-shard query ring connects shared gallery reads to a pipelined search path.",
     14, MUTED)

# Independent requests retain their external API boundaries.
box(.6, 7.85, 3.7, 2.65, "#eaf1f9")
text(.88, 10.13, "1 / Independent requests", 14, BLUE, "bold")
for y, label in [(9.58, "Request A  |  B1"), (8.98, "Request B  |  B1"),
                 (8.38, "Request C  |  B4")]:
    box(.9, y-.21, 3.1, .43, "#ffffff", radius=.07)
    text(2.45, y, label, 12, BLUE, ha="center")

arrow((4.37, 9.1), (4.78, 9.1), BLUE)
box(4.85, 7.85, 3.6, 2.65, "#eaf1f9")
text(5.13, 10.13, "2 / Bounded admission", 14, BLUE, "bold")
text(6.65, 9.37, "Compatibility checks\nQueue + resource limits", 12, ha="center")
for i, label in enumerate(("Q4", "Q5", "Q6")):
    box(5.22+i*.96, 8.33, .77, .45, "#ffffff", radius=.06)
    text(5.605+i*.96, 8.555, label, 11, BLUE, ha="center")
text(6.65, 8.02, "Wait / reject when capacity is exhausted", 9.4, MUTED, ha="center")
arrow((8.52, 9.1), (8.93, 9.1), BLUE)

# Four displayed lanes are an illustration, not the configured ring capacity.
box(9, 7.85, 8.8, 2.65, "#eaf1f9")
text(9.3, 10.13, "3 / Dynamic query ring", 14, BLUE, "bold")
text(9.3, 9.73, "Admit at tile boundaries when slots and resources allow", 11, MUTED)
for y, label, lanes in [(9.12, "Tile t", ("Q1", "Q2", "Q3", "free")),
                         (8.47, "Tile t+1", ("Q4 new", "Q2", "Q3", "Q5 new"))]:
    text(9.3, y, label, 11, MUTED)
    for i, lane in enumerate(lanes):
        x = 10.73+i*1.48
        new, empty = "new" in lane, lane == "free"
        fill = "#e2f2e9" if new else (BG if empty else "#ffffff")
        edge = GREEN if new else "#c4d4e5"
        box(x, y-.23, 1.25, .46, fill, edge, radius=.06)
        text(x+.625, y, lane, 10.3, GREEN if new else BLUE, "bold" if new else "normal", "center")
text(9.3, 8.02, "Q1 finishes its scan; Q2/Q3 continue. Example slots only.", 10.1, MUTED)

# The active query group consumes shared gallery tiles on the scan CPU.
box(.6, 4.65, 4.0, 2.45, "#fff3e8")
text(.9, 6.71, "Gallery tile stream", 14, ORANGE, "bold")
for i, label in enumerate(("t-1", "t", "t+1", "...")):
    x = .95+i*.84
    box(x, 5.77, .65, .47, "#fde2c9" if i == 1 else "#ffffff", ORANGE if i == 1 else "#ead8c8", radius=.06)
    text(x+.325, 6.005, label, 11, ORANGE, ha="center")
text(.9, 5.36, "Load / prefetch gallery tiles", 11, MUTED)
text(.9, 4.99, "Reuse each loaded tile across queries", 10.6, MUTED)
arrow((4.67, 5.82), (5.13, 5.82), ORANGE)

box(5.2, 4.65, 7.25, 2.45, "#fff3e8", edge="#ecc8a8")
text(5.5, 6.72, "4 / Scan + multi-query scoring", 14, ORANGE, "bold")
box(10.55, 6.09, 1.55, .39, "#fde2c9", edge="#ecc8a8", radius=.05)
text(11.325, 6.285, "1 compute CPU", 10.2, ORANGE, "bold", "center")
text(5.5, 6.18, "SIMD; AMX when available / eligible", 11.5, weight="bold")
text(5.5, 5.64, "Tiling + cache reuse + prefetching", 12, MUTED)
text(5.5, 5.12, "One gallery tile x active query lanes -> score tiles", 11, MUTED)
arrow((12.9, 7.78), (10.2, 7.16), BLUE)
text(10.0, 7.49, "active queries", 10.3, BLUE)

box(13.15, 4.65, 4.65, 2.45, "#ffffff")
text(13.45, 6.71, "Per-query scan progress", 13.5, BLUE, "bold")
text(13.45, 5.87, "Start at the admission tile;\ncomplete one full tile revolution.", 11.4)
text(13.45, 5.06, "Wrap at segment end; then release the slot.", 9.5, MUTED)
arrow((12.52, 5.85), (13.08, 5.85), ORANGE)
arrow((16.55, 7.15), (16.55, 7.78), GREEN)
text(16.1, 7.46, "release / refill", 10.1, GREEN, ha="right")

# Logical completion stages share the two support CPUs. TopK can consume
# score tiles during scanning; rerank waits for this query's scan coverage.
box(.6, 1.40, 17.2, 2.45, "#eaf4ee", edge="#c9dfd2")
text(.95, 3.53, "2 support CPUs", 11.5, GREEN, "bold")
text(6.0, 3.53, "5 / Pipelined completion", 14, GREEN, "bold")
card(1.0, 1.96, 4.1, 1.10, "Threshold filtering -> TopK", "Consume score tiles", GREEN)
card(5.75, 1.96, 3.45, 1.10, "FP32 rerank", "After this query's scan", GREEN)
card(9.85, 1.96, 3.0, 1.10, "Payload", "Materialize selected results", GREEN)
card(13.5, 1.96, 3.9, 1.10, "Qdrant response", "Original request boundaries", GREEN)
for left, right in ((5.16, 5.68), (9.26, 9.78), (12.91, 13.43)):
    arrow((left, 2.51), (right, 2.51), GREEN)
ax.plot([8.7, 8.7, 3.05], [4.58, 4.23, 4.23], color=GREEN, lw=1.7, zorder=3)
arrow((3.05, 4.23), (3.05, 3.12), GREEN)
text(4.95, 4.39, "score tiles", 10.4, GREEN)
text(.95, 1.64, "Completed queries can progress here while others scan. Bounded handoff may apply backpressure.", 11, MUTED)

text(.65, .91, "Goal: reduce amortized gallery-read traffic per completed query while keeping the pipeline productive.",
     12, weight="bold")
text(.65, .52, "Eligible single-segment quantized flat path. Reference profile: 3 vCPUs/node with offload enabled. Slots shown are illustrative.", 10.1, MUTED)
text(.65, .20, "No throughput or memory-bandwidth claim is implied. Qdrant retains its API, shard routing, persistence and clustering.", 10.2, MUTED)

OUT.mkdir(parents=True, exist_ok=True)
for suffix in ("png", "svg"):
    path = OUT / f"continuous-query-ring.{suffix}"
    meta = {"Date": None} if suffix == "svg" else {"Software": "Matplotlib; conceptual ring architecture"}
    fig.savefig(path, dpi=170, facecolor=BG, metadata=meta)
    if suffix == "svg":
        path.write_text("\n".join(line.rstrip() for line in path.read_text().splitlines()) + "\n")
plt.close(fig)
print(OUT / "continuous-query-ring.png")

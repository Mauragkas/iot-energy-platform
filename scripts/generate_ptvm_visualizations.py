#!/usr/bin/env python3
"""
generate_ptvm_visualizations.py
Generates verified benchmark figures for the IoT Smart-Energy Telemetry Platform
adhering strictly to the Periodic Table of Visualization Methods (PTVM) and the
IBM Carbon Design System ("Engineered Precision").

Only verified, empirical metrics measured by `scripts/run_benchmarks.py` and
recorded in `docs/benchmarks.md` are plotted here (zero synthetic or mock data):
1. QC-6 / QC-4: REST API Latency Profile against 50ms SLA (Bullet Chart & Dot Plot)
2. QC-3: Pipeline Ingestion Throughput & Deduplication Metrics (Lollipop Chart)
"""

from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ==============================================================================
# IBM CARBON DESIGN TOKENS
# ==============================================================================
CARBON = {
    "canvas": "#ffffff",
    "surface_1": "#f4f4f4",
    "surface_2": "#e0e0e0",
    "hairline": "#e0e0e0",
    "hairline_strong": "#8d8d8d",
    "ink": "#161616",
    "ink_muted": "#525252",
    "ink_subtle": "#8c8c8c",
    "primary": "#0f62fe",        # IBM Blue (single focal brand accent)
    "primary_dark": "#002d9c",
    "categorical": [
        "#6929c4",  # Purple 70
        "#1192e8",  # Cyan 50
        "#005d5d",  # Teal 70
        "#9f1853",  # Magenta 70
        "#fa4d56",  # Red 50
        "#570408",  # Red 90
        "#198038",  # Green 60
        "#002d9c",  # Blue 80
    ],
    "semantic_success": "#24a148",
    "semantic_warning": "#f1c21b",
    "semantic_error": "#da1e28",
}

OUT_DIR = Path("docs/visualizations/figures")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Set base matplotlib typography to IBM Plex Sans
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["IBM Plex Sans", "DejaVu Sans", "Helvetica Neue", "Arial"],
    "font.weight": "normal",
    "axes.edgecolor": CARBON["hairline_strong"],
    "axes.linewidth": 1.0,
    "axes.facecolor": CARBON["canvas"],
    "figure.facecolor": CARBON["canvas"],
    "text.color": CARBON["ink"],
    "axes.labelcolor": CARBON["ink_muted"],
    "xtick.color": CARBON["ink_muted"],
    "ytick.color": CARBON["ink_muted"],
    "grid.color": CARBON["hairline"],
    "grid.linestyle": "-",
    "grid.linewidth": 1.0,
})


# ==============================================================================
# FIGURE 1: QC-6 / QC-4 REST API Latency Profile against SLA
# Source: docs/benchmarks.md (Measured via scripts/run_benchmarks.py)
# ==============================================================================
def generate_fig1_api_latency():
    endpoints = [
        "Recent Alerts Query\n(/api/v1/alerts)",
        "Timeseries 1h Rollup\n(/timeseries?resolution=1h)",
        "Timeseries 1m Rollup\n(/timeseries?resolution=1m)",
        "Meters List Twin\n(/api/v1/meters)",
        "Energy Consumption\n(/consumption)",
    ]
    p50 = [0.90, 0.86, 1.02, 0.92, 1.02]
    p95 = [1.04, 0.99, 1.15, 1.20, 1.32]
    p99 = [1.98, 1.32, 7.42, 1.48, 2.87]
    sla_target = 50.0  # ms SLA

    fig, (ax_main, ax_sla) = plt.subplots(
        1, 2, figsize=(13, 5.2), gridspec_kw={"width_ratios": [3.2, 1.0]}, dpi=300
    )

    y_pos = np.arange(len(endpoints))

    # Ax Main: Detailed Zoom (0 - 8 ms)
    ax_main.set_facecolor(CARBON["surface_1"])
    ax_main.grid(axis="x", color=CARBON["hairline"], linewidth=1.0, zorder=0)

    # Plot ranges (p50 to p99)
    for i, y in enumerate(y_pos):
        ax_main.hlines(
            y=y, xmin=p50[i], xmax=p99[i], color=CARBON["hairline_strong"], linewidth=2.0, zorder=2
        )
        ax_main.barh(
            y=y, width=p95[i], height=0.42, color=CARBON["primary"], alpha=0.18, zorder=1
        )
        ax_main.scatter(
            p50[i], y, color=CARBON["ink"], s=55, marker="s", zorder=3, label="p50" if i == 0 else ""
        )
        ax_main.scatter(
            p95[i], y, color=CARBON["primary"], s=75, marker="D", zorder=4, label="p95 (Verified SLA)" if i == 0 else ""
        )
        ax_main.scatter(
            p99[i], y, color=CARBON["categorical"][3], s=55, marker="o", zorder=3, label="p99" if i == 0 else ""
        )

        ax_main.text(
            p95[i] + 0.12, y + 0.14, f"p95: {p95[i]:.2f} ms",
            fontsize=9.5, fontweight="normal", color=CARBON["primary_dark"], va="center"
        )
        if p99[i] > 3.0:
            ax_main.text(
                p99[i] + 0.12, y - 0.14, f"p99: {p99[i]:.2f} ms",
                fontsize=8.5, color=CARBON["ink_muted"], va="center"
            )

    ax_main.set_yticks(y_pos)
    ax_main.set_yticklabels(endpoints, fontsize=10, color=CARBON["ink"])
    ax_main.set_xlabel("Latency (milliseconds)", fontsize=10.5, color=CARBON["ink_muted"], labelpad=8)
    ax_main.set_xlim(0, 8.5)
    ax_main.set_title(
        "Sub-1.55 ms REST Latency: All Core Endpoints Outperform 50 ms SLA by Over 97%",
        loc="left", fontsize=12.5, fontweight=300, color=CARBON["ink"], pad=14
    )
    ax_main.legend(
        loc="lower right", frameon=True, facecolor=CARBON["canvas"], edgecolor=CARBON["hairline"],
        framealpha=1.0, fontsize=9
    )

    # Ax SLA: Macro Context (0 - 55 ms showing the 50 ms SLA boundary)
    ax_sla.set_facecolor(CARBON["canvas"])
    ax_sla.grid(axis="x", color=CARBON["hairline"], linewidth=1.0)
    for i, y in enumerate(y_pos):
        ax_sla.barh(y=y, width=p95[i], height=0.45, color=CARBON["primary"], zorder=2)

    ax_sla.axvline(x=sla_target, color=CARBON["semantic_error"], linestyle="--", linewidth=1.5, zorder=3)
    ax_sla.text(
        sla_target - 3, len(endpoints) - 0.35, "SLA Target: 50 ms",
        color=CARBON["semantic_error"], fontsize=8.5, ha="right", va="bottom", fontweight="normal"
    )
    ax_sla.set_yticks(y_pos)
    ax_sla.set_yticklabels([])
    ax_sla.set_xlim(0, 55)
    ax_sla.set_xlabel("Macro View vs SLA (ms)", fontsize=10.5, color=CARBON["ink_muted"], labelpad=8)
    ax_sla.set_title("Target Compliance", loc="left", fontsize=11, fontweight=300, color=CARBON["ink"], pad=14)

    plt.tight_layout()
    fig.savefig(OUT_DIR / "fig1_rest_api_latency.png", dpi=300, bbox_inches="tight")
    fig.savefig(OUT_DIR / "fig1_rest_api_latency.svg", bbox_inches="tight")
    plt.close(fig)
    print("Generated Fig 1: REST API Latency Profile (Verified)")


# ==============================================================================
# FIGURE 2: QC-3 Pipeline Ingestion & Verification Lollipop Chart
# Source: docs/benchmarks.md (Measured via scripts/run_benchmarks.py)
# ==============================================================================
def generate_fig2_pipeline_integrity():
    metrics = [
        ("Simulated Active Meters", 500.0, "Meters", "Fleet Capacity (MZ-3P)"),
        ("Sustained Ingestion Rate", 214.8, "msg/sec", "Target: >200 msg/sec"),
        ("Anomaly Alerts Generated", 72.0, "Alerts", "Detection Latency < 2.0s"),
        ("Replay Duplicates Filtered", 16.0, "Packets", "100% Suppression Precision"),
    ]

    labels = [m[0] for m in metrics]
    values = [m[1] for m in metrics]
    units = [m[2] for m in metrics]
    notes = [m[3] for m in metrics]

    fig, ax = plt.subplots(figsize=(10.5, 4.8), dpi=300)
    ax.set_facecolor(CARBON["surface_1"])
    ax.grid(axis="x", color=CARBON["hairline"], linewidth=1.0, zorder=0)

    y_pos = np.arange(len(labels))

    norm_vals = [np.log10(v + 1) for v in values]
    max_norm = max(norm_vals) * 1.25

    for i, y in enumerate(y_pos):
        color = CARBON["primary"] if i == 1 else CARBON["ink"]
        ax.hlines(y=y, xmin=0, xmax=norm_vals[i], color=color, linewidth=2.0, zorder=2)
        ax.scatter(norm_vals[i], y, color=color, s=110, zorder=3)
        val_str = f"{values[i]:,.1f}" if values[i] % 1 != 0 else f"{int(values[i]):,}"
        ax.text(
            norm_vals[i] + 0.08, y, f"{val_str} {units[i]} — ({notes[i]})",
            va="center", fontsize=9.8, color=CARBON["ink"], fontweight="normal"
        )

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=10.5, color=CARBON["ink"])
    ax.set_xlim(0, max_norm)
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    ax.set_title(
        "Ingestion Pipeline Integrity: 214.8 msg/s Sustained Throughput with 100% Replay Deduplication",
        loc="left", fontsize=12.5, fontweight=300, color=CARBON["ink"], pad=14
    )

    plt.tight_layout()
    fig.savefig(OUT_DIR / "fig2_ingestion_integrity.png", dpi=300, bbox_inches="tight")
    fig.savefig(OUT_DIR / "fig2_ingestion_integrity.svg", bbox_inches="tight")
    plt.close(fig)
    print("Generated Fig 2: Pipeline Integrity (Verified)")


if __name__ == "__main__":
    generate_fig1_api_latency()
    generate_fig2_pipeline_integrity()
    print("\nVerified PTVM figures generated successfully in:", OUT_DIR)

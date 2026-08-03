"""Result-figure generation.

Regenerates the project's key result figures from the existing experiment
functions and saves them as PNGs into results/figures/ (tracked despite
results/ otherwise being gitignored -- see .gitignore's explicit
exception). This module only plots; it doesn't compute anything the
experiments modules don't already compute.

Deterministic-step figures (beta sweep, AA trajectories) use the
full-horizon convention from experiments/sweeps.py; stochastic figures
(mitigation, position sensitivity) use the post-warmup, 20-seed-averaged
convention from experiments/stochastic.py. See those modules' docstrings
for why the two demand regimes need different metrics -- each figure
labels which regime it's from so the two are never confused.

Style: one light-mode palette (validated categorical hues, fixed chart
chrome) applied consistently across all four figures -- categorical colors
assigned by fixed slot order rather than per-chart choice, one axis per
chart (small multiples instead of dual-axis), a legend on every
multi-series chart, and mean +/- std error bars (CLAUDE.md's reporting
convention) wherever seeds are aggregated.
"""

import os

import matplotlib.pyplot as plt
import numpy as np

from agents.anchor_adjust import make_anchor_and_adjust_agents
from env.config import ECHELON_NAMES, SimulationConfig
from env.demand import step_demand
from env.engine import BeerGameEngine
from experiments.stochastic import (
    run_information_sharing_experiment_stochastic,
    run_position_sensitivity_experiment_stochastic,
)
from experiments.sweeps import run_beta_sweep

FIGURES_DIR = os.path.join("results", "figures")
DPI = 150

# Validated default palette (see dataviz skill references/palette.md);
# categorical slots used in fixed order, never re-picked per chart.
SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
AXIS = "#c3c2b7"
CATEGORICAL = [
    "#2a78d6",  # 1 blue
    "#eb6834",  # 2 orange
    "#1baf7a",  # 3 aqua
    "#eda100",  # 4 yellow
    "#e87ba4",  # 5 magenta
    "#008300",  # 6 green
    "#4a3aa7",  # 7 violet
    "#e34948",  # 8 red
]

plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["Helvetica", "Arial", "DejaVu Sans"]


def _style_axes(ax) -> None:
    ax.set_facecolor(SURFACE)
    ax.figure.set_facecolor(SURFACE)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color(AXIS)
    ax.tick_params(colors=INK_SECONDARY, labelsize=9)
    ax.yaxis.grid(True, color=GRIDLINE, linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    ax.xaxis.label.set_color(INK_SECONDARY)
    ax.yaxis.label.set_color(INK_SECONDARY)
    ax.title.set_color(INK_PRIMARY)


def _save(fig, filename: str) -> str:
    os.makedirs(FIGURES_DIR, exist_ok=True)
    path = os.path.join(FIGURES_DIR, filename)
    fig.savefig(path, dpi=DPI, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)
    return path


def _add_header(fig, title: str, subtitle: str) -> None:
    """Bold title + muted italic subtitle, placed above the axes rather
    than inside the plot area -- keeps them clear of the data (and any
    legend) regardless of what the data does, unlike an in-axes ax.text
    annotation. Used identically by every figure in this module."""
    fig.suptitle(title, fontsize=13, fontweight="bold", color=INK_PRIMARY, x=0.02, ha="left")
    fig.text(0.02, 0.92, subtitle, fontsize=8.5, color=INK_MUTED, style="italic")


def figure_beta_sweep() -> str:
    """Headline result: bullwhip ratio vs. beta, deterministic step demand,
    full horizon (experiments/sweeps.py's run_beta_sweep)."""
    results = run_beta_sweep()
    summary = results.groupby("beta")["bullwhip_ratio"].mean()

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(
        summary.index,
        summary.values,
        color=CATEGORICAL[0],
        linewidth=2,
        marker="o",
        markersize=7,
        markerfacecolor=CATEGORICAL[0],
        markeredgecolor=SURFACE,
        markeredgewidth=1.5,
        zorder=3,
    )
    ax.set_yscale("log")
    ax.set_xlabel("beta (supply-line weighting)")
    ax.set_ylabel("Bullwhip ratio\n(Var(Factory orders) / Var(customer demand))")
    _style_axes(ax)
    _add_header(
        fig,
        "Bullwhip collapses as agents credit the supply line",
        "deterministic step demand (4 to 8 units/wk) · full-horizon variance · anchor-and-adjust agents",
    )
    fig.tight_layout(rect=[0, 0, 1, 0.91])
    return _save(fig, "01_beta_sweep.png")


def figure_anchor_adjust_trajectories() -> str:
    """Order trajectories for all four echelons, canonical anchor-and-adjust
    (beta=0.25) run, deterministic step demand -- the Day-3 Sterman
    reproduction, showing amplification up the chain."""
    config = SimulationConfig()
    agents = make_anchor_and_adjust_agents(config)
    engine = BeerGameEngine(config, agents, step_demand)
    df = engine.run()

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.axhline(8, color=AXIS, linewidth=1, linestyle="--", zorder=1)
    for i, echelon in enumerate(ECHELON_NAMES):
        series = df[df["echelon"] == echelon].sort_values("week")
        ax.plot(
            series["week"],
            series["order_placed"],
            color=CATEGORICAL[i],
            linewidth=2,
            label=echelon,
            zorder=3,
        )
    ax.set_xlabel("week")
    ax.set_ylabel("order placed (units/week)")
    legend = ax.legend(frameon=False, loc="upper right", fontsize=9, labelcolor=INK_SECONDARY)
    _style_axes(ax)
    _add_header(
        fig,
        "Amplification up the chain: anchor-and-adjust after the demand step",
        "deterministic step demand (4 to 8 units/wk at week 5) · beta=0.25, theta=0.3, alpha=0.25 · dashed line = steady demand",
    )
    fig.tight_layout(rect=[0, 0, 1, 0.91])
    return _save(fig, "02_anchor_adjust_trajectories.png")


def figure_mitigation() -> str:
    """Information-sharing mitigation, 2x2 (agent type x forecast
    condition), stochastic demand, 20 seeds, mean +/- std
    (experiments/stochastic.py's run_information_sharing_experiment_stochastic)."""
    results = run_information_sharing_experiment_stochastic()
    summary = results.groupby(["agent_type", "condition"])["bullwhip_ratio"].agg(["mean", "std"])

    agent_types = ["base_stock", "anchor_and_adjust"]
    agent_labels = ["Base-stock", "Anchor-and-adjust"]
    conditions = ["baseline", "info_sharing"]
    condition_labels = {"baseline": "Baseline (local forecast)", "info_sharing": "Info-sharing (true demand)"}
    colors = {"baseline": CATEGORICAL[0], "info_sharing": CATEGORICAL[1]}

    x = np.arange(len(agent_types))
    width = 0.32
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for i, condition in enumerate(conditions):
        means = [summary.loc[(a, condition), "mean"] for a in agent_types]
        stds = [summary.loc[(a, condition), "std"] for a in agent_types]
        offset = (i - 0.5) * width
        ax.bar(
            x + offset,
            means,
            width,
            yerr=stds,
            capsize=4,
            color=colors[condition],
            label=condition_labels[condition],
            error_kw={"ecolor": INK_SECONDARY, "elinewidth": 1.2},
            zorder=3,
        )
    ax.set_yscale("log")
    top = max(m + s for m, s in zip(summary["mean"], summary["std"]))
    bottom = min(m - s for m, s in zip(summary["mean"], summary["std"]))
    ax.set_ylim(bottom / 1.8, top * 2.2)  # headroom so error-bar caps never touch the legend/ceiling
    ax.set_xticks(x)
    ax.set_xticklabels(agent_labels)
    ax.set_ylabel("Bullwhip ratio (post-warmup)")
    # Base-stock's bars are much shorter than anchor-and-adjust's, so the
    # legend sits over empty space here rather than over a tall bar.
    legend = ax.legend(frameon=False, loc="upper left", fontsize=9, labelcolor=INK_SECONDARY)
    _style_axes(ax)
    _add_header(
        fig,
        "Info-sharing helps base-stock far more than anchor-and-adjust",
        "stochastic demand N(8, 2) · 20 seeds, mean ± std · beta=0.25 for anchor-and-adjust",
    )
    fig.tight_layout(rect=[0, 0, 1, 0.91])
    return _save(fig, "03_mitigation_stochastic.png")


def figure_position_sensitivity() -> str:
    """Position sensitivity: team cost and Factory bullwhip by which
    position gets the single rational (base-stock) agent, stochastic
    demand, 20 seeds, mean +/- std
    (experiments/stochastic.py's run_position_sensitivity_experiment_stochastic)."""
    results = run_position_sensitivity_experiment_stochastic()
    metrics = ["team_cost", "bullwhip_Factory"]
    summary = results.groupby("config")[metrics].agg(["mean", "std"])

    order = [
        "baseline (all anchor-and-adjust)",
        "base-stock at Retailer",
        "base-stock at Wholesaler",
        "base-stock at Distributor",
        "base-stock at Factory",
    ]
    short_labels = ["baseline\n(all AA)", "Retailer", "Wholesaler", "Distributor", "Factory"]
    bar_colors = [CATEGORICAL[6]] + [CATEGORICAL[0]] * 4  # baseline (violet) vs. base-stock-at-position (blue)

    panel_titles = ["Total team cost (post-warmup)", "Factory bullwhip ratio (post-warmup)"]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    for ax, metric, title in zip(axes, metrics, panel_titles):
        means = [summary.loc[c, (metric, "mean")] for c in order]
        stds = [summary.loc[c, (metric, "std")] for c in order]
        x = np.arange(len(order))
        ax.bar(
            x,
            means,
            yerr=stds,
            capsize=4,
            color=bar_colors,
            width=0.6,
            error_kw={"ecolor": INK_SECONDARY, "elinewidth": 1.2},
            zorder=3,
        )
        ax.set_xticks(x)
        ax.set_xticklabels(short_labels, fontsize=8)
        ax.set_title(title, fontsize=10.5, color=INK_PRIMARY)
        _style_axes(ax)

    baseline_patch = plt.Rectangle((0, 0), 1, 1, color=CATEGORICAL[6])
    position_patch = plt.Rectangle((0, 0), 1, 1, color=CATEGORICAL[0])
    fig.legend(
        [baseline_patch, position_patch],
        ["baseline (all anchor-and-adjust)", "single base-stock agent at the labeled position"],
        loc="lower center",
        ncol=2,
        frameon=False,
        fontsize=9,
        labelcolor=INK_SECONDARY,
        bbox_to_anchor=(0.5, -0.02),
    )
    _add_header(
        fig,
        "Retailer-placement wins on both cost and bullwhip",
        "stochastic demand N(8, 2) · 20 seeds, mean ± std",
    )
    fig.tight_layout(rect=[0, 0.06, 1, 0.86])
    return _save(fig, "04_position_sensitivity_stochastic.png")


def generate_all() -> list:
    return [
        figure_beta_sweep(),
        figure_anchor_adjust_trajectories(),
        figure_mitigation(),
        figure_position_sensitivity(),
    ]


if __name__ == "__main__":
    for path in generate_all():
        print(f"saved {path}")

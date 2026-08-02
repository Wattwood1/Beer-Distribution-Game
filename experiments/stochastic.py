"""Beta sweep, information-sharing mitigation, and position-sensitivity
experiments re-run under stochastic demand — N(mu=8, sigma=2) truncated at
0 (env.demand.make_stochastic_demand) — with a real 20-seed loop.

These are new result sets ALONGSIDE the deterministic-step versions in
experiments/sweeps.py, experiments/mitigations.py, and
experiments/heterogeneous.py, not replacements. Bullwhip ratios here use
bullwhip_ratio_post_warmup, not sweeps.py's bullwhip_ratio: under
stochastic demand the full-horizon window is contaminated by an
empty-pipeline startup transient (confirmed in
tests/test_analytical_stochastic.py — the known-demand base-stock
benchmark, which should read ~1.0, reads ~7.4 full-horizon vs. ~1.0
post-warmup across 20 seeds), whereas under the deterministic step the
reverse holds (post-warmup is undefined — the step falls inside warmup, so
post-warmup customer demand has zero variance). Each demand regime has
exactly one defined/uncontaminated metric; this module always uses the one
that's valid for stochastic demand. Ratios here are NOT comparable in scale
to the deterministic-step numbers (real demand variance now exists as the
denominator throughout) — only the qualitative findings (does bullwhip
still decline with beta, does the mitigation still show synergy, does
Retailer-placement still win) are meant to be compared.

Seed pairing: every condition compared resets np.random.seed(seed)
immediately before building agents and running the engine, before any
other randomness could be consumed. Since nothing else in this codebase
draws from the global RNG, this guarantees bit-identical demand
realizations across conditions for a given seed — differences in the
reported metrics reflect the policy/position/beta difference, not
differing demand luck.
"""

from typing import Iterable, Optional

import numpy as np
import pandas as pd

from agents.anchor_adjust import make_anchor_and_adjust_agents
from agents.base_stock import make_base_stock_agents
from env.config import ECHELON_NAMES, SimulationConfig
from env.demand import make_stochastic_demand
from env.engine import BeerGameEngine
from experiments.learned_policy import post_warmup_team_cost
from experiments.sweeps import bullwhip_ratio_post_warmup

MU = 8.0
SIGMA = 2.0
SEEDS = range(20)


def run_beta_sweep_stochastic(
    betas: Iterable[float] = tuple(np.round(np.arange(0.0, 1.01, 0.1), 2)),
    seeds: Iterable[int] = SEEDS,
    theta: float = 0.3,
    alpha: float = 0.25,
    config: Optional[SimulationConfig] = None,
) -> pd.DataFrame:
    """Sweep beta (supply-line weighting) under stochastic demand; one row
    per (beta, seed). Mirrors experiments/sweeps.py's run_beta_sweep."""
    config = config or SimulationConfig()
    rows = []
    for beta in betas:
        for seed in seeds:
            np.random.seed(seed)
            agents = make_anchor_and_adjust_agents(config, theta=theta, alpha=alpha, beta=beta)
            demand_fn = make_stochastic_demand(mu=MU, sigma=SIGMA)
            engine = BeerGameEngine(config, agents, demand_fn)
            df = engine.run()
            rows.append(
                {"beta": beta, "seed": seed, "bullwhip_ratio": bullwhip_ratio_post_warmup(df, config)}
            )
    return pd.DataFrame(rows)


def run_information_sharing_experiment_stochastic(
    seeds: Iterable[int] = SEEDS,
    beta: float = 0.25,
    theta: float = 0.3,
    alpha: float = 0.25,
    config: Optional[SimulationConfig] = None,
) -> pd.DataFrame:
    """Mirrors experiments/mitigations.py's run_information_sharing_experiment.
    "Information sharing" here means the forecast source switches from the
    local incoming-order signal to the TRUE demand mean (MU) — the natural
    stochastic-demand analogue of being told the true rate directly, same
    as the deterministic version's TRUE_DEMAND_RATE."""
    config = config or SimulationConfig()
    rows = []
    for seed in seeds:
        conditions = {
            "baseline": {"expected_demand_per_week": None},
            "info_sharing": {"expected_demand_per_week": MU},
        }
        agent_builders = {
            "base_stock": lambda **kw: make_base_stock_agents(config, **kw),
            "anchor_and_adjust": lambda **kw: make_anchor_and_adjust_agents(
                config, theta=theta, alpha=alpha, beta=beta, **kw
            ),
        }
        for agent_type, build in agent_builders.items():
            for condition, kwargs in conditions.items():
                np.random.seed(seed)
                agents = build(**kwargs)
                demand_fn = make_stochastic_demand(mu=MU, sigma=SIGMA)
                engine = BeerGameEngine(config, agents, demand_fn)
                df = engine.run()
                rows.append(
                    {
                        "agent_type": agent_type,
                        "condition": condition,
                        "seed": seed,
                        "bullwhip_ratio": bullwhip_ratio_post_warmup(df, config),
                    }
                )
    return pd.DataFrame(rows)


def per_echelon_bullwhip_ratios_post_warmup(df: pd.DataFrame, config: SimulationConfig) -> dict:
    """Var(orders_i) / Var(customer demand), post-warmup, for every echelon
    — the stochastic-demand analogue of heterogeneous.py's
    per_echelon_bullwhip_ratios (full-horizon, correct for step demand)."""
    settled = df[df["week"] > config.warmup_weeks]
    customer_demand_var = settled.loc[settled["echelon"] == "Retailer", "order_received"].var()
    return {
        echelon: settled.loc[settled["echelon"] == echelon, "order_placed"].var() / customer_demand_var
        for echelon in ECHELON_NAMES
    }


def run_position_sensitivity_experiment_stochastic(
    seeds: Iterable[int] = SEEDS, config: Optional[SimulationConfig] = None
) -> pd.DataFrame:
    """Mirrors experiments/heterogeneous.py's run_position_sensitivity_experiment;
    one row per (config, seed)."""
    config = config or SimulationConfig()
    labels_and_swaps = [("baseline (all anchor-and-adjust)", None)] + [
        (f"base-stock at {echelon}", i) for i, echelon in enumerate(ECHELON_NAMES)
    ]

    rows = []
    for label, swap_index in labels_and_swaps:
        for seed in seeds:
            np.random.seed(seed)
            agents = make_anchor_and_adjust_agents(config)
            if swap_index is not None:
                base_stock_agents = make_base_stock_agents(config)
                agents[swap_index] = base_stock_agents[swap_index]

            demand_fn = make_stochastic_demand(mu=MU, sigma=SIGMA)
            engine = BeerGameEngine(config, agents, demand_fn)
            df = engine.run()

            ratios = per_echelon_bullwhip_ratios_post_warmup(df, config)
            row = {"config": label, "seed": seed, "team_cost": post_warmup_team_cost(df, config)}
            row.update({f"bullwhip_{echelon}": ratios[echelon] for echelon in ECHELON_NAMES})
            rows.append(row)

    return pd.DataFrame(rows)


if __name__ == "__main__":
    pd.set_option("display.width", 200)

    print("=== Beta sweep (stochastic demand) ===")
    beta_results = run_beta_sweep_stochastic()
    print(beta_results.groupby("beta")["bullwhip_ratio"].agg(["mean", "std"]))
    print()

    print("=== Information-sharing mitigation (stochastic demand) ===")
    mitigation_results = run_information_sharing_experiment_stochastic()
    print(mitigation_results.groupby(["agent_type", "condition"])["bullwhip_ratio"].agg(["mean", "std"]))
    print()

    print("=== Position sensitivity (stochastic demand) ===")
    position_results = run_position_sensitivity_experiment_stochastic()
    bullwhip_cols = [f"bullwhip_{echelon}" for echelon in ECHELON_NAMES]
    summary = position_results.groupby("config")[["team_cost"] + bullwhip_cols].agg(["mean", "std"])
    print(summary)

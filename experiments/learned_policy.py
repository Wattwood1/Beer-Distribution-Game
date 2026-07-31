"""Learned policy via direct optimization (CLAUDE.md's Option B fallback).

Rather than training an RL agent, this finds the anchor-and-adjust
parameters (theta, alpha, beta, safety_buffer) that minimize total
post-warmup team cost on the canonical step-demand scenario, using
scipy.optimize.differential_evolution -- a global, derivative-free
optimizer, needed because the objective is non-smooth (agents round
orders to integers and clamp at zero, so gradients don't exist
everywhere). Four homogeneous agents (make_anchor_and_adjust_agents
applies the same parameters to all four echelons, as elsewhere in this
project). Same cost definition (0.50/unit inventory + 1.00/unit backlog
per week, summed across all four echelons) and horizon as every other
experiment here, so results are directly comparable.
"""

from typing import Optional, Tuple

import pandas as pd
from scipy.optimize import differential_evolution

from agents.anchor_adjust import make_anchor_and_adjust_agents
from agents.base_stock import make_base_stock_agents
from env.config import SimulationConfig
from env.demand import step_demand
from env.engine import BeerGameEngine
from experiments.sweeps import bullwhip_ratio

PARAM_NAMES = ("theta", "alpha", "beta", "safety_buffer")
# Bounds were widened from an initial (0.01, 1.0)/(0.0, 20.0) pass after the
# optimizer kept landing near those edges across seeds. Direct probing
# confirmed both directions have genuine interior minima well inside these
# wider bounds (buffer optimum ~25, cost rises sharply above and below it;
# theta optimum is a real, if tiny, positive value ~0.001-0.003, not 0 --
# theta=0 measurably underperforms theta=0.001) -- see conversation/commit
# history, not bound-clamping artifacts.
BOUNDS = [(0.0, 1.0), (0.01, 1.5), (0.0, 1.0), (0.0, 40.0)]


def post_warmup_team_cost(df: pd.DataFrame, config: SimulationConfig) -> float:
    """Sum of holding+backlog cost across all echelons, weeks after warmup."""
    return df.loc[df["week"] > config.warmup_weeks, "cost"].sum()


def _objective(params, config: SimulationConfig) -> float:
    theta, alpha, beta, safety_buffer = params
    agents = make_anchor_and_adjust_agents(
        config, theta=theta, alpha=alpha, beta=beta, safety_buffer=safety_buffer
    )
    engine = BeerGameEngine(config, agents, step_demand)
    df = engine.run()
    return post_warmup_team_cost(df, config)


def optimize_anchor_and_adjust(
    config: Optional[SimulationConfig] = None, seed: int = 0
) -> Tuple[dict, float]:
    """Find (theta, alpha, beta, safety_buffer) minimizing post-warmup team cost.

    Returns (params_dict, minimized_cost).
    """
    config = config or SimulationConfig()
    result = differential_evolution(
        _objective,
        bounds=BOUNDS,
        args=(config,),
        seed=seed,
        maxiter=150,
        polish=True,
    )
    return dict(zip(PARAM_NAMES, result.x)), result.fun


def compare_policies(
    learned_params: dict, config: Optional[SimulationConfig] = None
) -> pd.DataFrame:
    """Bullwhip ratio and post-warmup team cost for the learned policy vs.
    base-stock (local/Level-0 baseline forecaster, same condition used
    throughout the info-sharing experiment) vs. anchor-and-adjust at the
    human-estimated beta=0.25."""
    config = config or SimulationConfig()
    policies = {
        "learned": make_anchor_and_adjust_agents(config, **learned_params),
        "base_stock": make_base_stock_agents(config),
        "anchor_and_adjust (beta=0.25)": make_anchor_and_adjust_agents(config),
    }
    rows = []
    for name, agents in policies.items():
        engine = BeerGameEngine(config, agents, step_demand)
        df = engine.run()
        rows.append(
            {
                "policy": name,
                "bullwhip_ratio": bullwhip_ratio(df),
                "team_cost": post_warmup_team_cost(df, config),
            }
        )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    params, cost = optimize_anchor_and_adjust()
    print("optimized params:", {k: round(v, 4) for k, v in params.items()})
    print("post-warmup team cost:", round(cost, 2))
    print()
    print(compare_policies(params).to_string(index=False))

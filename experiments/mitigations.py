"""Information-sharing mitigation experiment.

Two forecast conditions, using the pluggable-forecaster mechanism each
agent already has:

- Baseline (Level-0): every agent estimates demand from its own local
  signal only -- LocalMovingAverageForecaster for base-stock, local
  incoming_order smoothing for anchor-and-adjust. No visibility beyond
  what's actually received from downstream.
- Information-sharing (Level-1 POS sharing): every agent's forecast is
  fed the true demand rate directly instead -- KnownDemandForecaster for
  base-stock, true-demand smoothing for anchor-and-adjust.

Everything else (step demand, lead times, costs, theta/alpha/beta) is held
fixed; the forecast source is the only thing that changes between the two
columns of the resulting 2x2. Structured with a seeds loop for consistency
with experiments/sweeps.py, though seeds are currently a no-op (step_demand
is deterministic).

The headline 2x2 (run_information_sharing_experiment) shows info-sharing
helping anchor-and-adjust MORE than base-stock (27x vs 7.6x reduction at
beta=0.25) -- the opposite of the naive expectation that anchor-and-adjust's
problem is "purely behavioral" (supply-line misperception) and therefore
forecast-independent. run_beta_forecast_decomposition explains why: in this
4-echelon chain, an anchor-and-adjust agent's local signal isn't exogenous
noise, it's the output of the NEXT agent's own bullwhip, so BOTH forecast
quality and beta contribute substantially, and the effects compound rather
than simply add: info-sharing alone gives ~27x, beta=1 alone gives ~34x, but
both together give ~1718x -- about 1.9x more than the ~920x a naive product
of the two individual factors would predict. That is NOT independence (the
combination is super-multiplicative), just confirmation that neither
mechanism dominates the other on its own. At beta=1 AND info-sharing
together, bullwhip is essentially eliminated (ratio ~1, matching
base-stock).
"""

from typing import Iterable, Optional

import numpy as np
import pandas as pd

from agents.anchor_adjust import make_anchor_and_adjust_agents
from agents.base_stock import make_base_stock_agents
from env.config import SimulationConfig
from env.demand import step_demand
from env.engine import BeerGameEngine
from experiments.sweeps import bullwhip_ratio

TRUE_DEMAND_RATE = 8.0  # dominant/steady demand rate; see agents/base_stock.py docstring


def run_information_sharing_experiment(
    seeds: Iterable[int] = range(20),
    beta: float = 0.25,
    theta: float = 0.3,
    alpha: float = 0.25,
    config: Optional[SimulationConfig] = None,
) -> pd.DataFrame:
    """One row per (agent_type, condition, seed)."""
    config = config or SimulationConfig()
    rows = []
    for seed in seeds:
        np.random.seed(seed)  # no-op today; kept for consistency with sweeps.py

        conditions = {
            "baseline": {"expected_demand_per_week": None},
            "info_sharing": {"expected_demand_per_week": TRUE_DEMAND_RATE},
        }
        agent_builders = {
            "base_stock": lambda **kw: make_base_stock_agents(config, **kw),
            "anchor_and_adjust": lambda **kw: make_anchor_and_adjust_agents(
                config, theta=theta, alpha=alpha, beta=beta, **kw
            ),
        }

        for agent_type, build in agent_builders.items():
            for condition, kwargs in conditions.items():
                agents = build(**kwargs)
                engine = BeerGameEngine(config, agents, step_demand)
                df = engine.run()
                rows.append(
                    {
                        "agent_type": agent_type,
                        "condition": condition,
                        "seed": seed,
                        "bullwhip_ratio": bullwhip_ratio(df),
                    }
                )
    return pd.DataFrame(rows)


def run_beta_forecast_decomposition(
    betas: Iterable[float] = (0.25, 1.0),
    seeds: Iterable[int] = range(20),
    theta: float = 0.3,
    alpha: float = 0.25,
    config: Optional[SimulationConfig] = None,
) -> pd.DataFrame:
    """Cross beta in {0.25, 1.0} with both forecast conditions for
    anchor-and-adjust, to separate its beta-driven (supply-line
    misperception) bullwhip from its forecast-driven (cascading local-signal
    noise) bullwhip. See module docstring for the result and why it doesn't
    support treating the two mechanisms as independent."""
    config = config or SimulationConfig()
    rows = []
    for seed in seeds:
        np.random.seed(seed)  # no-op today; kept for consistency with sweeps.py
        for beta in betas:
            for condition, kwargs in [
                ("baseline", {"expected_demand_per_week": None}),
                ("info_sharing", {"expected_demand_per_week": TRUE_DEMAND_RATE}),
            ]:
                agents = make_anchor_and_adjust_agents(
                    config, theta=theta, alpha=alpha, beta=beta, **kwargs
                )
                engine = BeerGameEngine(config, agents, step_demand)
                df = engine.run()
                rows.append(
                    {
                        "beta": beta,
                        "condition": condition,
                        "seed": seed,
                        "bullwhip_ratio": bullwhip_ratio(df),
                    }
                )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    results = run_information_sharing_experiment()
    summary = results.groupby(["agent_type", "condition"])["bullwhip_ratio"].agg(["mean", "std"])
    print(summary)
    print()
    decomposition = run_beta_forecast_decomposition()
    print(decomposition.groupby(["beta", "condition"])["bullwhip_ratio"].agg(["mean", "std"]))

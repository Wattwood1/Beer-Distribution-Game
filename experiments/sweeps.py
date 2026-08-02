"""Parameter sweeps over agent policies.

CLAUDE.md's main result: bullwhip ratio vs. beta (supply-line weighting),
holding theta and alpha fixed. Structured to run across multiple seeds even
though the canonical step-demand generator is fully deterministic (seed has
no effect yet) — this is the same harness that later, stochastic demand
generators will plug into, and CLAUDE.md's "~20 seeds, mean +/- std"
protocol is non-negotiable once real randomness exists.
"""

from typing import Iterable, Optional

import numpy as np
import pandas as pd

from agents.anchor_adjust import make_anchor_and_adjust_agents
from env.config import SimulationConfig
from env.demand import step_demand
from env.engine import BeerGameEngine


def bullwhip_ratio(df: pd.DataFrame) -> float:
    """Var(Factory orders) / Var(customer demand), over the full horizon.

    The full horizon, not the post-warmup window, is used deliberately: the
    canonical demand step lands at week 5, inside the default 10-week
    warmup. Discarding warmup here would zero out demand variance entirely
    (post-step demand is flat) and make the ratio undefined — the warmup
    convention is meant for settling artifacts unrelated to the demand
    signal, not for discarding the signal itself.
    """
    factory_orders = df.loc[df["echelon"] == "Factory", "order_placed"]
    customer_demand = df.loc[df["echelon"] == "Retailer", "order_received"]
    return factory_orders.var() / customer_demand.var()


def bullwhip_ratio_post_warmup(df: pd.DataFrame, config: SimulationConfig) -> float:
    """Var(Factory orders) / Var(customer demand), weeks after warmup only.

    Use this instead of bullwhip_ratio whenever the demand generator has
    genuine variance throughout the run (e.g. env.demand.make_stochastic_demand)
    — bullwhip_ratio's full-horizon window is the right choice for the
    canonical step demand (see its docstring: the step falls inside
    warmup, so restricting to post-warmup would zero out demand variance
    entirely) but wrong here: the first ~warmup_weeks are an empty-pipeline
    startup transient (supply lines and delay queues start at zero/empty)
    that inflates factory-order variance for reasons unrelated to the
    demand signal. Confirmed empirically in tests/test_analytical_stochastic.py:
    the known-demand base-stock benchmark (which should read ~1.0, since
    order-up-to just relays demand upstream on a delay) reads ~7.4
    full-horizon vs. ~1.0 post-warmup, across 20 seeds. The two functions
    are siblings for different demand regimes, not competing defaults —
    neither should be used as a drop-in replacement for the other.
    """
    settled = df[df["week"] > config.warmup_weeks]
    factory_orders = settled.loc[settled["echelon"] == "Factory", "order_placed"]
    customer_demand = settled.loc[settled["echelon"] == "Retailer", "order_received"]
    return factory_orders.var() / customer_demand.var()


def run_beta_sweep(
    betas: Iterable[float] = tuple(np.round(np.arange(0.0, 1.01, 0.1), 2)),
    seeds: Iterable[int] = range(20),
    theta: float = 0.3,
    alpha: float = 0.25,
    config: Optional[SimulationConfig] = None,
) -> pd.DataFrame:
    """Sweep beta (supply-line weighting); one row per (beta, seed)."""
    config = config or SimulationConfig()
    rows = []
    for beta in betas:
        for seed in seeds:
            np.random.seed(seed)  # no-op today (step_demand is deterministic);
            # kept so this harness is ready for stochastic demand generators.
            agents = make_anchor_and_adjust_agents(config, theta=theta, alpha=alpha, beta=beta)
            engine = BeerGameEngine(config, agents, step_demand)
            df = engine.run()
            rows.append({"beta": beta, "seed": seed, "bullwhip_ratio": bullwhip_ratio(df)})
    return pd.DataFrame(rows)


if __name__ == "__main__":
    results = run_beta_sweep()
    summary = results.groupby("beta")["bullwhip_ratio"].agg(["mean", "std"])
    print(summary)

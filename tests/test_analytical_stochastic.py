"""Engine-correctness gate re-established under stochastic demand.

test_analytical.py's gate (four base-stock agents, KnownDemandForecaster,
step demand) proved the engine correct for a deterministic signal. Before
trusting any stochastic-demand experiment, the same style of gate has to
pass here too — with a different expected signature, since real demand
variance now exists.

Derivation of what "correct" looks like: KnownDemandForecaster is given the
TRUE mean mu (not a per-realization estimate), so S* = mu * lead_time +
buffer is a fixed constant. Tracing the order-up-to identity through one
engine week shows net_stock returns to exactly S* immediately after each
order is placed (see agents/base_stock.py), which means, once any echelon's
supply line/backlog have absorbed the initial transient, that echelon's
order_placed each week is EXACTLY the order/demand it received that same
week (confirmed empirically below) — not because bullwhip is absent, but
because the order-up-to rule with a fixed target simply relays demand
upstream unchanged, one echelon at a time, on a delay.

Consequence for the bullwhip ratio: the full-horizon bullwhip_ratio
convention used in experiments/sweeps.py (deliberately full-horizon there,
since the demand step falls inside the warmup window) is the WRONG metric
here — the first ~7 weeks are an empty-pipeline startup transient (supply
lines and delay queues start at zero/empty), which inflates factory-order
variance for reasons unrelated to demand variance. Restricting to
post-warmup weeks removes that artifact and the ratio settles to ~1.0
(confirmed across seeds below): not near-zero, because real demand variance
now exists, but stable and not blown up.
"""

import numpy as np

from agents.base_stock import make_base_stock_agents
from env.config import SimulationConfig
from env.demand import make_stochastic_demand
from env.engine import BeerGameEngine
from experiments.sweeps import bullwhip_ratio_post_warmup

MU = 8.0
SIGMA = 2.0
SEEDS = range(20)


def _run(seed: int):
    np.random.seed(seed)
    config = SimulationConfig()
    agents = make_base_stock_agents(config, expected_demand_per_week=MU)
    demand_fn = make_stochastic_demand(mu=MU, sigma=SIGMA)
    engine = BeerGameEngine(config, agents, demand_fn)
    return config, engine.run()


def test_orders_track_received_demand_exactly_once_settled():
    """Once past the warmup transient, order_placed == order_received for
    every echelon every week, regardless of the demand realization — the
    order-up-to identity holds exactly, not just on average."""
    for seed in SEEDS:
        config, df = _run(seed)
        settled = df[df["week"] > config.warmup_weeks]
        mismatches = settled[settled["order_placed"] != settled["order_received"]]
        assert mismatches.empty, f"seed {seed}: order_placed != order_received after settling"


def test_post_warmup_bullwhip_ratio_near_one_and_stable():
    ratios = np.array([bullwhip_ratio_post_warmup(df, config) for config, df in map(_run, SEEDS)])
    assert abs(ratios.mean() - 1.0) < 0.2, f"mean ratio {ratios.mean():.3f} too far from 1.0"
    assert ratios.std() < 0.3, f"ratio std {ratios.std():.3f} too unstable across seeds"
    assert ratios.max() < 2.0, f"max ratio {ratios.max():.3f} suggests blowup"


def test_no_blowup_in_inventory_or_backlog():
    for seed in SEEDS:
        _, df = _run(seed)
        assert df["inventory"].max() < 200
        assert df["backlog"].max() < 200

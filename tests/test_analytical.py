"""Base-stock correctness check — CLAUDE.md's engine-correctness gate.

Four base-stock agents, each given the true expected demand rate directly
(KnownDemandForecaster — an omniscient planning assumption, appropriate
since the canonical demand process is a fully-specified deterministic
step), should show near-zero bullwhip on step demand: orders converge and
then track demand exactly, with no residual variance. If they don't, the
engine has a bug, and nothing downstream (anchor-and-adjust, the beta
sweep) can be trusted until this passes.
"""

from agents.base_stock import make_base_stock_agents
from env.config import SimulationConfig
from env.demand import step_demand
from env.engine import BeerGameEngine

STEADY_DEMAND = 8.0


def _run():
    config = SimulationConfig()
    agents = make_base_stock_agents(config, expected_demand_per_week=STEADY_DEMAND)
    engine = BeerGameEngine(config, agents, step_demand)
    return config, engine.run()


def test_orders_settle_to_steady_demand_and_stay():
    config, df = _run()
    settled = df[df["week"] > config.warmup_weeks]

    assert (settled["order_placed"] == STEADY_DEMAND).all(), (
        "base-stock orders should exactly track steady-state demand after warmup; "
        "if not, the engine has a bug"
    )


def test_backlog_clears_once_settled():
    config, df = _run()
    settled = df[df["week"] > config.warmup_weeks]

    assert (settled["backlog"] == 0).all()


def test_no_amplifying_transient_across_echelons():
    """Peak order at each stage should not grow stage-to-stage in a way that
    signals runaway bullwhip amplification (a loose upper bound, not a tight
    one — the point is to catch gross engine breakage, e.g. an off-by-one in
    a delay pipeline, not to pin down exact peak values)."""
    _, df = _run()
    peak_by_echelon = df.groupby("echelon")["order_placed"].max()

    for peak in peak_by_echelon:
        assert peak <= 4 * STEADY_DEMAND, f"peak order {peak} suggests bullwhip amplification"

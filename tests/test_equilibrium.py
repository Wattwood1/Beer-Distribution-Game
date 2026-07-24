"""Zero-demand equilibrium test.

With no customer demand and a pass-through policy at every echelon, nothing
should ever move: no orders, no shipments, no backlog. Inventory should sit
at its initial level forever. This is the simplest possible correctness
check and should catch accidental "phantom" unit creation before the
conservation test is even needed.
"""

from agents.naive import PassThroughAgent
from env.config import SimulationConfig
from env.demand import zero_demand
from env.engine import BeerGameEngine


def test_zero_demand_chain_stays_at_equilibrium():
    config = SimulationConfig()
    agents = [PassThroughAgent() for _ in range(config.n_echelons)]
    engine = BeerGameEngine(config, agents, zero_demand)

    for week in range(1, config.horizon_weeks + 1):
        rows = engine.step(week)

        for st in engine.states:
            assert st.inventory == config.initial_inventory
            assert st.backlog == 0
            assert st.supply_line == 0

        for row in rows:
            assert row["shipment_received"] == 0
            assert row["order_received"] == 0
            assert row["shipped"] == 0
            assert row["order_placed"] == 0

    assert engine.cumulative_produced == 0
    assert engine.cumulative_delivered_to_customer == 0

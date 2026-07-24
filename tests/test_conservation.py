"""Conservation-of-units tests.

Nothing is created or destroyed except at the two system boundaries: Factory
production is the only source of new units, customer delivery (from the
Retailer) is the only sink. The invariant below accounts for the fixed
starting inventory loaded into every echelon at t=0, since that stock exists
before either boundary counter has moved.
"""

from agents.naive import PassThroughAgent
from env.config import SimulationConfig
from env.demand import step_demand
from env.engine import BeerGameEngine


def _build_engine() -> BeerGameEngine:
    config = SimulationConfig()
    agents = [PassThroughAgent() for _ in range(config.n_echelons)]
    return BeerGameEngine(config, agents, step_demand)


def test_unit_balance_holds_every_week():
    engine = _build_engine()
    initial_total_inventory = engine.config.n_echelons * engine.config.initial_inventory

    for week in range(1, engine.config.horizon_weeks + 1):
        engine.step(week)

        stock_in_system = sum(st.inventory for st in engine.states)
        stock_in_pipelines = sum(
            sum(st.incoming_shipments) + sum(st.incoming_production)
            for st in engine.states
        )

        lhs = stock_in_system + stock_in_pipelines + engine.cumulative_delivered_to_customer
        rhs = initial_total_inventory + engine.cumulative_produced

        assert lhs == rhs, f"unit balance broken at week {week}: {lhs} != {rhs}"


def test_inventory_and_backlog_never_negative():
    engine = _build_engine()
    for week in range(1, engine.config.horizon_weeks + 1):
        engine.step(week)
        for st in engine.states:
            assert st.inventory >= 0
            assert st.backlog >= 0


def test_pipeline_lengths_stay_constant():
    engine = _build_engine()
    config = engine.config
    for week in range(1, config.horizon_weeks + 1):
        engine.step(week)
        for i, st in enumerate(engine.states):
            if i == engine.factory_index:
                assert len(st.incoming_production) == config.production_delay
                assert len(st.incoming_shipments) == 0
            else:
                assert len(st.incoming_shipments) == config.ship_delay

            if i == 0:
                assert len(st.incoming_orders) == 0
            else:
                assert len(st.incoming_orders) == config.order_delay


def test_cumulative_counters_are_monotonic():
    engine = _build_engine()
    prev_produced = 0
    prev_delivered = 0
    for week in range(1, engine.config.horizon_weeks + 1):
        engine.step(week)
        assert engine.cumulative_produced >= prev_produced
        assert engine.cumulative_delivered_to_customer >= prev_delivered
        prev_produced = engine.cumulative_produced
        prev_delivered = engine.cumulative_delivered_to_customer

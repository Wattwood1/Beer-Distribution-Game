"""Core simulation engine: the weekly physics of the beer distribution game.

See CLAUDE.md for the authoritative six-phase weekly sequence. Echelons are
indexed 0=Retailer, 1=Wholesaler, 2=Distributor, 3=Factory; each echelon's
supplier is index+1 and its customer is index-1 (or the external customer
for the Retailer, and no supplier for the Factory).
"""

from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Deque, List

import pandas as pd

from agents.interface import Agent, Observation
from env.config import ECHELON_NAMES, SimulationConfig


@dataclass
class EchelonState:
    """Mutable per-echelon state.

    Not every field is used by every role: the Retailer never uses
    incoming_orders (customer demand arrives directly, with no transit
    delay) and the Factory never uses incoming_shipments (it has no
    supplier; incoming_production is its arriving-stock pipeline instead).
    """

    inventory: int
    backlog: int = 0
    supply_line: int = 0
    incoming_orders: Deque[int] = field(default_factory=deque)
    incoming_shipments: Deque[int] = field(default_factory=deque)
    incoming_production: Deque[int] = field(default_factory=deque)


class BeerGameEngine:
    """Runs the four-echelon serial supply chain for a configured horizon."""

    def __init__(
        self,
        config: SimulationConfig,
        agents: List[Agent],
        demand_fn: Callable[[int], int],
    ) -> None:
        if len(agents) != config.n_echelons:
            raise ValueError(f"expected {config.n_echelons} agents, got {len(agents)}")
        self.config = config
        self.agents = agents
        self.demand_fn = demand_fn
        self.factory_index = config.n_echelons - 1
        self.states: List[EchelonState] = [
            EchelonState(
                inventory=config.initial_inventory,
                incoming_orders=(
                    deque([0] * config.order_delay, maxlen=config.order_delay)
                    if i != 0
                    else deque()
                ),
                incoming_shipments=(
                    deque([0] * config.ship_delay, maxlen=config.ship_delay)
                    if i != self.factory_index
                    else deque()
                ),
                incoming_production=(
                    deque([0] * config.production_delay, maxlen=config.production_delay)
                    if i == self.factory_index
                    else deque()
                ),
            )
            for i in range(config.n_echelons)
        ]
        # The two system-boundary counters the conservation test relies on:
        # production is the only source of new units, customer delivery is
        # the only sink. Both start at zero; the fixed initial_inventory
        # loaded above is accounted for separately by the test.
        self.cumulative_produced = 0
        self.cumulative_delivered_to_customer = 0

    def step(self, week: int) -> List[dict]:
        """Advance the simulation by one week; returns one log row per echelon.

        All echelons read pipeline/demand state as it stood at the start of
        the week (phases 1-5); every pipeline push (phase 6) is applied only
        after all echelons have computed their shipment and order for the
        week, so per-echelon iteration order cannot affect the result.
        """
        n = self.config.n_echelons
        states = self.states

        # Phases 1-2: receive arriving shipment/production, then the
        # downstream order (or, for the Retailer, exogenous customer
        # demand), adding it to backlog.
        received_stock = [0] * n
        received_order = [0] * n
        for i, st in enumerate(states):
            if i == self.factory_index:
                qty = st.incoming_production.popleft()
            else:
                qty = st.incoming_shipments.popleft()
            st.inventory += qty
            st.supply_line -= qty
            received_stock[i] = qty

            order_in = self.demand_fn(week) if i == 0 else st.incoming_orders.popleft()
            st.backlog += order_in
            received_order[i] = order_in

        # Phase 3: ship to satisfy backlog as far as inventory allows.
        shipped = [0] * n
        for i, st in enumerate(states):
            qty = min(st.inventory, st.backlog)
            st.inventory -= qty
            st.backlog -= qty
            shipped[i] = qty

        # Phase 4: record cost.
        cost = [
            self.config.holding_cost * st.inventory + self.config.backlog_cost * st.backlog
            for st in states
        ]

        # Phase 5: each agent decides its new order from the post-shipment
        # state, using only its own observation (never another echelon's
        # state).
        order_placed = [0] * n
        for i, st in enumerate(states):
            obs = Observation(
                echelon=ECHELON_NAMES[i],
                week=week,
                inventory=st.inventory,
                backlog=st.backlog,
                supply_line=st.supply_line,
                incoming_order=received_order[i],
            )
            order_placed[i] = self.agents[i].order(obs)

        # Phase 6: propagate this week's shipments and orders, and update
        # supply lines and the two boundary counters. Applied only now, so
        # nothing pushed here was visible to any agent's observation above.
        for i, st in enumerate(states):
            st.supply_line += order_placed[i]

            if i == 0:
                self.cumulative_delivered_to_customer += shipped[i]
            else:
                states[i - 1].incoming_shipments.append(shipped[i])

            if i == self.factory_index:
                st.incoming_production.append(order_placed[i])
                self.cumulative_produced += order_placed[i]
            else:
                states[i + 1].incoming_orders.append(order_placed[i])

        return [
            {
                "week": week,
                "echelon": ECHELON_NAMES[i],
                "inventory": states[i].inventory,
                "backlog": states[i].backlog,
                "supply_line": states[i].supply_line,
                "shipment_received": received_stock[i],
                "order_received": received_order[i],
                "shipped": shipped[i],
                "order_placed": order_placed[i],
                "cost": cost[i],
                "cumulative_produced": self.cumulative_produced,
                "cumulative_delivered_to_customer": self.cumulative_delivered_to_customer,
            }
            for i in range(n)
        ]

    def run(self) -> pd.DataFrame:
        """Run the full configured horizon and return a tidy log DataFrame."""
        rows = []
        for week in range(1, self.config.horizon_weeks + 1):
            rows.extend(self.step(week))
        return pd.DataFrame(rows)

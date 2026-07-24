"""Base-stock (order-up-to) policy — the rational benchmark and the engine's
correctness check.

O_t = max(0, S_star - (inventory - backlog + supply_line))

S_star tracks a moving-average estimate of the demand/order signal this
echelon has observed (per Chen et al. 2000's base-stock + moving-average
forecasting formulation — see paper/beer-game-project-guide.md) times this
echelon's total replenishment lead time, plus a small fixed safety buffer.
A single-period estimate is not enough: an upstream echelon only observes
the *order quantities* placed by its downstream neighbor, which are
themselves lumpy corrections from that neighbor's own base-stock policy,
not smooth demand. Averaging over the lead-time window filters that
correction noise back out. Under deterministic demand and a known lead
time this converges within roughly one lead-time cycle and then tracks
demand exactly: near-zero bullwhip. If it doesn't, the engine has a bug —
this is the project's explicit correctness gate (see CLAUDE.md).
"""

from collections import deque
from typing import List

from agents.interface import Observation
from env.config import SimulationConfig


class BaseStockAgent:
    """Order-up-to policy; S_star re-based each week off a moving average."""

    def __init__(self, lead_time_weeks: int, safety_buffer: float = 4.0) -> None:
        self.lead_time_weeks = lead_time_weeks
        self.safety_buffer = safety_buffer
        self._demand_history: deque = deque(maxlen=lead_time_weeks)

    def order(self, observation: Observation) -> int:
        self._demand_history.append(observation.incoming_order)
        demand_estimate = sum(self._demand_history) / len(self._demand_history)
        s_star = demand_estimate * self.lead_time_weeks + self.safety_buffer
        net_stock = observation.inventory - observation.backlog + observation.supply_line
        return max(0, round(s_star - net_stock))


def make_base_stock_agents(
    config: SimulationConfig, safety_buffer: float = 4.0
) -> List[BaseStockAgent]:
    """One BaseStockAgent per echelon, each with its own correct lead time.

    Echelons 0..n-2 (Retailer/Wholesaler/Distributor in the canonical setup)
    wait order_delay + ship_delay weeks for a replenishment order to arrive.
    The last echelon (Factory) has no supplier — its only delay is its own
    production_delay.
    """
    factory_index = config.n_echelons - 1
    agents = []
    for i in range(config.n_echelons):
        lead_time = (
            config.production_delay if i == factory_index else config.order_delay + config.ship_delay
        )
        agents.append(BaseStockAgent(lead_time_weeks=lead_time, safety_buffer=safety_buffer))
    return agents

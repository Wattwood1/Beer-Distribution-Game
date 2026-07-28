"""Base-stock (order-up-to) policy — the rational benchmark and the engine's
correctness check.

O_t = max(0, S_star - (inventory - backlog + supply_line))

S_star = demand_estimate * lead_time_weeks + safety_buffer. The demand
estimate comes from a pluggable DemandForecaster rather than a hardcoded
value, because which forecast source is "fair game" is itself an
experimental condition later on (see paper/beer-game-project-guide.md
Phase 5, information sharing). Two forecasters are provided:

- KnownDemandForecaster: the agent is told the true expected demand rate
  directly (an omniscient planning assumption, reasonable since the
  canonical demand process is a fully-specified, deterministic step, not
  something that needs inferring). Used for the engine correctness check:
  it isolates engine bugs from forecast noise by removing the forecast
  itself as a source of amplification. On step demand, four base-stock
  agents in this mode show near-zero bullwhip (peak ~3.5x demand, flat by
  ~week 11) — if they don't, the engine has a bug (CLAUDE.md's explicit
  gate; do not proceed past this until it passes).
- LocalMovingAverageForecaster: the agent estimates demand from a moving
  average of the order quantities it has actually received from
  downstream (per Chen et al. 2000's base-stock + moving-average
  formulation). This is the true Level-0 baseline information condition —
  no visibility into other echelons or true customer demand — and is what
  the information-sharing mitigation will later improve on, by switching
  the forecast source to true customer demand. It is NOT near-zero
  bullwhip on its own: each echelon's own corrective re-ordering after a
  demand step gets misread by the next echelon upstream as a further
  demand-rate change, producing genuine (if self-correcting) cascading
  amplification — Factory transient peaks around 7.5x demand and the
  chain doesn't fully flatten until roughly week 28. That is expected
  behavior for this mode, not a bug, and is deliberately left as the
  baseline for later experiments rather than tuned away.
"""

from collections import deque
from typing import List, Optional, Protocol

from agents.interface import Observation
from env.config import SimulationConfig


class DemandForecaster(Protocol):
    def estimate(self, observation: Observation) -> float:
        """Return this week's demand-rate estimate, in units/week."""
        ...


class KnownDemandForecaster:
    """Omniscient: the true expected demand rate, fixed at construction."""

    def __init__(self, expected_demand_per_week: float) -> None:
        self.expected_demand_per_week = expected_demand_per_week

    def estimate(self, observation: Observation) -> float:
        return self.expected_demand_per_week


class LocalMovingAverageForecaster:
    """Moving average of the orders actually received from downstream."""

    def __init__(self, window: int) -> None:
        self._history: deque = deque(maxlen=window)

    def estimate(self, observation: Observation) -> float:
        self._history.append(observation.incoming_order)
        return sum(self._history) / len(self._history)


class BaseStockAgent:
    """Order-up-to policy; S_star is re-based each week from a pluggable
    demand forecaster (see module docstring for the two provided modes)."""

    def __init__(
        self,
        lead_time_weeks: int,
        forecaster: DemandForecaster,
        safety_buffer: float = 4.0,
    ) -> None:
        self.lead_time_weeks = lead_time_weeks
        self.forecaster = forecaster
        self.safety_buffer = safety_buffer

    def order(self, observation: Observation) -> int:
        demand_estimate = self.forecaster.estimate(observation)
        s_star = demand_estimate * self.lead_time_weeks + self.safety_buffer
        net_stock = observation.inventory - observation.backlog + observation.supply_line
        return max(0, round(s_star - net_stock))


def make_base_stock_agents(
    config: SimulationConfig,
    expected_demand_per_week: Optional[float] = None,
    safety_buffer: float = 4.0,
) -> List[BaseStockAgent]:
    """One BaseStockAgent per echelon, each with its own correct lead time.

    If expected_demand_per_week is given, every agent uses the omniscient
    KnownDemandForecaster — the engine-correctness configuration. Otherwise
    every agent uses a LocalMovingAverageForecaster over its own lead-time
    window — the Level-0 baseline used in later experiments.

    Echelons 0..n-2 (Retailer/Wholesaler/Distributor in the canonical
    setup) wait order_delay + ship_delay weeks for a replenishment order to
    arrive. The last echelon (Factory) has no supplier — its only delay is
    its own production_delay.
    """
    factory_index = config.n_echelons - 1
    agents = []
    for i in range(config.n_echelons):
        lead_time = (
            config.production_delay if i == factory_index else config.order_delay + config.ship_delay
        )
        forecaster: DemandForecaster
        if expected_demand_per_week is not None:
            forecaster = KnownDemandForecaster(expected_demand_per_week)
        else:
            forecaster = LocalMovingAverageForecaster(window=lead_time)
        agents.append(BaseStockAgent(lead_time, forecaster, safety_buffer))
    return agents

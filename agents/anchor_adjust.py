"""Anchor-and-adjust (Sterman 1989) — the human ordering-behavior model.

O_t = max(0, D_hat_t + alpha * (S_desired_t - current_stock_t - beta * supply_line_t))

This is the headline reproduction of Sterman's result. Three behavioral
elements distinguish it from the base-stock rational benchmark:

- D_hat_t: an EXPONENTIALLY SMOOTHED demand forecast (smoothing theta ~0.3),
  not an omniscient or moving-average estimate. S_desired_t is tied to this
  same forecast (D_hat_t * lead_time_weeks + a safety buffer), the way
  Sterman's subjects set their target stock from their own belief about
  demand. The signal fed into the smoothing recursion is itself pluggable
  (expected_demand_per_week below) so this agent can run under the same
  baseline/information-sharing conditions as base-stock: baseline smooths
  the local incoming_order signal (Level-0, no visibility beyond what's
  actually received); information-sharing smooths the true demand rate
  instead (Level-1 POS sharing). The smoothing MECHANISM (theta) is the
  same either way -- only the input signal changes.
- alpha (~0.25): a PARTIAL stock-adjustment rate. Each week the agent only
  closes about a quarter of the perceived gap between desired and current
  position, rather than closing it fully in one step the way base-stock
  does. This is what turns a one-time correction into a multi-week,
  oscillating correction.
- beta (~0.25): SUPPLY LINE WEIGHTING — this is the whole story. The agent
  perceives its total inventory position as current_stock + beta *
  supply_line, i.e. it only partially credits units already on order. Low
  beta means the agent keeps ordering more because it doesn't fully
  "trust" that units already ordered are coming; beta = 1 would fully
  account for the supply line and remove this channel of amplification.

NOTE: "current_stock" here (inventory - backlog) deliberately excludes
supply_line — unlike base-stock's net_stock, which already includes it.
Supply_line enters this formula as its own, separately beta-weighted term.
Folding supply_line into current_stock here would make beta's effective
weight (1 - beta) instead of beta, silently inverting CLAUDE.md's stated
beta=1-fully-accounts / low-beta-produces-bullwhip relationship.
"""

from typing import List, Optional

from agents.interface import Observation
from env.config import SimulationConfig


class AnchorAndAdjustAgent:
    """Sterman's anchor-and-adjust ordering heuristic."""

    def __init__(
        self,
        lead_time_weeks: int,
        theta: float = 0.3,
        alpha: float = 0.25,
        beta: float = 0.25,
        safety_buffer: float = 4.0,
        expected_demand_per_week: Optional[float] = None,
    ) -> None:
        self.lead_time_weeks = lead_time_weeks
        self.theta = theta
        self.alpha = alpha
        self.beta = beta
        self.safety_buffer = safety_buffer
        self.expected_demand_per_week = expected_demand_per_week
        self._d_hat: float = None  # lazily seeded from the first observed signal

    def order(self, observation: Observation) -> int:
        signal = (
            self.expected_demand_per_week
            if self.expected_demand_per_week is not None
            else observation.incoming_order
        )
        if self._d_hat is None:
            self._d_hat = float(signal)
        else:
            self._d_hat = self.theta * signal + (1 - self.theta) * self._d_hat

        s_desired = self._d_hat * self.lead_time_weeks + self.safety_buffer
        current_stock = observation.inventory - observation.backlog
        gap = s_desired - current_stock - self.beta * observation.supply_line
        return max(0, round(self._d_hat + self.alpha * gap))


def make_anchor_and_adjust_agents(
    config: SimulationConfig,
    theta: float = 0.3,
    alpha: float = 0.25,
    beta: float = 0.25,
    safety_buffer: float = 4.0,
    expected_demand_per_week: Optional[float] = None,
) -> List[AnchorAndAdjustAgent]:
    """One AnchorAndAdjustAgent per echelon, each with its own lead time.

    Echelons 0..n-2 (Retailer/Wholesaler/Distributor in the canonical
    setup) wait order_delay + ship_delay weeks for a replenishment order to
    arrive. The last echelon (Factory) has no supplier — its only delay is
    its own production_delay.

    If expected_demand_per_week is given, every agent's forecast smooths
    the true demand rate instead of its local incoming_order signal (the
    information-sharing condition). Otherwise (default) every agent smooths
    its own local signal (the Level-0 baseline) -- the committed Day-3
    behavior.
    """
    factory_index = config.n_echelons - 1
    agents = []
    for i in range(config.n_echelons):
        lead_time = (
            config.production_delay if i == factory_index else config.order_delay + config.ship_delay
        )
        agents.append(
            AnchorAndAdjustAgent(lead_time, theta, alpha, beta, safety_buffer, expected_demand_per_week)
        )
    return agents

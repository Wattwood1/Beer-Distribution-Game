"""Simulation-wide configuration for the beer distribution game engine."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SimulationConfig:
    """Parameters shared by the engine, agents, and experiments.

    order_delay and ship_delay are the two 2-week transit pipelines that
    together make up the 4-week order-to-receipt lead time for echelons
    0-2. production_delay is the Factory's own production lead time and is
    a separate knob even though it defaults to the same value as
    ship_delay.
    """

    n_echelons: int = 4
    order_delay: int = 2
    ship_delay: int = 2
    production_delay: int = 2
    initial_inventory: int = 12
    horizon_weeks: int = 52
    warmup_weeks: int = 10
    holding_cost: float = 0.50
    backlog_cost: float = 1.00


ECHELON_NAMES = ("Retailer", "Wholesaler", "Distributor", "Factory")

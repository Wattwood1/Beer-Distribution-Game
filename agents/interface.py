"""Shared agent interface.

The Observation is deliberately minimal: an echelon sees only its own state
and the order/demand it just received from downstream. It has no visibility
into other echelons' inventory, backlog, or orders. This is the Level-0
(baseline) information condition; richer observations for the
information-sharing mitigation are added later by extending this object,
not by agents reaching into engine internals.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Observation:
    """What a single echelon can see when it makes its ordering decision."""

    echelon: str
    week: int
    inventory: int
    backlog: int
    supply_line: int
    incoming_order: int


class Agent(Protocol):
    """Interface every ordering policy implements."""

    def order(self, observation: Observation) -> int:
        """Return the quantity to order upstream this week (>= 0)."""
        ...

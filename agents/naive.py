"""Trivial test-only policy: order exactly what was just received.

This is CLAUDE.md's build-order step 1 policy, used only to exercise the
engine's mechanics for the conservation and equilibrium tests. It is not
one of the three real policies (base-stock, anchor-and-adjust, learned).
"""

from agents.interface import Observation


class PassThroughAgent:
    """Orders whatever quantity it just received as an incoming order."""

    def order(self, observation: Observation) -> int:
        return observation.incoming_order

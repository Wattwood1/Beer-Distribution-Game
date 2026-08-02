"""Customer demand generators.

Each generator is a callable with signature ``demand_fn(week: int) -> int``,
where ``week`` is the 1-indexed simulation week. Keeping this a plain
callable interface (rather than a class hierarchy) makes it trivial to swap
generators later (stationary stochastic, AR(1), seasonal) without touching
the engine.
"""

from typing import Callable

import numpy as np


def step_demand(week: int) -> int:
    """Sterman's classic step: 4 units/week for weeks 1-4, then 8/week."""
    return 4 if week <= 4 else 8


def zero_demand(week: int) -> int:
    """No customer demand, ever. Used to test engine equilibrium."""
    return 0


def make_stochastic_demand(mu: float = 8.0, sigma: float = 2.0) -> Callable[[int], int]:
    """Stationary customer demand: round(N(mu, sigma)), floored at 0.

    Draws from the global NumPy RNG rather than owning a private one, so a
    caller's ``np.random.seed(seed)`` — the convention the seed loops in
    experiments/sweeps.py and mitigations.py already use, previously a
    no-op under deterministic step_demand — now actually determines the
    draw sequence.

    "Truncated at 0" is implemented as ``max(0, sample)`` rather than
    rejection-resampling: at mu=8, sigma=2, a negative draw is a ~4-sigma
    event (P ~ 3e-5), so the two are numerically indistinguishable and the
    simpler form is used. See tests/test_demand.py for the check that this
    doesn't measurably distort mean/std.
    """

    def demand_fn(week: int) -> int:
        return max(0, round(float(np.random.normal(mu, sigma))))

    return demand_fn

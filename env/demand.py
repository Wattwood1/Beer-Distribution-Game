"""Customer demand generators.

Each generator is a callable with signature ``demand_fn(week: int) -> int``,
where ``week`` is the 1-indexed simulation week. Keeping this a plain
callable interface (rather than a class hierarchy) makes it trivial to swap
generators later (stationary stochastic, AR(1), seasonal) without touching
the engine.
"""


def step_demand(week: int) -> int:
    """Sterman's classic step: 4 units/week for weeks 1-4, then 8/week."""
    return 4 if week <= 4 else 8


def zero_demand(week: int) -> int:
    """No customer demand, ever. Used to test engine equilibrium."""
    return 0

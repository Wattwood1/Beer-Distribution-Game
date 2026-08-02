"""Validate the stochastic demand generator in isolation, before it's wired
into any experiment. See env/demand.py's make_stochastic_demand: N(mu,
sigma) truncated at 0, drawn from the global NumPy RNG.
"""

import numpy as np

from env.demand import make_stochastic_demand

MU = 8.0
SIGMA = 2.0
N_SAMPLES = 20_000


def _sample(n: int = N_SAMPLES) -> np.ndarray:
    np.random.seed(0)
    demand_fn = make_stochastic_demand(mu=MU, sigma=SIGMA)
    return np.array([demand_fn(week) for week in range(1, n + 1)])


def test_mean_close_to_mu():
    assert abs(_sample().mean() - MU) < 0.1


def test_std_close_to_sigma():
    assert abs(_sample().std() - SIGMA) < 0.1


def test_never_negative():
    assert (_sample() >= 0).all()


def test_truncation_effect_is_negligible():
    """At mu=8, sigma=2, truncation at 0 is a ~4-sigma event, so clip-at-0
    and reject-and-resample give practically the same distribution.
    Confirm the clipped fraction is negligible rather than assume it."""
    np.random.seed(0)
    raw = np.random.normal(MU, SIGMA, N_SAMPLES)
    clipped_fraction = (raw < 0).mean()
    assert clipped_fraction < 0.001


def test_deterministic_given_seed():
    np.random.seed(42)
    a = make_stochastic_demand(mu=MU, sigma=SIGMA)
    samples_a = [a(week) for week in range(1, 51)]
    np.random.seed(42)
    b = make_stochastic_demand(mu=MU, sigma=SIGMA)
    samples_b = [b(week) for week in range(1, 51)]
    assert samples_a == samples_b

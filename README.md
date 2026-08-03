# Beer Distribution Game

An instrumented simulation of the Beer Distribution Game (Sterman's classic) that quantifies bullwhip amplification under three ordering policies and tests mitigations.

![Bullwhip ratio vs. beta](results/figures/01_beta_sweep.png)

## What it does

- Simulates a 4-echelon serial supply chain (Retailer → Wholesaler → Distributor → Factory) with order and shipping delays
- Implements three ordering policies: base-stock (rational benchmark), anchor-and-adjust (Sterman's behavioral model), and a learned policy (parameters optimized via scipy)
- Quantifies bullwhip amplification with multiple metrics
- Tests an information-sharing mitigation
- Validated across both deterministic step demand and stochastic demand (multi-seed, with confidence intervals)

## Key findings

**Bullwhip is governed by supply-line weighting: as agents better account for in-transit orders (beta 0→1), the bullwhip ratio falls ~150x.** See the hero figure above — beta sweeps from 0 (bullwhip ratio ~7,993) to 1 (~54), full-horizon, deterministic step demand.

**Anchor-and-adjust agents reproduce the classic amplifying oscillation — order swings grow at each stage upstream, Factory swinging hardest, from a demand that only steps 4→8.**

![Order trajectories, anchor-and-adjust](results/figures/02_anchor_adjust_trajectories.png)

**Under stochastic demand, information-sharing helps the forecast-driven base-stock agent far more than the misperception-driven anchor-and-adjust agent (~63x vs. ~25x reduction) — this reverses the naive deterministic result, because deterministic demand has no variance to forecast.**

![Information-sharing mitigation, stochastic demand](results/figures/03_mitigation_stochastic.png)

**A single rational agent's position matters: placing it at the demand-facing Retailer end gives the most leverage on both cost and bullwhip (verified across 20 seeds, decisive paired test).**

![Position sensitivity, stochastic demand](results/figures/04_position_sensitivity_stochastic.png)

Figures 1–2 use deterministic step demand (full-horizon variance); figures 3–4 use stochastic demand (post-warmup variance, 20-seed mean ± std). The two regimes use different bullwhip-ratio conventions for principled reasons — see `experiments/sweeps.py` and `experiments/stochastic.py` — so values are not comparable across that boundary; only the qualitative findings are meant to be compared.

## The mechanism

Bullwhip is a structural property of the system, not a result of irrational agents. Even locally sensible ordering rules produce it; the amplification comes from delays and supply-line misperception, not from anyone behaving badly. This is the formal, instrumented version of the lesson the MIT Sloan Beer Game is famous for teaching: players in that game routinely blame each other for swings that the system's own delays and hidden demand signal actually cause.

## How to run

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the test suite:

```bash
python3 -m pytest
```

Run the experiments:

```bash
python3 -m experiments.sweeps          # beta sweep (deterministic step demand) — the headline result
python3 -m experiments.mitigations     # information-sharing 2x2 + beta/forecast decomposition (deterministic)
python3 -m experiments.heterogeneous   # position-sensitivity experiment (deterministic)
python3 -m experiments.learned_policy  # scipy-optimized policy vs. base-stock and anchor-and-adjust
python3 -m experiments.stochastic      # beta sweep, mitigation, and position experiments re-run under stochastic demand, 20 seeds
python3 -m experiments.figures         # regenerate the four committed result figures into results/figures/
```

## Repo structure

```
env/                  simulation engine
  engine.py             weekly physics: the six-phase per-echelon step
  config.py              SimulationConfig, canonical setup, echelon names
  demand.py              deterministic step demand + stochastic demand generator

agents/                ordering policies
  interface.py           shared Observation/Agent protocol
  base_stock.py           rational order-up-to benchmark, pluggable demand forecaster
  anchor_adjust.py        Sterman's behavioral model (theta, alpha, beta)
  naive.py                pass-through test-only agent

experiments/           experiment runners and figure generation
  sweeps.py               beta sweep (deterministic)
  mitigations.py           information-sharing mitigation (deterministic)
  heterogeneous.py         position sensitivity (deterministic)
  learned_policy.py        scipy.optimize parameter search
  stochastic.py            beta sweep, mitigation, position — all re-run under stochastic demand
  figures.py               generates results/figures/*.png

tests/                 conservation, equilibrium, and correctness-gate tests
results/figures/       committed result figures (PNG)
```

## How it was built

Built incrementally: the engine was validated by conservation, equilibrium, and analytical (near-zero-bullwhip) tests before any behavioral agent logic was added, so engine bugs and agent behavior were never debugged at the same time. Each subsequent result — the beta sweep, the mitigation, the position-sensitivity experiment — was re-verified under both deterministic step demand and stochastic demand, with a re-established correctness gate for the stochastic case before any stochastic experiment was trusted. Developed with Claude Code.

## Limitations

The behavioral agents (anchor-and-adjust) are a model of human ordering behavior, not human subjects — they reproduce Sterman's documented pattern but aren't validated against new experimental data here. Results are reported for two specific demand processes (a deterministic step and a stationary stochastic process); other demand patterns (seasonal, trending, correlated) are untested. The "learned" policy uses direct parameter optimization (scipy's differential evolution) over the anchor-and-adjust functional form, not a general-purpose deep RL agent — it finds the best parameters within that structure, not the best policy in an unconstrained policy space. The supply chain itself is a 4-echelon serial simplification; real distribution networks are typically non-serial, multi-sourced, and capacity-constrained.

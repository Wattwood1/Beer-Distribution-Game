# CLAUDE.md — Beer Distribution Game Project

This file briefs Claude Code on the project. Read it fully before doing anything.

## What this project is

An instrumented rebuild of Sterman's Beer Distribution Game as a multi-agent simulation.
Four echelons in series — Retailer -> Wholesaler -> Distributor -> Factory. Each week each
echelon receives stock, fills downstream orders (shortfalls become backlog), and orders
from upstream. Orders take 2 weeks to travel upstream; shipments take 2 weeks to travel
back down. Only the Retailer sees true customer demand.

The phenomenon under study is the **bullwhip effect**: customer demand steps from 4 to 8
units/week and stays flat, yet order variance amplifies at each upstream stage, with the
Factory swinging violently. Sterman's explanation is that decision-makers **underweight the
supply line** — inventory ordered but not yet received. This project quantifies that and
tests mitigations.

## Framing (the point of the whole thing)

The amplification is a property of the STRUCTURE, not the agents. Even a locally sensible
ordering rule produces the bullwhip. The MIT Sloan version of this game is famous for
teaching that players wrongly blame each other for swings that the system's delays and
hidden demand signal actually cause. This simulation is the formal, instrumented version
of that lesson. Keep this framing in any write-up.

## Scope: 6-day project, NOT a full paper

The deliverable is a working simulator, a clean reproduction of Sterman's result, three
policy types, and one tested mitigation (information sharing). Do not scope-creep toward
VMI, an 81-config sweep, Shapley attribution, or multiple demand distributions unless the
core is done and there's time left. Protect the core.

## The physics (implement exactly)

State per echelon: inventory, backlog, supply_line, plus two 2-slot delay pipelines
(orders up, shipments down).

Weekly sequence — order matters, this is where implementations break:
1. Receive arriving shipment; decrement supply line.
2. Receive downstream order (Retailer receives customer demand); add to backlog.
3. Ship min(inventory, backlog); decrement both.
4. Record cost: 0.50 * inventory + 1.00 * backlog.
5. Agent decides new order upstream.

Factory has no supplier — its "order" is a production start with a 2-week delay, never
constrained by raw materials.

Canonical setup: starting inventory 12 units per echelon, demand = 4/week for weeks 1-4
then 8/week thereafter, horizon 52 weeks. Discard first 10 weeks as warm-up in statistics.

## The three agent policies

All behind one interface: `agent.order(observation) -> int`.

1. BASE-STOCK (rational benchmark, also the correctness check):
   O_t = max(0, S_star - (inventory - backlog + supply_line))
   S_star from expected demand over the 4-week total lead time plus a small buffer.
   On step demand, four base-stock agents should show NEAR-ZERO bullwhip. If they don't,
   the ENGINE has a bug. Do not proceed past this until it passes.

   The "expected demand" feeding S_star is a pluggable forecaster (agents/base_stock.py),
   not a hardcoded value, because the two modes serve different purposes:
     - KnownDemandForecaster (omniscient, true rate given at construction) — use this for
       the correctness gate above. It isolates engine bugs from forecast noise: peak order
       ~3.5x demand, flat by ~week 11.
     - LocalMovingAverageForecaster (moving average of orders actually received from
       downstream, no visibility beyond that) — the real Level-0 baseline for later
       experiments. On its own it is NOT near-zero bullwhip: each echelon's corrective
       re-ordering after a demand step gets misread upstream as a further demand change,
       producing genuine cascading amplification (Factory peak ~7.5x demand, doesn't
       flatten until ~week 28) before eventually settling exactly. That's expected, not a
       bug — it's what the information-sharing mitigation (switching the forecast source
       to true customer demand) is there to fix.

2. ANCHOR-AND-ADJUST (Sterman's human model — the headline reproduction):
   O_t = max(0, D_hat + alpha * (S_desired - net_stock - beta * supply_line))
   - D_hat = exponentially smoothed demand, smoothing ~0.3
   - alpha = stock adjustment rate ~0.25
   - beta = SUPPLY LINE WEIGHTING, ~0.25 for human-like behavior. THIS IS THE WHOLE STORY.
     beta = 1 fully accounts for in-transit orders; low beta produces the bullwhip.

3. LEARNED policy (timeboxed to one day):
   - Option A: PPO via Stable-Baselines3, one learning agent at Retailer, others
     anchor-and-adjust. State [inventory, backlog, supply_line, last 3 demands], action
     d_t + a with a in [-8,+8], reward = negative weekly cost, ~100k steps.
   - Option B (fallback, fully legitimate): grid-search / scipy.optimize over
     (alpha, beta, theta) to minimize total cost. Likely finds beta near 1.0, which
     independently confirms the beta result. Switch to B without guilt if RL stalls.

## Metrics (report several, they disagree and that's informative)

- Bullwhip ratio: Var(factory_orders) / Var(customer_demand)  <- headline
- Per-stage amplification: Var(orders_i) / Var(orders_{i-1})
- Peak order: max(factory_orders)
- Total team cost: summed holding + backlog across all four echelons
Report cost and variance SEPARATELY — they can move in opposite directions.

## Key experiments

- Beta sweep: sweep beta 0 to 1 in steps of 0.1, plot bullwhip ratio vs beta. MAIN RESULT.
- Four configs (not 81): all base-stock; all anchor-and-adjust; learned at Retailer;
  learned at Factory. Question: does position matter?
- Information sharing mitigation: flag that puts true customer demand into every agent's
  observation. Expected: helps base-stock a lot, anchor-and-adjust much less, because the
  behavioral problem is supply-line misperception, not bad forecasts. If the data shows
  that, it's the key finding.

Run experiments on ~20 seeds, report mean +/- std. This is non-negotiable — it's the
difference between a result and an anecdote.

## Engineering requirements

- Deterministic given a seed. Log every state variable every week to a tidy dataframe.
- Unit tests: conservation of units (nothing created/destroyed), zero-demand chain stays
  at equilibrium, base-stock near-zero-bullwhip check.
- Run `python -m pytest` before considering any milestone done.

## Repository structure

beergame/
  env/          engine.py, demand.py, config.py
  agents/       base_stock.py, anchor_adjust.py, rl_agent.py, interface.py
  experiments/  sweeps.py, heterogeneous.py, mitigations.py
  analysis/     metrics.py, figures.py, stats.py
  tests/        test_conservation.py, test_equilibrium.py, test_analytical.py
  results/      raw logs (gitignored), processed dataframes
  paper/

Stack: NumPy, Pandas, Matplotlib. Add Gymnasium + Stable-Baselines3 only for RL Option A.

## Build order (first steps)

1. Engine with a hard-coded "order what you received" policy. Verify conservation.
2. Base-stock agents. Confirm near-zero bullwhip on step demand (engine correctness proof).
3. Anchor-and-adjust with beta=0.25. Confirm the oscillation appears (Sterman reproduction).
Once step 3 reproduces the oscillation, the platform works and the rest is experiments.

## Conventions

- Python 3, type hints, docstrings on every agent and the engine step function.
- Keep the engine and the agents strictly separate — agents only see an observation object,
  never the full engine state. The observation's contents define the information-sharing
  conditions, so design it deliberately.

# Instrumented Beer Distribution Game: Project Guide

A multi-agent simulation study of bullwhip amplification under heterogeneous ordering
policies, with controlled tests of information-sharing and VMI mitigations.

---

## 0. Background you should read before writing code

| Source | Why it matters |
|---|---|
| Sterman (1989), *Modeling Managerial Behavior*, Mgmt Science 35(3) | The anchor-and-adjust model and the "supply line underweighting" result. This is your baseline agent and your baseline finding. |
| Lee, Padmanabhan & Whang (1997), *Information Distortion in a Supply Chain* | The four structural causes of bullwhip: demand signal processing, order batching, price fluctuation, rationing/shortage gaming. Your mitigation section maps onto these. |
| Chen et al. (2000), *Quantifying the Bullwhip Effect* | Closed-form bullwhip bounds under base-stock + moving-average forecasting. Gives you an analytical benchmark to validate your sim against. |
| Oroojlooyjadid et al. (2022), *A Deep Q-Network for the Beer Game* | The canonical RL-agent-plays-beer-game paper. Read it to know what's already been done so you can differentiate. |
| Croson & Donohue (2006) | Shows bullwhip persists even with known, stationary demand — kills the "it's just forecasting error" explanation. |

**Your differentiation angle:** most prior work makes all four agents the same type. Your
mentor is proposing *heterogeneous* chains — a learned agent sitting next to a human-like
heuristic agent next to an optimal one. The interesting question becomes: *does one
well-behaved echelon fix the chain, or does it get destabilized by its neighbors?* That's
a publishable question and it's the spine of your paper.

---

## 1. Phase 1 — Simulation engine (weeks 1–2)

Build this first, get it exactly right, and freeze it. Everything downstream depends on
the physics being correct.

### 1.1 State per echelon `i` at week `t`
- `inventory[i]` — on-hand units
- `backlog[i]` — unfilled downstream orders (cumulative)
- `incoming_shipments[i]` — pipeline of length `L_ship` (default 2)
- `incoming_orders[i]` — pipeline of length `L_order` (default 2)
- `supply_line[i]` — units ordered but not yet received (the critical instrumented quantity)

### 1.2 Weekly update order (get this sequence right — it's where most implementations break)
1. Receive inventory arriving this week; decrement supply line.
2. Receive incoming order from downstream (Retailer receives exogenous customer demand).
3. Add new order to backlog.
4. Ship `min(inventory, backlog)` downstream; decrement both.
5. Record cost for the week.
6. Compute and place new order upstream (this is the **agent decision point**).

The Factory has no upstream supplier — its "order" is a production start with its own
production delay, and it never stocks out of raw materials.

### 1.3 Cost function (Sterman's standard)
- Holding: `$0.50` per unit per week
- Backlog: `$1.00` per unit per week
- Team cost = sum across all four echelons

### 1.4 Demand generators (make these swappable)
- **Step**: 4/week for weeks 1–4, then 8/week thereafter. *The classic. Use for headline results.*
- **Stationary stochastic**: `N(mu=10, sigma=2)`, truncated at 0.
- **AR(1)**: `d_t = mu + rho*(d_{t-1} - mu) + eps_t`. Sweep `rho` — Chen et al. predict bullwhip
  grows with autocorrelation, so this is a validation test.
- **Seasonal / burst**: for robustness.

### 1.5 Engineering requirements
- Fully deterministic given a seed. Log *every* state variable every week to a tidy
  dataframe — you cannot re-run 10,000 experiments to recover a variable you forgot.
- Horizon: 52 weeks. Discard the first ~10 as warm-up when computing statistics; report
  that you did.
- Write unit tests: conservation of units (nothing created or destroyed), zero-demand
  chain stays at equilibrium, known-analytical base-stock case matches theory.

---

## 2. Phase 2 — The agent policies (weeks 3–5)

Define one interface — `agent.order(observation) -> int` — and implement all policies
behind it. The observation object is what determines your information-sharing conditions
later, so design it deliberately.

### 2.1 Base-stock (order-up-to)
```
O_t = max(0, S* - (inventory - backlog + supply_line))
```
`S*` set from the newsvendor critical ratio `c_b / (c_b + c_h) = 1/1.5 ≈ 0.667` over
lead-time demand. This is the near-optimal rational benchmark. Under deterministic demand
and known lead time it should produce **near-zero bullwhip** — if yours doesn't, your
engine has a bug. Use this as your correctness check.

### 2.2 Anchor-and-adjust (Sterman 1989) — the human-behavior model
```
O_t = max(0, D_hat_t + alpha_S * (S' - S_t - beta * SL_t))
```
- `D_hat_t` = exponentially smoothed demand forecast, smoothing `theta`
- `S'` = desired stock, `S_t` = current net stock, `SL_t` = supply line
- `alpha_S` = stock adjustment rate
- **`beta` = supply line weighting — this is the whole story.** `beta = 1` means fully
  accounting for in-transit orders; Sterman's estimated human values cluster around
  **0.25–0.34**. Low `beta` produces the bullwhip.

Sweep `beta` from 0 to 1 and plot bullwhip ratio against it. That single figure is
probably your paper's Figure 1.

### 2.3 ML-learned agent
Formulate as an MDP:
- **State**: recent inventory, backlog, supply line, last `k` demands/orders received, and
  (in information-sharing conditions) downstream state.
- **Action**: order quantity. Either discretize (e.g. `d_t + a` where `a ∈ [-8, +8]`, the
  Oroojlooyjadid formulation) or use a continuous policy.
- **Reward**: negative cost. **Design decision to be explicit about:** local echelon cost
  vs. shared team cost. Local reward is realistic but selfish; team reward is a form of
  implicit coordination and is arguably already a "mitigation." Run both; the comparison
  is itself a result.
- **Algorithm**: start with PPO (stable, forgiving) via Stable-Baselines3. DQN if you
  discretize. Don't start with anything exotic.

**Training protocol** — this is where projects like this lose credibility:
- Train the learned agent against *fixed* opponents (other echelons on known policies).
  Simultaneous learning by all four is non-stationary and much harder; note it as future work.
- Hold out demand seeds between training and evaluation. Report performance on unseen seeds only.
- Train ≥5 seeds per configuration and report mean ± std. Single-seed RL results are noise.

---

## 3. Phase 3 — Quantifying bullwhip (week 6)

Do not report a single number. The metrics disagree with each other, and that's informative.

| Metric | Definition | What it captures |
|---|---|---|
| Bullwhip ratio (per echelon) | `Var(orders_i) / Var(orders_{i-1})` | Stage-to-stage amplification |
| Cumulative amplification | `Var(orders_factory) / Var(customer_demand)` | End-to-end headline number |
| Net stock amplification | `Var(net_stock_i) / Var(demand)` | Inventory instability — often the real cost driver |
| Peak order ratio | `max(orders_i) / mean(demand)` | Transient severity the variance ratio hides |
| Phase lag | Cross-correlation lag between demand and orders | Oscillation delay upstream |
| Total team cost | Sum of holding + backlog over horizon | The economic bottom line |
| Time-to-settle | Weeks until orders stay within ±10% of steady state | Stability |

**Report cost and variance separately.** They can move in opposite directions, and a
policy that lowers variance while raising cost is a genuinely interesting finding.

---

## 4. Phase 4 — Heterogeneous chain experiments (weeks 7–8)

This is the novel core. With 3 policy types across 4 positions there are 81 configurations —
tractable to run exhaustively.

Questions to answer:
1. **Position sensitivity.** Does an ML agent at the Retailer help more than at the Factory?
   Hypothesis: upstream positions have more leverage because they sit atop the amplification cascade.
2. **Contamination.** Does a single anchor-and-adjust agent destabilize a chain of otherwise
   rational agents? How far does the disturbance propagate?
3. **Rescue.** Can a single learned agent stabilize a chain of three behavioral agents — and
   what does it *learn to do*? (Probably: hold buffer stock and absorb variance at its own
   cost. Check whether it sacrifices local cost for team stability.)
4. **Shapley-style attribution.** Attribute total team cost to individual echelons' policy
   choices. This makes the "which echelon matters most" claim quantitative rather than anecdotal.

---

## 5. Phase 5 — Mitigations (weeks 9–10)

Each mitigation is an **information or control structure change**, implemented by changing
what the observation contains or who makes the decision. Test each against every policy
configuration — the key question is whether mitigations help *all* policy types equally.

### 5.1 Information sharing
- **Level 0 (baseline)**: each echelon sees only orders from immediately downstream.
- **Level 1 (POS sharing)**: all echelons see true customer demand.
- **Level 2 (full visibility)**: all echelons see all inventory and backlog positions.

Expected: Level 1 removes the demand-signal-processing component of bullwhip but *not*
the behavioral component — base-stock agents should improve substantially, anchor-and-adjust
agents much less, because their problem is supply-line misperception, not bad forecasts.
**If you find that, it's a clean and quotable result.**

### 5.2 Vendor-Managed Inventory (VMI)
The upstream echelon decides replenishment for the downstream one, observing its inventory
directly. Effectively removes one order-decision node and its associated delay. Specify
carefully: who bears holding cost, and what is the service-level constraint? VMI's benefit
is partly delay elimination and partly information — design a variant that isolates each,
or reviewers will ask.

### 5.3 Additional arms worth including
- **Lead time reduction**: halve `L_order` and `L_ship`. Often dominates information sharing.
  Worth reporting honestly even if it undercuts the fashionable interventions.
- **Echelon base-stock / centralized control**: the theoretical lower bound on cost. Gives
  every other result a normalized "% of achievable improvement" interpretation.
- **Order smoothing constraint**: cap week-over-week order change. Cheap, and often
  surprisingly effective.

---

## 6. Phase 6 — Analysis and write-up (weeks 11–12)

### Figures to build toward
1. Bullwhip ratio vs. supply-line weighting `beta` — the Sterman replication.
2. Order trajectories over time, four echelons, one panel per policy type — the classic
   amplification visual.
3. Heatmap: policy configuration × echelon position, colored by team cost.
4. Grouped bars: mitigation × policy type, showing bullwhip reduction — the interaction
   effect is the point.
5. Pareto frontier: variance vs. cost across all configurations.

### Statistical discipline
- ≥100 demand seeds per configuration; report confidence intervals, not point estimates.
- Bootstrap CIs on variance ratios (variance ratios are skewed; don't assume normality).
- Correct for multiple comparisons across your configuration sweep.

### Validity threats to address explicitly (reviewers will raise these)
- Your anchor-and-adjust agents are a *model* of humans, not humans. Cite Sterman's
  estimated parameters and stay inside their empirical range.
- RL results depend on reward shaping and training budget — report both, and show the
  learning curves.
- Serial four-echelon chains are a simplification of real networks. Say so.

---

## 7. Recommended repository structure

```
beergame/
  env/          engine.py, demand.py, config.py
  agents/       base_stock.py, anchor_adjust.py, rl_agent.py, interface.py
  experiments/  sweeps.py, heterogeneous.py, mitigations.py
  analysis/     metrics.py, figures.py, stats.py
  tests/        test_conservation.py, test_equilibrium.py, test_analytical.py
  results/      raw logs (gitignored), processed dataframes
  paper/
```

Suggested stack: NumPy/Pandas for the engine, Gymnasium for the RL interface,
Stable-Baselines3 for PPO/DQN, Matplotlib or Plotnine for figures, Hydra or plain YAML
for experiment configs.

---

## 8. Suggested first week

1. Read Sterman (1989) properly, especially the anchor-and-adjust formulation.
2. Play the game once online (MIT has a free web version) so you have physical intuition
   for the oscillation.
3. Build the engine with a single hard-coded "order what you received" policy. Verify
   conservation of units.
4. Add base-stock agents. Confirm near-zero bullwhip on deterministic demand — that's your
   engine-correctness proof.
5. Add anchor-and-adjust with `beta = 0.25`. Confirm the bullwhip appears.

If step 5 reproduces Sterman's oscillation, you have a working platform and everything
after that is experiments.

---

## 9. Scope warning

The full plan above is genuinely paper-scale. If time is limited, cut in this order:
drop the Shapley attribution, then the extra mitigation arms, then reduce the
heterogeneous sweep to a targeted subset. **Do not cut** the multi-seed protocol or the
base-stock validation — those are what separate a credible result from a plausible-looking one.

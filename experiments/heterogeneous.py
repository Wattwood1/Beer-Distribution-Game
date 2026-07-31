"""Position-sensitivity experiment (paper guide Phase 4, question 1).

Baseline: four homogeneous anchor-and-adjust(beta=0.25) agents -- the Day-3
Sterman reproduction. Then, one config per echelon, swap a single position
to base-stock (local/Level-0 forecaster -- the same baseline condition used
throughout the information-sharing experiment) while the other three stay
anchor-and-adjust, holding demand/params/costs fixed otherwise.

Reports per-echelon bullwhip ratio (Var(orders_i) / Var(customer demand),
full horizon -- the same convention as experiments/sweeps.py's Factory-only
bullwhip_ratio, generalized to every echelon) and total post-warmup team
cost, so both the overall (cost) and localized (per-echelon variance)
effects of position are visible.

Agents are stateful (D_hat, demand-history windows persist across order()
calls), so each config below builds fresh agent instances rather than
reusing objects across engine.run() calls -- reusing them would leak state
from one config's run into the next.
"""

from typing import Dict, Optional

import pandas as pd

from agents.anchor_adjust import make_anchor_and_adjust_agents
from agents.base_stock import make_base_stock_agents
from env.config import ECHELON_NAMES, SimulationConfig
from env.demand import step_demand
from env.engine import BeerGameEngine
from experiments.learned_policy import post_warmup_team_cost


def per_echelon_bullwhip_ratios(df: pd.DataFrame) -> Dict[str, float]:
    """Var(orders_i) / Var(customer demand) for every echelon, full horizon."""
    customer_demand_var = df.loc[df["echelon"] == "Retailer", "order_received"].var()
    return {
        echelon: df.loc[df["echelon"] == echelon, "order_placed"].var() / customer_demand_var
        for echelon in ECHELON_NAMES
    }


def run_position_sensitivity_experiment(config: Optional[SimulationConfig] = None) -> pd.DataFrame:
    """One row per config: baseline, then one per position swapped to base-stock."""
    config = config or SimulationConfig()

    labels_and_swaps = [("baseline (all anchor-and-adjust)", None)] + [
        (f"base-stock at {echelon}", i) for i, echelon in enumerate(ECHELON_NAMES)
    ]

    rows = []
    for label, swap_index in labels_and_swaps:
        agents = make_anchor_and_adjust_agents(config)  # fresh instances for every config
        if swap_index is not None:
            base_stock_agents = make_base_stock_agents(config)  # fresh instances
            agents[swap_index] = base_stock_agents[swap_index]

        engine = BeerGameEngine(config, agents, step_demand)
        df = engine.run()

        ratios = per_echelon_bullwhip_ratios(df)
        row = {"config": label, "team_cost": post_warmup_team_cost(df, config)}
        row.update({f"bullwhip_{echelon}": ratios[echelon] for echelon in ECHELON_NAMES})
        rows.append(row)

    return pd.DataFrame(rows)


if __name__ == "__main__":
    pd.set_option("display.width", 200)
    print(run_position_sensitivity_experiment().to_string(index=False))

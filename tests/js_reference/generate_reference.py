"""Generates the ground-truth reference run for the JS engine port.

Fully-specified deterministic test case: step demand (4 -> 8 at week 5),
all four echelons running anchor-and-adjust with beta=0.25, theta=0.3,
alpha=0.25, canonical setup (initial inventory 12, 2-week order + 2-week
ship delays), 52 weeks. Dumps the full per-week, per-echelon state exactly
as the Python engine logs it -- the JS port must reproduce every field of
every row exactly (see tests/js_reference/verify.js).
"""

import json
import os

from agents.anchor_adjust import make_anchor_and_adjust_agents
from env.config import SimulationConfig
from env.demand import step_demand
from env.engine import BeerGameEngine

config = SimulationConfig()
agents = make_anchor_and_adjust_agents(config, theta=0.3, alpha=0.25, beta=0.25)
engine = BeerGameEngine(config, agents, step_demand)
df = engine.run()

records = df.to_dict(orient="records")

out = {
    "config": {
        "n_echelons": config.n_echelons,
        "order_delay": config.order_delay,
        "ship_delay": config.ship_delay,
        "production_delay": config.production_delay,
        "initial_inventory": config.initial_inventory,
        "horizon_weeks": config.horizon_weeks,
        "warmup_weeks": config.warmup_weeks,
        "holding_cost": config.holding_cost,
        "backlog_cost": config.backlog_cost,
    },
    "agent_params": {"policy": "anchor_and_adjust", "theta": 0.3, "alpha": 0.25, "beta": 0.25, "safety_buffer": 4.0},
    "demand": "step_demand (4 units/wk weeks 1-4, 8 units/wk weeks 5+)",
    "rows": records,
}

out_path = os.path.join(os.path.dirname(__file__), "reference_run.json")
with open(out_path, "w") as f:
    json.dump(out, f, indent=2)

print(f"wrote {len(records)} rows to {out_path}")

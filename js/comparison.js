// End-game comparison: runs the SAME verified engine and agent factories
// used everywhere else in this project, non-interactively, after a game
// is over -- swapping a single algorithmic policy into the player's
// position while the other three echelons keep whatever policy the real
// playthrough used. This is the same "swap one echelon" pattern as
// experiments/heterogeneous.py, just mirrored in JS. No new simulation
// logic: engine.run() and the agent factories are called completely
// unchanged, so nothing here needs re-verification against the Python
// reference (that gate covers run()/step(), which this file never
// touches).

import { ECHELON_NAMES } from "./config.js";
import { makeAnchorAndAdjustAgents } from "./agents/anchorAdjust.js";
import { makeBaseStockAgents } from "./agents/baseStock.js";
import { BeerGameEngine } from "./engine.js";

const POLICY_FACTORIES = {
  base_stock: makeBaseStockAgents,
  anchor_and_adjust: makeAnchorAndAdjustAgents,
};

const POLICY_LABELS = {
  base_stock: "Base-stock (rational optimum)",
  anchor_and_adjust: "Anchor-and-adjust (human-like)",
};

function totalCostForEchelon(rows, echelon) {
  return rows.filter((r) => r.echelon === echelon).reduce((sum, r) => sum + r.cost, 0);
}

// Runs one comparison agent at playerEchelon's position, other three
// echelons unchanged from the real game's configuration. Returns the full
// row set (all echelons, all weeks) and the comparison agent's own total
// cost, summed over the full horizon -- the same window
// GameController.playerCumulativeCost already uses, so the numbers are
// directly comparable to the player's own score.
function runComparisonAgent(policy, { config, playerEchelon, otherPolicy, otherPolicyParams, demandFn }) {
  const playerIndex = ECHELON_NAMES.indexOf(playerEchelon);
  const agents = POLICY_FACTORIES[otherPolicy](config, otherPolicyParams);
  const comparisonAgents = POLICY_FACTORIES[policy](config);
  agents[playerIndex] = comparisonAgents[playerIndex];

  const engine = new BeerGameEngine(config, agents, demandFn);
  const rows = engine.run();
  return { rows, totalCost: totalCostForEchelon(rows, playerEchelon) };
}

// Runs both comparison policies and returns a small summary keyed by
// policy name, each with a human label and total cost.
export function runComparisons({ config, playerEchelon, otherPolicy, otherPolicyParams = {}, demandFn }) {
  const results = {};
  for (const policy of Object.keys(POLICY_FACTORIES)) {
    const { totalCost } = runComparisonAgent(policy, { config, playerEchelon, otherPolicy, otherPolicyParams, demandFn });
    results[policy] = { label: POLICY_LABELS[policy], totalCost };
  }
  return results;
}

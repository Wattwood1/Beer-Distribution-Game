// Anchor-and-adjust (Sterman 1989) -- ported from agents/anchor_adjust.py.
// O_t = max(0, D_hat_t + alpha * (S_desired_t - current_stock_t - beta * supply_line_t))
// See the Python module's docstring for the full explanation of theta,
// alpha, and beta; this is a direct, line-for-line port, not a
// reinterpretation.

import { pythonRound } from "../round.js";

export class AnchorAndAdjustAgent {
  constructor(
    leadTimeWeeks,
    { theta = 0.3, alpha = 0.25, beta = 0.25, safetyBuffer = 4.0, expectedDemandPerWeek = null } = {}
  ) {
    this.leadTimeWeeks = leadTimeWeeks;
    this.theta = theta;
    this.alpha = alpha;
    this.beta = beta;
    this.safetyBuffer = safetyBuffer;
    this.expectedDemandPerWeek = expectedDemandPerWeek;
    this.dHat = null; // lazily seeded from the first observed signal
  }

  order(observation) {
    const signal = this.expectedDemandPerWeek !== null ? this.expectedDemandPerWeek : observation.incomingOrder;
    if (this.dHat === null) {
      this.dHat = signal;
    } else {
      this.dHat = this.theta * signal + (1 - this.theta) * this.dHat;
    }

    const sDesired = this.dHat * this.leadTimeWeeks + this.safetyBuffer;
    const currentStock = observation.inventory - observation.backlog;
    const gap = sDesired - currentStock - this.beta * observation.supplyLine;
    return Math.max(0, pythonRound(this.dHat + this.alpha * gap));
  }
}

// One AnchorAndAdjustAgent per echelon, each with its own lead time.
// Echelons 0..n-2 wait orderDelay + shipDelay weeks for a replenishment
// order to arrive; the Factory (last echelon) has no supplier -- its only
// delay is its own productionDelay.
export function makeAnchorAndAdjustAgents(config, params = {}) {
  const factoryIndex = config.nEchelons - 1;
  const agents = [];
  for (let i = 0; i < config.nEchelons; i++) {
    const leadTime = i === factoryIndex ? config.productionDelay : config.orderDelay + config.shipDelay;
    agents.push(new AnchorAndAdjustAgent(leadTime, params));
  }
  return agents;
}

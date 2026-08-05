// Base-stock (order-up-to) policy -- ported from agents/base_stock.py.
// O_t = max(0, S_star - (inventory - backlog + supply_line))
// S_star = demand_estimate * lead_time_weeks + safety_buffer, from a
// pluggable forecaster -- see the Python module's docstring for why two
// forecast modes exist (KnownDemandForecaster is the engine-correctness
// gate; LocalMovingAverageForecaster is the Level-0 baseline).

import { pythonRound } from "../round.js";

export class KnownDemandForecaster {
  constructor(expectedDemandPerWeek) {
    this.expectedDemandPerWeek = expectedDemandPerWeek;
  }

  estimate(_observation) {
    return this.expectedDemandPerWeek;
  }
}

export class LocalMovingAverageForecaster {
  constructor(window) {
    this.window = window;
    this.history = [];
  }

  estimate(observation) {
    this.history.push(observation.incomingOrder);
    if (this.history.length > this.window) {
      this.history.shift();
    }
    const sum = this.history.reduce((a, b) => a + b, 0);
    return sum / this.history.length;
  }
}

export class BaseStockAgent {
  constructor(leadTimeWeeks, forecaster, safetyBuffer = 4.0) {
    this.leadTimeWeeks = leadTimeWeeks;
    this.forecaster = forecaster;
    this.safetyBuffer = safetyBuffer;
  }

  order(observation) {
    const demandEstimate = this.forecaster.estimate(observation);
    const sStar = demandEstimate * this.leadTimeWeeks + this.safetyBuffer;
    const netStock = observation.inventory - observation.backlog + observation.supplyLine;
    return Math.max(0, pythonRound(sStar - netStock));
  }
}

// One BaseStockAgent per echelon, each with its own correct lead time. If
// expectedDemandPerWeek is given, every agent uses the omniscient
// KnownDemandForecaster; otherwise every agent uses a
// LocalMovingAverageForecaster over its own lead-time window.
export function makeBaseStockAgents(config, { expectedDemandPerWeek = null, safetyBuffer = 4.0 } = {}) {
  const factoryIndex = config.nEchelons - 1;
  const agents = [];
  for (let i = 0; i < config.nEchelons; i++) {
    const leadTime = i === factoryIndex ? config.productionDelay : config.orderDelay + config.shipDelay;
    const forecaster =
      expectedDemandPerWeek !== null
        ? new KnownDemandForecaster(expectedDemandPerWeek)
        : new LocalMovingAverageForecaster(leadTime);
    agents.push(new BaseStockAgent(leadTime, forecaster, safetyBuffer));
  }
  return agents;
}

// Simulation-wide configuration. Mirrors env/config.py's SimulationConfig
// and ECHELON_NAMES exactly -- see that file for field meanings.

export const ECHELON_NAMES = ["Retailer", "Wholesaler", "Distributor", "Factory"];

export function defaultConfig(overrides = {}) {
  return {
    nEchelons: 4,
    orderDelay: 2,
    shipDelay: 2,
    productionDelay: 2,
    initialInventory: 12,
    horizonWeeks: 52,
    warmupWeeks: 10,
    holdingCost: 0.5,
    backlogCost: 1.0,
    ...overrides,
  };
}

// Core simulation engine: the weekly physics of the beer distribution
// game. Ported faithfully from env/engine.py -- same six-phase weekly
// sequence, same supply-line accounting (its own accumulator, incremented
// on order and decremented on receipt, never derived from the pipeline
// contents), same delay pipelines (plain arrays used as FIFOs: push() to
// append, shift() for popleft()). Echelons are indexed
// 0=Retailer, 1=Wholesaler, 2=Distributor, 3=Factory; each echelon's
// supplier is index+1 and its customer is index-1 (or the external
// customer for the Retailer, and no supplier for the Factory).
//
// Output row field names are intentionally snake_case (order_placed, not
// orderPlaced) to match the Python engine's logged column names exactly --
// this is the ground truth format tests/js_reference/reference_run.json
// uses, and tests/js_reference/verify.mjs diffs against it field-by-field.

import { ECHELON_NAMES } from "./config.js";

class EchelonState {
  constructor({ inventory, incomingOrders, incomingShipments, incomingProduction }) {
    this.inventory = inventory;
    this.backlog = 0;
    this.supplyLine = 0;
    this.incomingOrders = incomingOrders;
    this.incomingShipments = incomingShipments;
    this.incomingProduction = incomingProduction;
  }
}

export class BeerGameEngine {
  constructor(config, agents, demandFn) {
    if (agents.length !== config.nEchelons) {
      throw new Error(`expected ${config.nEchelons} agents, got ${agents.length}`);
    }
    this.config = config;
    this.agents = agents;
    this.demandFn = demandFn;
    this.factoryIndex = config.nEchelons - 1;

    this.states = [];
    for (let i = 0; i < config.nEchelons; i++) {
      this.states.push(
        new EchelonState({
          inventory: config.initialInventory,
          incomingOrders: i !== 0 ? new Array(config.orderDelay).fill(0) : [],
          incomingShipments: i !== this.factoryIndex ? new Array(config.shipDelay).fill(0) : [],
          incomingProduction: i === this.factoryIndex ? new Array(config.productionDelay).fill(0) : [],
        })
      );
    }

    // The two system-boundary counters the conservation test relies on:
    // production is the only source of new units, customer delivery is
    // the only sink.
    this.cumulativeProduced = 0;
    this.cumulativeDeliveredToCustomer = 0;
  }

  step(week) {
    const n = this.config.nEchelons;
    const states = this.states;

    // Phases 1-2: receive arriving shipment/production, then the
    // downstream order (or, for the Retailer, exogenous customer
    // demand), adding it to backlog.
    const receivedStock = new Array(n).fill(0);
    const receivedOrder = new Array(n).fill(0);
    for (let i = 0; i < n; i++) {
      const st = states[i];
      const qty = i === this.factoryIndex ? st.incomingProduction.shift() : st.incomingShipments.shift();
      st.inventory += qty;
      st.supplyLine -= qty;
      receivedStock[i] = qty;

      const orderIn = i === 0 ? this.demandFn(week) : st.incomingOrders.shift();
      st.backlog += orderIn;
      receivedOrder[i] = orderIn;
    }

    // Phase 3: ship to satisfy backlog as far as inventory allows.
    const shipped = new Array(n).fill(0);
    for (let i = 0; i < n; i++) {
      const st = states[i];
      const qty = Math.min(st.inventory, st.backlog);
      st.inventory -= qty;
      st.backlog -= qty;
      shipped[i] = qty;
    }

    // Phase 4: record cost.
    const cost = states.map((st) => this.config.holdingCost * st.inventory + this.config.backlogCost * st.backlog);

    // Phase 5: each agent decides its new order from the post-shipment
    // state, using only its own observation.
    const orderPlaced = new Array(n).fill(0);
    for (let i = 0; i < n; i++) {
      const st = states[i];
      const observation = {
        echelon: ECHELON_NAMES[i],
        week,
        inventory: st.inventory,
        backlog: st.backlog,
        supplyLine: st.supplyLine,
        incomingOrder: receivedOrder[i],
      };
      orderPlaced[i] = this.agents[i].order(observation);
    }

    // Phase 6: propagate this week's shipments and orders, and update
    // supply lines and the two boundary counters. Applied only now, so
    // nothing pushed here was visible to any agent's observation above.
    for (let i = 0; i < n; i++) {
      const st = states[i];
      st.supplyLine += orderPlaced[i];

      if (i === 0) {
        this.cumulativeDeliveredToCustomer += shipped[i];
      } else {
        states[i - 1].incomingShipments.push(shipped[i]);
      }

      if (i === this.factoryIndex) {
        st.incomingProduction.push(orderPlaced[i]);
        this.cumulativeProduced += orderPlaced[i];
      } else {
        states[i + 1].incomingOrders.push(orderPlaced[i]);
      }
    }

    return states.map((st, i) => ({
      week,
      echelon: ECHELON_NAMES[i],
      inventory: st.inventory,
      backlog: st.backlog,
      supply_line: st.supplyLine,
      shipment_received: receivedStock[i],
      order_received: receivedOrder[i],
      shipped: shipped[i],
      order_placed: orderPlaced[i],
      cost: cost[i],
      cumulative_produced: this.cumulativeProduced,
      cumulative_delivered_to_customer: this.cumulativeDeliveredToCustomer,
    }));
  }

  run() {
    const rows = [];
    for (let week = 1; week <= this.config.horizonWeeks; week++) {
      rows.push(...this.step(week));
    }
    return rows;
  }
}

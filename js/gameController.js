// Turn-based game controller: wraps the verified engine so a human can
// play ONE echelon while the other three run on an algorithmic policy.
// Pure logic, zero DOM dependencies -- see
// tests/js_reference/game_controller_smoke.mjs for a non-interactive
// Node-only test of this file.
//
// INFORMATION RESTRICTION: the player's view (getPlayerView / the return
// value of beginTurn) is never anything more than
// weekState.observations[playerIndex] plus this controller's own
// tracking of the player's past orders and running cost -- the same
// narrow Observation object every algorithmic agent already receives from
// engine.beginWeek(). There is no second, fuller view that gets filtered
// down for display; the fuller view (weekState.observations for other
// echelons, and the full per-week log) is never read by this class until
// getFinalReveal(), which requires the game to be over. That's what makes
// the restriction structural rather than a UI convention.

import { ECHELON_NAMES } from "./config.js";
import { makeAnchorAndAdjustAgents } from "./agents/anchorAdjust.js";
import { makeBaseStockAgents } from "./agents/baseStock.js";
import { BeerGameEngine } from "./engine.js";

const POLICY_FACTORIES = {
  anchor_and_adjust: makeAnchorAndAdjustAgents,
  base_stock: makeBaseStockAgents,
};

export class GameController {
  constructor({ config, playerEchelon, otherPolicy = "anchor_and_adjust", otherPolicyParams = {}, demandFn }) {
    const playerIndex = ECHELON_NAMES.indexOf(playerEchelon);
    if (playerIndex === -1) {
      throw new Error(`playerEchelon must be one of ${ECHELON_NAMES.join(", ")}, got "${playerEchelon}"`);
    }
    const makeAgents = POLICY_FACTORIES[otherPolicy];
    if (!makeAgents) {
      throw new Error(`otherPolicy must be one of ${Object.keys(POLICY_FACTORIES).join(", ")}, got "${otherPolicy}"`);
    }

    this.config = config;
    this.playerEchelon = playerEchelon;
    this.playerIndex = playerIndex;

    const agents = makeAgents(config, otherPolicyParams);
    // Never called in normal play -- the controller supplies the
    // player's order directly to finishWeek() and never lets the engine's
    // own step()/agents[i].order() path run for this index. Throwing here
    // is a defensive assertion that nothing bypassed the controller.
    agents[playerIndex] = {
      order: () => {
        throw new Error("player's order must come from GameController.submitOrder(), not engine.step()");
      },
    };
    this.engine = new BeerGameEngine(config, agents, demandFn);

    this.currentWeek = 1;
    this.fullHistory = []; // all 4 echelons, every week -- not exposed until getFinalReveal()
    this.playerOrderHistory = [];
    this.playerCumulativeCost = 0;
    this._pendingWeekState = null;
  }

  isGameOver() {
    return this.currentWeek > this.config.horizonWeeks;
  }

  // Runs phases 1-4 for the current week and returns the player's
  // restricted view. Must be followed by submitOrder() before the next
  // beginTurn().
  beginTurn() {
    if (this.isGameOver()) {
      throw new Error("game is over");
    }
    if (this._pendingWeekState) {
      throw new Error("a turn is already in progress; call submitOrder() first");
    }
    this._pendingWeekState = this.engine.beginWeek(this.currentWeek);
    return this.getPlayerView();
  }

  // The restricted view itself -- see the module docstring above for why
  // this is the only thing this class ever hands to a caller mid-game.
  getPlayerView() {
    const obs = this._pendingWeekState.observations[this.playerIndex];
    const st = this.engine.states[this.playerIndex];
    // The player's own receiving-side delay queue -- incomingShipments for
    // everyone except the Factory, which uses incomingProduction instead.
    // This is the player's own EchelonState property (same object
    // inventory/backlog already come from), not another echelon's state,
    // and it's already-committed data (the supplier already decided to
    // ship it) rather than a prediction -- see js/gameController.js's
    // module docstring and the Phase 3 plan for why this is NOT the same
    // as computing "arrival week" from the player's own order history,
    // which would be unreliable whenever the supplier is backlogged.
    // Index 0 arrives next week; the array is one slot short of
    // config.shipDelay/productionDelay right now because this week's
    // shift() already happened (in beginWeek) but this week's push()
    // hasn't (that's finishWeek, still ahead).
    const shipmentsInTransit =
      this.playerIndex === this.engine.factoryIndex ? [...st.incomingProduction] : [...st.incomingShipments];
    return {
      echelon: this.playerEchelon,
      week: obs.week,
      inventory: obs.inventory,
      backlog: obs.backlog,
      orderReceivedFromDownstream: obs.incomingOrder,
      shipmentArriving: obs.shipmentReceived,
      shipmentsInTransit,
      costThisWeek: obs.cost,
      cumulativeCostBeforeThisWeek: this.playerCumulativeCost,
      orderHistory: [...this.playerOrderHistory],
    };
  }

  // Completes the current week: computes the other three echelons'
  // orders from their own (real) agents, slots the player's quantity in
  // at their index, and runs phase 6.
  submitOrder(quantity) {
    if (!this._pendingWeekState) {
      throw new Error("call beginTurn() before submitOrder()");
    }
    if (!Number.isInteger(quantity) || quantity < 0) {
      throw new Error(`order must be a non-negative integer, got ${quantity}`);
    }

    const weekState = this._pendingWeekState;
    const observations = weekState.observations;
    const orderPlaced = observations.map((obs, i) =>
      i === this.playerIndex ? quantity : this.engine.agents[i].order(obs)
    );

    const rows = this.engine.finishWeek(this.currentWeek, weekState, orderPlaced);
    this.fullHistory.push(...rows);

    this.playerOrderHistory.push(quantity);
    this.playerCumulativeCost += observations[this.playerIndex].cost;

    this._pendingWeekState = null;
    this.currentWeek += 1;

    return { gameOver: this.isGameOver() };
  }

  // Only callable once the game is over -- the full chain (including the
  // bullwhip the player never saw) plus their final score.
  getFinalReveal() {
    if (!this.isGameOver()) {
      throw new Error("game is not over yet");
    }
    return {
      fullHistory: this.fullHistory,
      playerEchelon: this.playerEchelon,
      playerTotalCost: this.playerCumulativeCost,
      playerOrderHistory: [...this.playerOrderHistory],
    };
  }
}

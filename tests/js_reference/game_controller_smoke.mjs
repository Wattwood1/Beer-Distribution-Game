// Non-interactive smoke test for GameController -- no DOM, no human, just
// a scripted "player" so the turn-based logic (and the information
// restriction) can be verified the same way verify.mjs verifies the
// engine. Not a byte-for-byte ground-truth comparison (there's no Python
// reference for interactive play); this checks internal consistency and
// invariants instead. Exits non-zero on any failed assertion.

import { defaultConfig, ECHELON_NAMES } from "../../js/config.js";
import { stepDemand } from "../../js/demand.js";
import { GameController } from "../../js/gameController.js";

const failures = [];

function assert(condition, message) {
  if (!condition) failures.push(message);
}

function assertEqual(actual, expected, message) {
  if (actual !== expected) failures.push(`${message}: expected ${expected}, got ${actual}`);
}

// --- Test 1: full 52-week play-through as Wholesaler, "order what I received" strategy ---
{
  const config = defaultConfig();
  const game = new GameController({
    config,
    playerEchelon: "Wholesaler",
    otherPolicy: "anchor_and_adjust",
    otherPolicyParams: { theta: 0.3, alpha: 0.25, beta: 0.25 },
    demandFn: stepDemand,
  });

  const EXPECTED_VIEW_KEYS = [
    "echelon",
    "week",
    "inventory",
    "backlog",
    "orderReceivedFromDownstream",
    "shipmentArriving",
    "shipmentsInTransit",
    "costThisWeek",
    "cumulativeCostBeforeThisWeek",
    "orderHistory",
  ].sort();

  let weeksPlayed = 0;
  let runningCost = 0;
  while (!game.isGameOver()) {
    const view = game.beginTurn();

    // Information restriction: the view must contain exactly these
    // fields -- nothing about any other echelon, no raw engine state.
    const actualKeys = Object.keys(view).sort();
    assert(
      JSON.stringify(actualKeys) === JSON.stringify(EXPECTED_VIEW_KEYS),
      `week ${weeksPlayed + 1}: player view keys ${JSON.stringify(actualKeys)} != expected ${JSON.stringify(EXPECTED_VIEW_KEYS)}`
    );
    assert(
      Array.isArray(view.shipmentsInTransit) && view.shipmentsInTransit.length < config.shipDelay,
      `week ${weeksPlayed + 1}: shipmentsInTransit should be an array shorter than shipDelay (this week's slot hasn't been pushed yet), got ${JSON.stringify(view.shipmentsInTransit)}`
    );
    assert(
      view.shipmentsInTransit.every((q) => Number.isInteger(q) && q >= 0),
      `week ${weeksPlayed + 1}: shipmentsInTransit entries should all be non-negative integers, got ${JSON.stringify(view.shipmentsInTransit)}`
    );
    assertEqual(view.echelon, "Wholesaler", `week ${weeksPlayed + 1}: view.echelon`);
    assertEqual(view.cumulativeCostBeforeThisWeek, runningCost, `week ${weeksPlayed + 1}: cumulativeCostBeforeThisWeek`);
    assertEqual(view.orderHistory.length, weeksPlayed, `week ${weeksPlayed + 1}: orderHistory length before this week's order`);

    const orderQty = view.orderReceivedFromDownstream; // "order what I received" -- naive.py's PassThroughAgent, ported to a player strategy
    const { gameOver } = game.submitOrder(orderQty);
    runningCost += view.costThisWeek;
    weeksPlayed += 1;
    assertEqual(gameOver, game.isGameOver(), `week ${weeksPlayed}: gameOver flag matches isGameOver()`);
  }

  assertEqual(weeksPlayed, config.horizonWeeks, "total weeks played");

  const reveal = game.getFinalReveal();
  assertEqual(reveal.fullHistory.length, config.horizonWeeks * config.nEchelons, "fullHistory row count");
  assertEqual(reveal.playerOrderHistory.length, config.horizonWeeks, "revealed playerOrderHistory length");
  assertEqual(reveal.playerTotalCost, runningCost, "playerTotalCost matches sum of per-week costThisWeek seen during play");

  // Cross-check against the full history the player never saw: summing
  // the Wholesaler's own cost column in fullHistory should agree exactly
  // with what the restricted per-turn view reported as costThisWeek.
  const wholesalerRows = reveal.fullHistory.filter((r) => r.echelon === "Wholesaler");
  const costFromFullHistory = wholesalerRows.reduce((sum, r) => sum + r.cost, 0);
  assertEqual(reveal.playerTotalCost, costFromFullHistory, "playerTotalCost vs. sum of fullHistory's Wholesaler cost column");

  // Every echelon, every week should be present in the reveal -- the
  // player gets the whole chain only now, not during play.
  for (const echelon of ECHELON_NAMES) {
    const rows = reveal.fullHistory.filter((r) => r.echelon === echelon);
    assertEqual(rows.length, config.horizonWeeks, `fullHistory row count for ${echelon}`);
  }
}

// --- Test 2: playing as Retailer means orderReceivedFromDownstream IS true customer demand ---
{
  const config = defaultConfig();
  const game = new GameController({
    config,
    playerEchelon: "Retailer",
    otherPolicy: "anchor_and_adjust",
    demandFn: stepDemand,
  });
  for (let week = 1; week <= 6; week++) {
    const view = game.beginTurn();
    assertEqual(view.orderReceivedFromDownstream, stepDemand(week), `Retailer week ${week}: sees true customer demand directly`);
    game.submitOrder(8);
  }
}

// --- Test 3: playing as Factory (last in phase-5 order) works ---
{
  const config = defaultConfig();
  const game = new GameController({
    config,
    playerEchelon: "Factory",
    otherPolicy: "base_stock",
    demandFn: stepDemand,
  });
  while (!game.isGameOver()) {
    const view = game.beginTurn();
    assertEqual(view.echelon, "Factory", "Factory game: view.echelon");
    game.submitOrder(8);
  }
  const reveal = game.getFinalReveal();
  assertEqual(reveal.playerEchelon, "Factory", "Factory game: reveal.playerEchelon");
}

// --- Test 4: misuse guards ---
{
  const config = defaultConfig();
  const game = new GameController({ config, playerEchelon: "Distributor", demandFn: stepDemand });

  let threw = false;
  try {
    game.submitOrder(5);
  } catch (e) {
    threw = true;
  }
  assert(threw, "submitOrder() before beginTurn() should throw");

  game.beginTurn();
  threw = false;
  try {
    game.beginTurn();
  } catch (e) {
    threw = true;
  }
  assert(threw, "beginTurn() called twice in a row should throw");

  threw = false;
  try {
    game.submitOrder(-1);
  } catch (e) {
    threw = true;
  }
  assert(threw, "submitOrder(-1) should throw");

  threw = false;
  try {
    game.submitOrder(2.5);
  } catch (e) {
    threw = true;
  }
  assert(threw, "submitOrder(2.5) should throw");

  threw = false;
  try {
    game.getFinalReveal();
  } catch (e) {
    threw = true;
  }
  assert(threw, "getFinalReveal() before game over should throw");
}

if (failures.length === 0) {
  console.log("PASS -- all game controller smoke test assertions passed.");
  process.exit(0);
} else {
  console.log(`FAIL -- ${failures.length} assertion(s) failed:`);
  for (const f of failures) console.log(`  ${f}`);
  process.exit(1);
}

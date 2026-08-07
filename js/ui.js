// Display layer -- charts, pipeline visualization, cost meter, end-game
// comparison, pacing, and (this pass) the explanatory copy layer: a
// how-to-play screen, labeled/interpreted in-play numbers, and a
// lesson-first end screen. This file only reads what GameController
// already exposes (the restricted view during play, the full reveal only
// after game-over) and what js/comparison.js computes from the
// already-verified engine offline. It never reaches into engine internals
// directly and never shows the player anything the information
// restriction wouldn't already allow -- that boundary lives in
// js/gameController.js, not here. Nothing in this file changes what the
// simulation computes, only how it's explained.

import { defaultConfig, ECHELON_NAMES } from "./config.js";
import { stepDemand } from "./demand.js";
import { GameController } from "./gameController.js";
import { runComparisons } from "./comparison.js";

// Same categorical slot order used by experiments/figures.py's committed
// PNGs (blue/orange/aqua/yellow for Retailer/Wholesaler/Distributor/Factory),
// kept here for visual consistency between the Python figures and the game.
const ECHELON_COLORS = { Retailer: "#2a78d6", Wholesaler: "#eb6834", Distributor: "#1baf7a", Factory: "#eda100" };
const INVENTORY_COLOR = "#2a78d6";
const BACKLOG_COLOR = "#e34948";
const STEADY_DEMAND = 8;

// Who each echelon's downstream order comes from, in plain language.
const DOWNSTREAM_ACTOR = { Retailer: "your customers", Wholesaler: "the Retailer", Distributor: "the Wholesaler", Factory: "the Distributor" };
const DOWNSTREAM_LABEL = { Retailer: "Customer demand", Wholesaler: "Retailer's order", Distributor: "Wholesaler's order", Factory: "Distributor's order" };
const SUPPLIER_ACTOR = { Retailer: "the Wholesaler", Wholesaler: "the Distributor", Distributor: "the Factory" };

let game = null;
let config = null;
let playerEchelon = null;
let otherPolicy = null;
let playerChart = null;

const setupEl = document.getElementById("setup");
const howToPlayEl = document.getElementById("howToPlay");
const playEl = document.getElementById("play");
const revealEl = document.getElementById("reveal");
const orderInput = document.getElementById("orderInput");

document.getElementById("continueButton").addEventListener("click", () => {
  playerEchelon = document.getElementById("playerEchelon").value;
  otherPolicy = document.getElementById("otherPolicy").value;
  config = defaultConfig();

  document.getElementById("howToPlayBody").innerHTML = buildHowToPlayHTML(playerEchelon, config);

  setupEl.hidden = true;
  howToPlayEl.hidden = false;
});

document.getElementById("startButton").addEventListener("click", () => {
  game = new GameController({ config, playerEchelon, otherPolicy, demandFn: stepDemand });

  howToPlayEl.hidden = true;
  playEl.hidden = false;
  document.getElementById("totalWeeks").textContent = String(config.horizonWeeks);
  document.getElementById("playerEchelonLabel").textContent = playerEchelon;

  initChart();
  renderTurn();
});

document.getElementById("orderForm").addEventListener("submit", (event) => {
  event.preventDefault();
  const qty = Number(orderInput.value);
  if (!Number.isInteger(qty) || qty < 0) {
    alert("Enter a non-negative whole number.");
    return;
  }
  const { gameOver } = game.submitOrder(qty);
  if (gameOver) {
    renderReveal();
  } else {
    renderTurn();
  }
});

// --- How to play -----------------------------------------------------

function buildHowToPlayHTML(echelon, cfg) {
  const holding = cfg.holdingCost.toFixed(2);
  const backlogRate = cfg.backlogCost.toFixed(2);

  const firstBullet =
    echelon === "Retailer"
      ? `Every week, ${DOWNSTREAM_ACTOR[echelon]} place orders.`
      : `Every week, ${DOWNSTREAM_ACTOR[echelon]} places an order with you.`;

  const leadTimeBullet =
    echelon === "Factory"
      ? `You have no supplier limiting you — instead, ordering means starting a production run, which takes about <strong>${cfg.productionDelay} weeks</strong> to complete, and is never limited by raw materials.`
      : `When you order from ${SUPPLIER_ACTOR[echelon]}, it takes about <strong>${cfg.orderDelay + cfg.shipDelay} weeks</strong> to arrive — ${cfg.orderDelay} weeks for your order to reach them, plus ${cfg.shipDelay} more weeks for their shipment to reach you.`;

  return `
    <p>You are the <strong>${echelon}</strong>.</p>
    <ul>
      <li>${firstBullet} If you can't fill it completely from your inventory, the unfilled part becomes <strong>backlog</strong> — units you still owe, which cost you money every week until you ship them.</li>
      <li>${leadTimeBullet}</li>
      <li>Costs, charged every week: <strong>$${holding} per unit in inventory</strong>, <strong>$${backlogRate} per unit in backlog</strong> — backlog costs twice as much, so it's usually better to carry a little extra stock than to run out.</li>
      <li>Your goal: minimize your <strong>total cost over all ${cfg.horizonWeeks} weeks</strong>. There's no reward for precision — just keep both numbers low, week after week.</li>
      <li class="strategy-hint">The natural temptation is to order more whenever you're short. Watch for that — it's how the trouble usually starts.</li>
      <li>You'll only see your own numbers as you play — not what any other echelon is doing. That's realistic: nobody in a real supply chain sees the whole picture either.</li>
    </ul>
  `;
}

// --- Live play ---------------------------------------------------------

function initChart() {
  const ctx = document.getElementById("playerChart").getContext("2d");
  playerChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Inventory",
          data: [],
          borderColor: INVENTORY_COLOR,
          backgroundColor: INVENTORY_COLOR,
          borderWidth: 2,
          pointRadius: 3,
          tension: 0.15,
        },
        {
          label: "Backlog",
          data: [],
          borderColor: BACKLOG_COLOR,
          backgroundColor: "rgba(227, 73, 72, 0.15)",
          borderWidth: 2,
          pointRadius: 3,
          fill: true,
          tension: 0.15,
        },
      ],
    },
    options: {
      animation: { duration: 200 },
      scales: {
        x: { title: { display: true, text: "week" } },
        y: { beginAtZero: true },
      },
      plugins: { legend: { display: true } },
    },
  });
}

function renderTurn() {
  const view = game.beginTurn();
  document.getElementById("weekNumber").textContent = String(view.week);

  renderEventNote(view);
  renderStatusList(view);
  renderCostMeter(view);
  renderPipeline(view);
  updateChart(view);

  orderInput.value = String(view.orderHistory.length > 0 ? view.orderHistory[view.orderHistory.length - 1] : 8);
  orderInput.focus();
  orderInput.select();
}

// Only the Retailer ever legitimately knows true customer demand changed --
// for any other echelon, announcing this would leak information they
// couldn't actually observe.
function renderEventNote(view) {
  const note = document.getElementById("eventNote");
  if (view.echelon === "Retailer" && view.week === 5) {
    note.textContent = "Customer demand just jumped: 4 -> 8 units/week.";
    note.hidden = false;
  } else {
    note.hidden = true;
  }
}

function renderStatusList(view) {
  const statusList = document.getElementById("statusList");
  statusList.innerHTML = "";

  const inventoryCost = view.inventory * config.holdingCost;
  const backlogCost = view.backlog * config.backlogCost;

  const lines = [
    `${DOWNSTREAM_LABEL[view.echelon]} this week: ${view.orderReceivedFromDownstream} units`,
    `Shipment arriving this week: ${view.shipmentArriving} units landing in your inventory`,
    `Inventory: ${view.inventory} units on your shelf — costing $${inventoryCost.toFixed(2)} this week`,
    view.backlog > 0
      ? `Backlog: ${view.backlog} units you still owe — costing $${backlogCost.toFixed(2)} this week`
      : `Backlog: 0 — you're fully caught up`,
    `Total cost this week: $${view.costThisWeek.toFixed(2)} (inventory + backlog)`,
  ];
  for (const text of lines) {
    const li = document.createElement("li");
    li.textContent = text;
    statusList.appendChild(li);
  }
  document.getElementById("orderHistory").textContent =
    view.orderHistory.length > 0 ? view.orderHistory.join(", ") : "(no orders placed yet)";
  document.getElementById("shipmentArrivingNow").textContent = `${view.shipmentArriving} units`;
}

function renderCostMeter(view) {
  const runningTotal = view.cumulativeCostBeforeThisWeek + view.costThisWeek;
  const meter = document.getElementById("costMeter");
  document.getElementById("costMeterValue").textContent = `$${runningTotal.toFixed(2)}`;
  // "Danger" reads on backlog existing right now, or a costly week just
  // hit -- both are the player's own, already-known numbers, not a
  // prediction.
  meter.classList.toggle("danger", view.backlog > 0);
}

function renderPipeline(view) {
  const zoneAEl = document.getElementById("pipelineZoneA");
  const zoneBEl = document.getElementById("pipelineZoneB");
  zoneAEl.innerHTML = "";
  zoneBEl.innerHTML = "";

  let zoneAEntries = [];
  if (view.echelon === "Factory") {
    const note = document.createElement("p");
    note.className = "pipeline-note";
    note.textContent = "Production starts immediately once you order -- there's no supplier decision to wait on.";
    zoneAEl.appendChild(note);
  } else {
    const orderDelay = config.orderDelay;
    const startIdx = Math.max(0, view.orderHistory.length - orderDelay);
    for (let idx = startIdx; idx < view.orderHistory.length; idx++) {
      if (view.orderHistory[idx] > 0) {
        zoneAEntries.push({ week: idx + 1, quantity: view.orderHistory[idx] });
      }
    }
    if (zoneAEntries.length === 0) {
      zoneAEl.appendChild(emptyNote("(nothing awaiting a shipping decision)"));
    } else {
      for (const entry of zoneAEntries) {
        zoneAEl.appendChild(pipelineToken("zone-a", `${entry.quantity} units`, `ordered wk ${entry.week}`));
      }
    }
  }

  const zoneBEntries = view.shipmentsInTransit
    .map((quantity, i) => ({ quantity, arrivesInWeeks: i + 1, arrivalWeek: view.week + i + 1 }))
    .filter((entry) => entry.quantity > 0);
  if (zoneBEntries.length === 0) {
    zoneBEl.appendChild(emptyNote("(nothing confirmed in transit)"));
  } else {
    for (const entry of zoneBEntries) {
      zoneBEl.appendChild(
        pipelineToken("zone-b", `${entry.quantity} units`, `arrives in ${entry.arrivesInWeeks}wk`)
      );
    }
  }

  renderPipelineSummary(view, zoneAEntries, zoneBEntries);
}

// Makes the pipeline explicit in words, split honestly into two zones:
// Zone B has a guaranteed arrival week (already shipped, fixed transit
// time), so a specific week range is accurate. Zone A does NOT -- whether
// and when it ships depends on the supplier's own backlog, which the
// player can't see, so quoting a specific arrival week for it would be a
// false certainty about exactly the thing the player is supposed to be
// uncertain about. That's deliberate, not an oversight.
function renderPipelineSummary(view, zoneAEntries, zoneBEntries) {
  const el = document.getElementById("pipelineSummary");
  const zoneATotal = zoneAEntries.reduce((sum, e) => sum + e.quantity, 0);
  const zoneBTotal = zoneBEntries.reduce((sum, e) => sum + e.quantity, 0);
  const inProductionVerb = view.echelon === "Factory";

  if (zoneATotal === 0 && zoneBTotal === 0) {
    el.textContent = "You haven't placed any orders yet, so nothing is in your pipeline.";
    return;
  }

  const parts = [];

  if (zoneBTotal > 0) {
    const weeks = zoneBEntries.map((e) => e.arrivalWeek);
    const minWk = Math.min(...weeks);
    const maxWk = Math.max(...weeks);
    const weekRange = minWk === maxWk ? `week ${minWk}` : `weeks ${minWk}–${maxWk}`;
    parts.push(
      inProductionVerb
        ? `<strong>${zoneBTotal} units are already in production</strong>, arriving ${weekRange}.`
        : `<strong>${zoneBTotal} units are already on the way</strong>, arriving ${weekRange}.`
    );
  } else if (!inProductionVerb) {
    parts.push("Nothing confirmed in transit yet.");
  }

  if (zoneATotal > 0) {
    parts.push(
      `Plus <strong>${zoneATotal} units you've ordered that your supplier hasn't shipped yet</strong> — no guaranteed arrival date yet. That's the part that's easy to forget when deciding how much more to order.`
    );
  }

  el.innerHTML = parts.join(" ");
}

function emptyNote(text) {
  const p = document.createElement("p");
  p.className = "pipeline-empty";
  p.textContent = text;
  return p;
}

function pipelineToken(zoneClass, mainText, subText) {
  const div = document.createElement("div");
  div.className = `pipeline-token ${zoneClass}`;
  div.innerHTML = `${mainText}<br>${subText}`;
  return div;
}

function updateChart(view) {
  playerChart.data.labels.push(view.week);
  playerChart.data.datasets[0].data.push(view.inventory);
  playerChart.data.datasets[1].data.push(view.backlog);
  playerChart.update();
}

// --- Reveal --------------------------------------------------------------

function renderReveal() {
  playEl.hidden = true;
  revealEl.hidden = false;

  const reveal = game.getFinalReveal();
  const comparisons = runComparisons({ config, playerEchelon, otherPolicy, demandFn: stepDemand });

  renderVerdict(reveal, comparisons);
  renderComparisonPanel(reveal, comparisons);
  renderBullwhipExplanation(reveal);
  renderRevealChart(reveal);
  renderRevealTable(reveal);
}

function renderVerdict(reveal, comparisons) {
  const player = reveal.playerTotalCost;
  const base = comparisons.base_stock.totalCost;
  const aa = comparisons.anchor_and_adjust.totalCost;

  let comparisonSentence;
  if (Math.abs(player - base) < 0.01) {
    comparisonSentence = `You matched the rational (base-stock) benchmark almost exactly ($${base.toFixed(2)}).`;
  } else if (player > base) {
    const ratio = player / base;
    comparisonSentence = `A rational (base-stock) policy would have scored $${base.toFixed(2)} at this position — about ${ratio.toFixed(1)}x better than you.`;
  } else {
    const ratio = base / player;
    comparisonSentence = `You actually beat the rational (base-stock) benchmark ($${base.toFixed(2)}) by about ${ratio.toFixed(1)}x — nice.`;
  }

  document.getElementById("verdict").innerHTML = `
    <p>You scored <strong>$${player.toFixed(2)}</strong>. ${comparisonSentence}</p>
    <p class="muted">For reference, a simulated human-like (anchor-and-adjust) policy scored $${aa.toFixed(2)} here.</p>
  `;
}

function renderComparisonPanel(reveal, comparisons) {
  const entries = [
    { label: `You (${reveal.playerEchelon})`, value: reveal.playerTotalCost, isPlayer: true },
    { label: comparisons.base_stock.label, value: comparisons.base_stock.totalCost },
    { label: comparisons.anchor_and_adjust.label, value: comparisons.anchor_and_adjust.totalCost },
  ];
  const minValue = Math.min(...entries.map((e) => e.value));

  const panel = document.getElementById("comparisonPanel");
  panel.innerHTML = "";
  for (const entry of entries) {
    const card = document.createElement("div");
    card.className = "comparison-card";
    if (entry.isPlayer) card.classList.add("you");
    if (entry.value === minValue) card.classList.add("winner");
    card.innerHTML = `<div class="label">${entry.label}</div><div class="value">$${entry.value.toFixed(2)}</div>`;
    panel.appendChild(card);
  }
}

// Computed entirely from this playthrough's real numbers -- not canned
// text -- so it stays honest even when the "other 3" ran base-stock and
// the swings genuinely are small.
function renderBullwhipExplanation(reveal) {
  const playerOrders = reveal.fullHistory.filter((r) => r.echelon === reveal.playerEchelon).map((r) => r.order_placed);
  const factoryOrders = reveal.fullHistory.filter((r) => r.echelon === "Factory").map((r) => r.order_placed);
  const playerMin = Math.min(...playerOrders);
  const playerMax = Math.max(...playerOrders);
  const factoryMax = Math.max(...factoryOrders);
  const factoryRatio = (factoryMax / STEADY_DEMAND).toFixed(1);

  let swingSentence;
  if (reveal.playerEchelon === "Factory") {
    swingSentence =
      playerMin === playerMax
        ? `But your own orders — you're the Factory, farthest from the customer — stayed rock-steady at ${playerMin} units the whole game.`
        : `But your own orders — you're the Factory, farthest from the customer — swung between ${playerMin} and ${playerMax} units, peaking at about ${factoryRatio}x the steady demand of ${STEADY_DEMAND}/week.`;
  } else {
    const playerSwing =
      playerMin === playerMax
        ? `your own orders stayed rock-steady at ${playerMin} units`
        : `your own orders swung between ${playerMin} and ${playerMax} units`;
    swingSentence = `But ${playerSwing}, and by the Factory — farthest from the customer — orders peaked at ${factoryMax} units, about ${factoryRatio}x the steady demand of ${STEADY_DEMAND}/week.`;
  }

  document.getElementById("bullwhipExplanation").innerHTML = `
    <p><strong>What happened:</strong> Customer demand only ever did one thing this game — it stepped from 4 to ${STEADY_DEMAND} units/week in week 5, then stayed flat. ${swingSentence}</p>
    <p>This growing swing as you move upstream is the <strong>bullwhip effect</strong>. It isn't caused by anyone panicking — it happens because orders take weeks to arrive: you kept ordering to cover a shortage that was already on its way, then got flooded when it all arrived at once. Repeat that at each stage of the chain, and a small demand change turns into a big supply swing by the time it reaches the Factory.</p>
  `;
}

function renderRevealChart(reveal) {
  const byWeekByEchelon = {};
  for (const echelon of ECHELON_NAMES) byWeekByEchelon[echelon] = [];
  for (const row of reveal.fullHistory) {
    byWeekByEchelon[row.echelon].push(row.order_placed);
  }
  const weeks = [...new Set(reveal.fullHistory.map((r) => r.week))].sort((a, b) => a - b);

  const ctx = document.getElementById("revealChart").getContext("2d");
  new Chart(ctx, {
    type: "line",
    data: {
      labels: weeks,
      datasets: ECHELON_NAMES.map((echelon) => ({
        label: echelon,
        data: byWeekByEchelon[echelon],
        borderColor: ECHELON_COLORS[echelon],
        backgroundColor: ECHELON_COLORS[echelon],
        borderWidth: echelon === reveal.playerEchelon ? 3 : 2,
        pointRadius: 0,
        tension: 0.15,
      })),
    },
    options: {
      scales: {
        x: { title: { display: true, text: "week" } },
        y: { title: { display: true, text: "order placed (units/week)" }, beginAtZero: true },
      },
      plugins: { legend: { display: true } },
    },
  });
}

function renderRevealTable(reveal) {
  const byWeek = new Map();
  for (const row of reveal.fullHistory) {
    if (!byWeek.has(row.week)) byWeek.set(row.week, {});
    byWeek.get(row.week)[row.echelon] = row.order_placed;
  }

  const tbody = document.querySelector("#revealTable tbody");
  tbody.innerHTML = "";
  for (const week of [...byWeek.keys()].sort((a, b) => a - b)) {
    const rowData = byWeek.get(week);
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${week}</td>` + ECHELON_NAMES.map((e) => `<td>${rowData[e]}</td>`).join("");
    tbody.appendChild(tr);
  }
}

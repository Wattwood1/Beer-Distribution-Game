// Correctness gate for the JS engine port. Runs the JS engine on the
// identical test case used to generate reference_run.json (step demand,
// all four echelons anchor-and-adjust beta=0.25/theta=0.3/alpha=0.25,
// canonical setup, 52 weeks) and compares every field of every
// week/echelon row against the Python ground truth. Pass condition: zero
// discrepancies. Any mismatch is reported with its exact week, echelon,
// and field -- nothing is summarized away.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

import { defaultConfig } from "../../js/config.js";
import { stepDemand } from "../../js/demand.js";
import { makeAnchorAndAdjustAgents } from "../../js/agents/anchorAdjust.js";
import { BeerGameEngine } from "../../js/engine.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

const reference = JSON.parse(readFileSync(join(__dirname, "reference_run.json"), "utf8"));
const refConfig = reference.config;
const refParams = reference.agent_params;

if (refParams.policy !== "anchor_and_adjust") {
  throw new Error(`reference file's policy is "${refParams.policy}", this script only knows how to replay anchor_and_adjust`);
}

const config = defaultConfig({
  nEchelons: refConfig.n_echelons,
  orderDelay: refConfig.order_delay,
  shipDelay: refConfig.ship_delay,
  productionDelay: refConfig.production_delay,
  initialInventory: refConfig.initial_inventory,
  horizonWeeks: refConfig.horizon_weeks,
  warmupWeeks: refConfig.warmup_weeks,
  holdingCost: refConfig.holding_cost,
  backlogCost: refConfig.backlog_cost,
});

const agents = makeAnchorAndAdjustAgents(config, {
  theta: refParams.theta,
  alpha: refParams.alpha,
  beta: refParams.beta,
  safetyBuffer: refParams.safety_buffer,
});

const engine = new BeerGameEngine(config, agents, stepDemand);
const jsRows = engine.run();

const FIELDS = [
  "inventory",
  "backlog",
  "supply_line",
  "shipment_received",
  "order_received",
  "shipped",
  "order_placed",
  "cost",
  "cumulative_produced",
  "cumulative_delivered_to_customer",
];

const refRows = reference.rows;

const mismatches = [];

if (jsRows.length !== refRows.length) {
  mismatches.push({
    week: null,
    echelon: null,
    field: "row_count",
    expected: refRows.length,
    actual: jsRows.length,
  });
}

const key = (row) => `${row.week}::${row.echelon}`;
const refByKey = new Map(refRows.map((row) => [key(row), row]));
const jsByKey = new Map(jsRows.map((row) => [key(row), row]));

for (const [k, refRow] of refByKey) {
  const jsRow = jsByKey.get(k);
  if (!jsRow) {
    mismatches.push({ week: refRow.week, echelon: refRow.echelon, field: "(missing row)", expected: "present", actual: "absent" });
    continue;
  }
  for (const field of FIELDS) {
    const expected = refRow[field];
    const actual = jsRow[field];
    if (expected !== actual) {
      mismatches.push({ week: refRow.week, echelon: refRow.echelon, field, expected, actual });
    }
  }
}

for (const k of jsByKey.keys()) {
  if (!refByKey.has(k)) {
    const jsRow = jsByKey.get(k);
    mismatches.push({ week: jsRow.week, echelon: jsRow.echelon, field: "(extra row)", expected: "absent", actual: "present" });
  }
}

console.log(`Python reference rows: ${refRows.length}`);
console.log(`JS engine rows:        ${jsRows.length}`);
console.log(`Fields compared per row: ${FIELDS.join(", ")}`);
console.log("");

if (mismatches.length === 0) {
  console.log(`PASS -- 0 mismatches across ${refRows.length} rows x ${FIELDS.length} fields (${refRows.length * FIELDS.length} values compared).`);
  process.exit(0);
} else {
  console.log(`FAIL -- ${mismatches.length} mismatch(es):`);
  for (const m of mismatches) {
    console.log(`  week=${m.week} echelon=${m.echelon} field=${m.field}: expected=${m.expected} actual=${m.actual}`);
  }
  process.exit(1);
}

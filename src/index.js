#!/usr/bin/env node
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const DATA_PATH = join(__dirname, "..", "creators.json");

// ---------------------------------------------------------------------------
// Data helpers
// ---------------------------------------------------------------------------

function loadCreators() {
  const raw = readFileSync(DATA_PATH, "utf-8");
  return JSON.parse(raw);
}

function saveCreators(creators) {
  writeFileSync(DATA_PATH, JSON.stringify(creators, null, 2) + "\n");
}

function daysSince(isoDate) {
  const then = new Date(isoDate + "T00:00:00");
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  return Math.floor((now - then) / 86_400_000);
}

function normalizeHandle(h) {
  h = h.trim();
  return h.startsWith("@") ? h : `@${h}`;
}

function pad(str, width) {
  return String(str).padEnd(width);
}

// ---------------------------------------------------------------------------
// Commands
// ---------------------------------------------------------------------------

function cmdList(args) {
  let creators = loadCreators();
  const minHeat = parseFloat(args["--min-heat"] ?? "0");
  creators = creators.filter((c) => c.heat >= minHeat);

  const sort = args["--sort"] ?? "heat";
  if (sort === "staleness") {
    creators.sort((a, b) => daysSince(b.last_boosted) - daysSince(a.last_boosted));
  } else {
    creators.sort((a, b) => b.heat - a.heat);
  }

  const limit = args["--limit"] ? parseInt(args["--limit"]) : creators.length;
  creators = creators.slice(0, limit);

  if (!creators.length) {
    console.log("No creators match the current filters.");
    return;
  }

  console.log(
    `${pad("Handle", 18)}${pad("Platform", 12)}${pad("Heat", 8)}${pad("Last boosted", 20)}Note`
  );
  console.log("-".repeat(110));
  for (const c of creators) {
    const days = daysSince(c.last_boosted);
    console.log(
      `${pad(c.handle, 18)}${pad(c.platform, 12)}${pad(c.heat.toFixed(2), 8)}${pad(`${c.last_boosted} (${days}d)`, 20)}${c.note}`
    );
  }
}

function cmdSummary() {
  const creators = loadCreators();
  const avg = creators.reduce((s, c) => s + c.heat, 0) / creators.length;
  const hottest = creators.reduce((a, b) => (a.heat > b.heat ? a : b));
  const stalest = creators.reduce((a, b) =>
    daysSince(a.last_boosted) > daysSince(b.last_boosted) ? a : b
  );

  console.log("=== Creator Spark Registry ===");
  console.log(`Average heat: ${avg.toFixed(2)}`);
  console.log(
    `Top lead: ${hottest.handle} (${hottest.heat.toFixed(2)}) — ${hottest.category} on ${hottest.platform}`
  );
  console.log(
    `Needs love: ${stalest.handle} (last boost ${daysSince(stalest.last_boosted)} days ago)`
  );
}

function cmdAdd(args) {
  const creators = loadCreators();
  const handle = normalizeHandle(args._[0]);
  if (creators.some((c) => c.handle.toLowerCase() === handle.toLowerCase())) {
    console.error(`Handle ${handle} already exists.`);
    process.exit(1);
  }

  const today = new Date().toISOString().slice(0, 10);
  creators.push({
    handle,
    platform: args._[1],
    category: args._[2],
    note: args._[3] ?? "",
    heat: parseFloat(args._[4] ?? "0.5"),
    last_seen: today,
    last_boosted: today,
  });
  saveCreators(creators);
  console.log(`Added ${handle}.`);
}

function cmdBoost(args) {
  const creators = loadCreators();
  const handle = normalizeHandle(args._[0]);
  const creator = creators.find(
    (c) => c.handle.toLowerCase() === handle.toLowerCase()
  );
  if (!creator) {
    console.error(`No creator named ${handle} in the registry.`);
    process.exit(1);
  }

  creator.last_boosted = new Date().toISOString().slice(0, 10);
  if (args["--note"]) creator.note = args["--note"];
  saveCreators(creators);
  console.log(`Logged boost for ${creator.handle} (${creator.category}).`);
}

function cmdRemove(args) {
  let creators = loadCreators();
  const handle = normalizeHandle(args._[0]);
  const before = creators.length;
  creators = creators.filter(
    (c) => c.handle.toLowerCase() !== handle.toLowerCase()
  );
  if (creators.length === before) {
    console.error(`No creator named ${handle} in the registry.`);
    process.exit(1);
  }
  saveCreators(creators);
  console.log(`Removed ${handle} from the registry.`);
}

function cmdAgenda(args) {
  const creators = loadCreators();
  const window = parseInt(args["--window"] ?? "7");
  const limit = parseInt(args["--limit"] ?? "5");

  let queued = creators.filter((c) => daysSince(c.last_boosted) > window);
  queued.sort(
    (a, b) => daysSince(b.last_boosted) - daysSince(a.last_boosted) || b.heat - a.heat
  );
  queued = queued.slice(0, limit);

  if (!queued.length) {
    console.log(`All creators were boosted within the last ${window} days.`);
    return;
  }

  console.log(`Boost agenda (older than ${window} days)`);
  console.log(`${pad("Handle", 18)}${pad("Heat", 8)}${pad("Days", 8)}Note`);
  console.log("-".repeat(96));
  for (const c of queued) {
    console.log(
      `${pad(c.handle, 18)}${pad(c.heat.toFixed(2), 8)}${pad(daysSince(c.last_boosted), 8)}${c.note}`
    );
  }
}

// ---------------------------------------------------------------------------
// Arg parsing
// ---------------------------------------------------------------------------

function parseArgs(argv) {
  const command = argv[0];
  const positional = [];
  const flags = {};

  for (let i = 1; i < argv.length; i++) {
    if (argv[i].startsWith("--")) {
      const key = argv[i];
      const next = argv[i + 1];
      if (next && !next.startsWith("--")) {
        flags[key] = next;
        i++;
      } else {
        flags[key] = true;
      }
    } else {
      positional.push(argv[i]);
    }
  }
  return { command, _: positional, ...flags };
}

function showHelp() {
  console.log(`Creator Spark Registry — Micro-CRM for tracking creators

Commands:
  list     List creators (--sort heat|staleness, --min-heat N, --limit N)
  summary  Show quick stats
  add      <handle> <platform> <category> [note] [heat]
  boost    <handle> [--note "text"]
  remove   <handle>
  agenda   Who needs love (--window N, --limit N)
  help     Show this message`);
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

const argv = process.argv.slice(2);
if (!argv.length || argv[0] === "help" || argv[0] === "--help") {
  showHelp();
  process.exit(0);
}

const args = parseArgs(argv);

const commands = {
  list: cmdList,
  summary: cmdSummary,
  add: cmdAdd,
  boost: cmdBoost,
  remove: cmdRemove,
  agenda: cmdAgenda,
};

if (!commands[args.command]) {
  console.error(`Unknown command: ${args.command}`);
  showHelp();
  process.exit(1);
}

commands[args.command](args);

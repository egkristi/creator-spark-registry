#!/usr/bin/env node
/**
 * Creator Spark Registry v2.0 — Micro-CRM with live data enrichment.
 *
 * Data Sources:
 *   GitHub API (public)       — profile, repos, followers, stars
 *   DEV.to API (public)       — articles, reactions, comments
 *   Hacker News Algolia API   — mentions, points, discussions
 *   Mastodon API (public)     — profile, followers, statuses
 *
 * Commands: list, summary, add, boost, enrich, agenda, report, edit, remove, export
 */

import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import process from 'node:process';

const VERSION = '2.0.0';
const USER_AGENT = `CreatorSparkRegistry/${VERSION} github.com/egkristi/creator-spark-registry`;
const __dirname = dirname(fileURLToPath(import.meta.url));
const DATA_PATH = join(__dirname, '..', 'creators.json');

// ── API Fetching ────────────────────────────────────────────────────────────

async function fetchJson(url) {
  try {
    const resp = await fetch(url, {
      headers: { 'User-Agent': USER_AGENT },
      signal: AbortSignal.timeout(10_000),
    });
    if (!resp.ok) return null;
    return await resp.json();
  } catch { return null; }
}

async function enrichGithub(username) {
  username = username.replace(/^@/, '');
  const data = await fetchJson(`https://api.github.com/users/${username}`);
  if (!data?.login) return null;
  const repos = await fetchJson(`https://api.github.com/users/${username}/repos?per_page=5&sort=updated`);
  const totalStars = Array.isArray(repos) ? repos.reduce((s, r) => s + (r.stargazers_count ?? 0), 0) : 0;
  const recentRepos = Array.isArray(repos) ? repos.slice(0, 5).map(r => ({
    name: r.name, stars: r.stargazers_count ?? 0, updated: (r.pushed_at ?? '').slice(0, 10),
  })) : [];
  return {
    source: 'github', name: data.name, bio: data.bio,
    followers: data.followers ?? 0, following: data.following ?? 0,
    public_repos: data.public_repos ?? 0, total_stars: totalStars,
    location: data.location, company: data.company,
    recent_repos: recentRepos, fetched: new Date().toISOString(),
  };
}

async function enrichDevto(username) {
  username = username.replace(/^@/, '');
  const articles = await fetchJson(`https://dev.to/api/articles?username=${username}&per_page=10`);
  if (!Array.isArray(articles)) return null;
  const totalReactions = articles.reduce((s, a) => s + (a.positive_reactions_count ?? 0), 0);
  const totalComments = articles.reduce((s, a) => s + (a.comments_count ?? 0), 0);
  const recent = articles.slice(0, 5).map(a => ({
    title: (a.title ?? '').slice(0, 60),
    reactions: a.positive_reactions_count ?? 0,
    published: (a.published_at ?? '').slice(0, 10),
  }));
  return {
    source: 'devto', articles_count: articles.length,
    total_reactions: totalReactions, total_comments: totalComments,
    recent_articles: recent, fetched: new Date().toISOString(),
  };
}

async function enrichHackernews(query) {
  query = query.replace(/^@/, '');
  const data = await fetchJson(`https://hn.algolia.com/api/v1/search?query=${encodeURIComponent(query)}&tags=story&hitsPerPage=10`);
  if (!data) return null;
  const hits = data.hits ?? [];
  const totalPoints = hits.reduce((s, h) => s + (h.points ?? 0), 0);
  const totalComments = hits.reduce((s, h) => s + (h.num_comments ?? 0), 0);
  const recent = hits.slice(0, 5).map(h => ({
    title: (h.title ?? '').slice(0, 60),
    points: h.points ?? 0,
    date: (h.created_at ?? '').slice(0, 10),
  }));
  return {
    source: 'hackernews', mentions: data.nbHits ?? 0,
    total_points: totalPoints, total_comments: totalComments,
    recent_mentions: recent, fetched: new Date().toISOString(),
  };
}

async function enrichMastodon(username) {
  username = username.replace(/^@/, '');
  let instance = 'mastodon.social';
  if (username.includes('@')) {
    const parts = username.split('@');
    username = parts[0];
    if (parts[1]) instance = parts[1];
  }
  const data = await fetchJson(`https://${instance}/api/v1/accounts/lookup?acct=${username}`);
  if (!data?.id) return null;
  return {
    source: 'mastodon', display_name: data.display_name,
    note: (data.note ?? '').slice(0, 200),
    followers: data.followers_count ?? 0,
    following: data.following_count ?? 0,
    statuses: data.statuses_count ?? 0,
    instance, fetched: new Date().toISOString(),
  };
}

const ENRICHERS = { github: enrichGithub, devto: enrichDevto, hackernews: enrichHackernews, mastodon: enrichMastodon };

// ── Data Helpers ────────────────────────────────────────────────────────────

function loadCreators() {
  if (!existsSync(DATA_PATH)) return [];
  return JSON.parse(readFileSync(DATA_PATH, 'utf-8'));
}

function saveCreators(creators) {
  writeFileSync(DATA_PATH, JSON.stringify(creators, null, 2) + '\n');
}

function daysSince(isoDate) {
  if (!isoDate) return 0;
  const then = new Date(isoDate + 'T00:00:00');
  const now = new Date(); now.setHours(0, 0, 0, 0);
  return Math.max(0, Math.floor((now - then) / 86_400_000));
}

function normalizeHandle(h) {
  h = (h ?? '').trim();
  return h.startsWith('@') ? h : `@${h}`;
}

function pad(s, w) { return String(s).padEnd(w); }

function today() { return new Date().toISOString().slice(0, 10); }

function activityScore(creator) {
  const e = creator.enrichment ?? {};
  if (!Object.keys(e).length) return 0;
  const scores = [];
  if (e.github) {
    const f = Math.min((e.github.followers ?? 0) / 1000, 1);
    const r = Math.min((e.github.public_repos ?? 0) / 50, 1);
    scores.push((f + r) / 2);
  }
  if (e.devto) {
    const rx = Math.min((e.devto.total_reactions ?? 0) / 100, 1);
    const a = Math.min((e.devto.articles_count ?? 0) / 20, 1);
    scores.push((rx + a) / 2);
  }
  if (e.hackernews) {
    const p = Math.min((e.hackernews.total_points ?? 0) / 500, 1);
    const m = Math.min((e.hackernews.mentions ?? 0) / 50, 1);
    scores.push((p + m) / 2);
  }
  if (e.mastodon) {
    const f = Math.min((e.mastodon.followers ?? 0) / 1000, 1);
    const st = Math.min((e.mastodon.statuses ?? 0) / 1000, 1);
    scores.push((f + st) / 2);
  }
  return scores.length ? +(scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(2) : 0;
}

function findCreator(creators, handle) {
  handle = normalizeHandle(handle);
  const c = creators.find(c => c.handle.toLowerCase() === handle.toLowerCase());
  if (!c) { console.error(`No creator named ${handle} in the registry.`); process.exit(1); }
  return c;
}

function printEnrichSummary(source, data) {
  if (source === 'github') {
    console.log(`✓ ${data.name ?? '?'} | ${data.public_repos} repos, ${data.followers} followers, ${data.total_stars} stars`);
  } else if (source === 'devto') {
    console.log(`✓ ${data.articles_count} articles, ${data.total_reactions} reactions, ${data.total_comments} comments`);
  } else if (source === 'hackernews') {
    console.log(`✓ ${data.mentions} mentions, ${data.total_points} total points`);
  } else if (source === 'mastodon') {
    console.log(`✓ ${data.display_name ?? '?'} | ${data.followers} followers, ${data.statuses} statuses`);
  } else {
    console.log('✓ enriched');
  }
}

function printEnrichDetail(source, data) {
  if (source === 'github' && data.recent_repos) {
    for (const r of data.recent_repos.slice(0, 3)) {
      console.log(`    → ${r.name} ★${r.stars} (updated ${r.updated})`);
    }
  } else if (source === 'devto' && data.recent_articles) {
    for (const a of data.recent_articles.slice(0, 3)) {
      console.log(`    → ${a.title} (${a.reactions} reactions, ${a.published})`);
    }
  } else if (source === 'hackernews' && data.recent_mentions) {
    for (const h of data.recent_mentions.slice(0, 3)) {
      console.log(`    → ${h.title} (${h.points} pts, ${h.date})`);
    }
  } else if (source === 'mastodon' && data.note) {
    const clean = data.note.replace(/<[^>]+>/g, '').slice(0, 100);
    if (clean) console.log(`    Bio: ${clean}`);
  }
}

// ── Commands ────────────────────────────────────────────────────────────────

function cmdList(args) {
  let creators = loadCreators();
  if (!creators.length) { console.log('Registry is empty. Add creators with: node src/index.js add'); return; }

  const minHeat = parseFloat(args['--min-heat'] ?? '0');
  creators = creators.filter(c => c.heat >= minHeat);
  if (args['--platform']) creators = creators.filter(c => c.platform.toLowerCase() === args['--platform'].toLowerCase());
  if (args['--tag']) creators = creators.filter(c => (c.tags ?? []).some(t => t.toLowerCase() === args['--tag'].toLowerCase()));

  const sort = args['--sort'] ?? 'heat';
  if (sort === 'staleness') creators.sort((a, b) => daysSince(b.last_boosted) - daysSince(a.last_boosted));
  else if (sort === 'activity') creators.sort((a, b) => activityScore(b) - activityScore(a));
  else creators.sort((a, b) => b.heat - a.heat);

  const limit = args['--limit'] ? parseInt(args['--limit']) : creators.length;
  creators = creators.slice(0, limit);

  if (!creators.length) { console.log('No creators match the current filters.'); return; }

  console.log(`${pad('Handle', 18)}${pad('Platform', 12)}${pad('Heat', 8)}${pad('Act.', 8)}${pad('Last boosted', 20)}Note`);
  console.log('─'.repeat(110));
  for (const c of creators) {
    const days = daysSince(c.last_boosted);
    const act = Object.keys(c.enrichment ?? {}).length ? activityScore(c).toFixed(2) : ' — ';
    const tags = (c.tags ?? []).length ? ` [${c.tags.join(', ')}]` : '';
    console.log(
      `${pad(c.handle, 18)}${pad(c.platform, 12)}${pad(c.heat.toFixed(2), 8)}${pad(act, 8)}${pad(`${c.last_boosted} (${days}d)`, 20)}${(c.note ?? '').slice(0, 40)}${tags}`
    );
  }
  if (args['--json']) console.log(JSON.stringify(creators, null, 2));
}

function cmdSummary(args) {
  const creators = loadCreators();
  if (!creators.length) { console.log('Registry is empty.'); return; }

  const avg = creators.reduce((s, c) => s + c.heat, 0) / creators.length;
  const hottest = creators.reduce((a, b) => a.heat > b.heat ? a : b);
  const stalest = creators.reduce((a, b) => daysSince(a.last_boosted) > daysSince(b.last_boosted) ? a : b);
  const enriched = creators.filter(c => Object.keys(c.enrichment ?? {}).length);
  const platforms = {};
  for (const c of creators) platforms[c.platform] = (platforms[c.platform] ?? 0) + 1;

  console.log('═'.repeat(40));
  console.log('Creator Spark Registry');
  console.log('═'.repeat(40));
  console.log(`  Total creators: ${creators.length}`);
  console.log(`  Average heat: ${avg.toFixed(2)}`);
  console.log(`  Enriched: ${enriched.length}/${creators.length}`);
  console.log(`  Platforms: ${Object.entries(platforms).sort().map(([k, v]) => `${k} (${v})`).join(', ')}`);
  console.log(`\n  Top lead: ${hottest.handle} (${hottest.heat.toFixed(2)}) — ${hottest.category} on ${hottest.platform}`);
  console.log(`  Needs love: ${stalest.handle} (last boost ${daysSince(stalest.last_boosted)} days ago)`);

  if (enriched.length) {
    const bestAct = enriched.reduce((a, b) => activityScore(a) > activityScore(b) ? a : b);
    console.log(`  Most active: ${bestAct.handle} (activity score: ${activityScore(bestAct).toFixed(2)})`);
  }
  if (args['--json']) console.log(JSON.stringify({ total: creators.length, avg_heat: +avg.toFixed(2), enriched: enriched.length, platforms }, null, 2));
}

function cmdAdd(args) {
  const creators = loadCreators();
  const handle = normalizeHandle(args._[0]);
  if (creators.some(c => c.handle.toLowerCase() === handle.toLowerCase())) {
    console.error(`Handle ${handle} already exists.`); process.exit(1);
  }
  const t = today();
  const tags = args['--tags'] ? args['--tags'].split(',').map(s => s.trim()) : [];
  creators.push({
    handle, platform: args._[1], category: args._[2], note: args._[3] ?? '',
    heat: parseFloat(args._[4] ?? '0.5'), last_seen: t, last_boosted: t,
    tags, url: args['--url'] ?? '', enrichment: {},
  });
  saveCreators(creators);
  console.log(`Added ${handle} (${args._[1]}, heat ${parseFloat(args._[4] ?? '0.5').toFixed(2)}).`);
}

function cmdBoost(args) {
  const creators = loadCreators();
  const creator = findCreator(creators, args._[0]);
  creator.last_boosted = today();
  creator.last_seen = today();
  if (args['--note']) creator.note = args['--note'];
  if (args['--heat']) creator.heat = Math.min(1, Math.max(0, parseFloat(args['--heat'])));
  saveCreators(creators);
  console.log(`Logged boost for ${creator.handle} (${creator.category}).`);
}

async function cmdEnrich(args) {
  const creators = loadCreators();
  const targets = args['--all'] ? creators : [findCreator(creators, args._[0])];

  for (const creator of targets) {
    const platformKey = creator.platform.toLowerCase().replace(/\./g, '').replace(/\s/g, '');
    const handleClean = creator.handle.replace(/^@/, '');

    console.log(`\n${creator.handle} (${creator.platform})`);
    let enrichedAny = false;

    const sources = args['--source'] ? [args['--source']]
      : ENRICHERS[platformKey] ? [platformKey]
      : ['hackernews'];

    for (const source of sources) {
      const enricher = ENRICHERS[source];
      if (!enricher) { console.log(`  ${source}: no enricher available`); continue; }

      process.stdout.write(`  Fetching ${source}... `);
      const result = await enricher(handleClean);
      if (result) {
        if (!creator.enrichment) creator.enrichment = {};
        creator.enrichment[source] = result;
        enrichedAny = true;
        printEnrichSummary(source, result);
      } else {
        console.log('no data found');
      }
    }
    if (enrichedAny) {
      creator.last_seen = today();
      console.log(`  Activity score: ${activityScore(creator).toFixed(2)}`);
    }
  }
  saveCreators(creators);
}

function cmdAgenda(args) {
  const creators = loadCreators();
  if (!creators.length) { console.log('Registry is empty.'); return; }

  const window = parseInt(args['--window'] ?? '7');
  const limit = parseInt(args['--limit'] ?? '10');
  let queued = creators.filter(c => daysSince(c.last_boosted) > window);
  queued.sort((a, b) => daysSince(b.last_boosted) - daysSince(a.last_boosted) || b.heat - a.heat);
  queued = queued.slice(0, limit);

  if (!queued.length) { console.log(`All creators were boosted within the last ${window} days. 🎉`); return; }

  console.log(`Boost agenda (older than ${window} days)`);
  console.log(`${pad('Handle', 18)}${pad('Heat', 8)}${pad('Act.', 8)}${pad('Days', 8)}Note`);
  console.log('─'.repeat(96));
  for (const c of queued) {
    const act = Object.keys(c.enrichment ?? {}).length ? activityScore(c).toFixed(2) : ' — ';
    console.log(`${pad(c.handle, 18)}${pad(c.heat.toFixed(2), 8)}${pad(act, 8)}${pad(daysSince(c.last_boosted), 8)}${(c.note ?? '').slice(0, 55)}`);
  }
  if (args['--json']) console.log(JSON.stringify(queued, null, 2));
}

async function cmdReport(args) {
  const creators = loadCreators();
  if (!creators.length) { console.log('Registry is empty.'); return; }

  const t = today();
  console.log('═'.repeat(60));
  console.log(`Creator Spark Report — ${t}`);
  console.log('═'.repeat(60));

  for (const c of creators) {
    const platformKey = c.platform.toLowerCase().replace(/\./g, '').replace(/\s/g, '');
    const handleClean = c.handle.replace(/^@/, '');

    console.log(`\n${'─'.repeat(50)}`);
    console.log(`${c.handle}  (${c.platform}, ${c.category})`);
    console.log(`  Heat: ${c.heat.toFixed(2)} | Staleness: ${daysSince(c.last_boosted)}d | Last boost: ${c.last_boosted}`);
    if ((c.tags ?? []).length) console.log(`  Tags: ${c.tags.join(', ')}`);
    if (c.note) console.log(`  Note: ${c.note}`);

    const sources = args['--source'] ? [args['--source']]
      : ENRICHERS[platformKey] ? [platformKey]
      : ['hackernews'];

    let enrichedAny = false;
    for (const source of sources) {
      const enricher = ENRICHERS[source];
      if (!enricher) continue;
      process.stdout.write(`  Fetching ${source}... `);
      const result = await enricher(handleClean);
      if (result) {
        if (!c.enrichment) c.enrichment = {};
        c.enrichment[source] = result;
        enrichedAny = true;
        printEnrichSummary(source, result);
        printEnrichDetail(source, result);
      } else {
        console.log('no data found');
      }
    }
    if (enrichedAny) {
      c.last_seen = t;
      console.log(`  Activity score: ${activityScore(c).toFixed(2)}`);
    }
  }

  saveCreators(creators);
  console.log(`\n${'═'.repeat(60)}`);
  console.log(`Report complete. ${creators.length} creators checked.`);
  if (args['--json']) console.log(JSON.stringify(creators, null, 2));
}

function cmdEdit(args) {
  const creators = loadCreators();
  const creator = findCreator(creators, args._[0]);
  const changes = [];
  if (args['--note'] != null) { creator.note = args['--note']; changes.push('note'); }
  if (args['--heat'] != null) { creator.heat = Math.min(1, Math.max(0, parseFloat(args['--heat']))); changes.push('heat'); }
  if (args['--category'] != null) { creator.category = args['--category']; changes.push('category'); }
  if (args['--platform'] != null) { creator.platform = args['--platform']; changes.push('platform'); }
  if (args['--tags'] != null) { creator.tags = args['--tags'].split(',').map(s => s.trim()); changes.push('tags'); }
  if (args['--url'] != null) { creator.url = args['--url']; changes.push('url'); }

  if (!changes.length) { console.log('No changes specified.'); return; }
  saveCreators(creators);
  console.log(`Updated ${creator.handle}: ${changes.join(', ')}.`);
}

function cmdRemove(args) {
  let creators = loadCreators();
  const handle = normalizeHandle(args._[0]);
  const before = creators.length;
  creators = creators.filter(c => c.handle.toLowerCase() !== handle.toLowerCase());
  if (creators.length === before) { console.error(`No creator named ${handle} in the registry.`); process.exit(1); }
  saveCreators(creators);
  console.log(`Removed ${handle} from the registry.`);
}

function cmdExport(args) {
  const creators = loadCreators();
  if (!creators.length) { console.log('Registry is empty.'); return; }
  const fmt = args['--format'] ?? 'json';
  if (fmt === 'json') {
    console.log(JSON.stringify(creators, null, 2));
  } else if (fmt === 'csv') {
    console.log('handle,platform,category,note,heat,last_seen,last_boosted,tags,url,activity_score');
    for (const c of creators) {
      const tags = (c.tags ?? []).join('|');
      const csvNote = `"${(c.note ?? '').replace(/"/g, '""')}"`;
      console.log(`${c.handle},${c.platform},${c.category},${csvNote},${c.heat.toFixed(2)},${c.last_seen},${c.last_boosted},${tags},${c.url ?? ''},${activityScore(c).toFixed(2)}`);
    }
  }
}

// ── Arg Parsing ─────────────────────────────────────────────────────────────

function parseArgs(argv) {
  const command = argv[0] && !argv[0].startsWith('-') ? argv[0] : 'list';
  const rest = command === argv[0] ? argv.slice(1) : argv;
  const positional = [];
  const flags = {};

  for (let i = 0; i < rest.length; i += 1) {
    if (rest[i].startsWith('--')) {
      const key = rest[i];
      const next = rest[i + 1];
      if (next && !next.startsWith('--')) { flags[key] = next; i += 1; }
      else { flags[key] = true; }
    } else {
      positional.push(rest[i]);
    }
  }
  return { command, _: positional, ...flags };
}

// ── Main ────────────────────────────────────────────────────────────────────

async function main() {
  const argv = process.argv.slice(2);

  if (argv.includes('--version') || argv.includes('-v')) {
    console.log(`creator-spark-registry ${VERSION}`);
    return;
  }

  if (!argv.length || argv[0] === 'help' || argv[0] === '--help' || argv[0] === '-h') {
    console.log(`Creator Spark Registry ${VERSION} — Micro-CRM with live data enrichment

Usage: node src/index.js [command] [options]

Commands:
  list       List creators (--sort heat|staleness|activity, --min-heat, --limit, --platform, --tag)
  summary    Quick stats overview
  add        <handle> <platform> <category> [note] [heat] [--tags a,b] [--url URL]
  boost      <handle> [--note text] [--heat N]
  enrich     <handle> [--source github|devto|hackernews|mastodon] or --all
  agenda     Who needs engagement (--window N, --limit N)
  report     Full enrichment report across all creators [--source S]
  edit       <handle> [--note|--heat|--category|--platform|--tags|--url]
  remove     <handle>
  export     [--format json|csv]`);
    return;
  }

  const args = parseArgs(argv);
  const syncCommands = { list: cmdList, summary: cmdSummary, add: cmdAdd, boost: cmdBoost, edit: cmdEdit, remove: cmdRemove, export: cmdExport, agenda: cmdAgenda };
  const asyncCommands = { enrich: cmdEnrich, report: cmdReport };

  if (syncCommands[args.command]) {
    syncCommands[args.command](args);
  } else if (asyncCommands[args.command]) {
    await asyncCommands[args.command](args);
  } else {
    console.error(`Unknown command: ${args.command}. Use --help for usage.`);
    process.exitCode = 1;
  }
}

main().catch(err => {
  console.error('Creator Spark Registry failed:', err);
  process.exitCode = 1;
});

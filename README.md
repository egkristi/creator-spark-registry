# Creator Spark Registry

Micro-CRM with live data enrichment for tracking creators across platforms. Fetches real-time stats from GitHub, DEV.to, Hacker News, and Mastodon APIs. Stores handles, heat scores, boost history, tags, and enrichment data in a local JSON file.

## Data Sources

| Source | Data | Auth Required |
|--------|------|:---:|
| GitHub API | Repos, followers, stars, recent activity | No |
| DEV.to API | Articles, reactions, comments | No |
| Hacker News Algolia | Mentions, points, discussions | No |
| Mastodon API | Followers, statuses, profile | No |

Zero external dependencies. Python uses `urllib` (stdlib). Node.js uses native `fetch`.

## Quick Start

### Python (3.10+)

```bash
# List all creators
python3 registry.py list

# Add a GitHub creator and enrich with live data
python3 registry.py add @torvalds GitHub "open source" "Linux creator" 0.95 --tags linux,git
python3 registry.py enrich @torvalds

# Add a DEV.to writer and enrich
python3 registry.py add @ben DEV.to "community" "DEV co-founder" 0.88
python3 registry.py enrich @ben

# Enrich all creators at once
python3 registry.py enrich --all

# Full enrichment report
python3 registry.py report

# Check who needs engagement
python3 registry.py agenda --window 7
```

### Node.js (18+)

```bash
node src/index.js list
node src/index.js enrich @torvalds
node src/index.js enrich --all
node src/index.js report
node src/index.js agenda --window 14
```

## Commands

| Command | Description | Key Flags |
|---------|-------------|-----------|
| `list` | List creators in a table | `--sort heat\|staleness\|activity`, `--limit`, `--platform`, `--tag`, `--json` |
| `summary` | Stats overview (heat, platforms, enrichment) | `--json` |
| `add` | Add a new creator | positional: handle platform category note heat; `--tags`, `--url` |
| `boost` | Log that you amplified a creator today | `--note`, `--heat` |
| `enrich` | Fetch live data from platform APIs | `--all`, `--source github\|devto\|hackernews\|mastodon` |
| `agenda` | Who needs engagement next | `--window N`, `--limit N`, `--json` |
| `report` | Full enrichment report for all creators | `--source`, `--json` |
| `edit` | Update a creator's fields | `--note`, `--heat`, `--category`, `--platform`, `--tags`, `--url` |
| `remove` | Remove a creator | — |
| `export` | Export as JSON or CSV | `--format json\|csv` |
| `import` | Import from JSON or CSV file | positional: filepath |

## Enrichment

The `enrich` command auto-detects which API to use based on the creator's platform:

| Platform | Enricher | Data Retrieved |
|----------|----------|---------------|
| GitHub | GitHub API | Repos, followers, stars, latest activity |
| DEV.to | DEV.to API | Articles, reactions, comments |
| Mastodon | Mastodon API | Followers, statuses, profile |
| Other | Hacker News | Mentions and discussions |

You can override with `--source`:
```bash
# Search Hacker News for any creator
python3 registry.py enrich @torvalds --source hackernews

# Check a GitHub creator's DEV.to presence too
python3 registry.py enrich @ben --source devto
```

## Activity Score

Each enriched creator gets an **activity score** (0–1) calculated from:
- **GitHub**: followers (÷1000) + repos (÷50)
- **DEV.to**: reactions (÷100) + articles (÷20)
- **Hacker News**: points (÷500) + mentions (÷50)
- **Mastodon**: followers (÷1000) + statuses (÷1000)

Multiple sources are averaged. Use `--sort activity` to rank by real engagement.

## Data Model

```json
{
  "handle": "@torvalds",
  "platform": "GitHub",
  "category": "open source",
  "note": "Linux kernel creator.",
  "heat": 0.95,
  "last_seen": "2026-04-20",
  "last_boosted": "2026-04-15",
  "tags": ["linux", "git", "open-source"],
  "url": "https://github.com/torvalds",
  "enrichment": {
    "github": {
      "source": "github",
      "name": "Linus Torvalds",
      "followers": 299482,
      "public_repos": 11,
      "total_stars": 227,
      "recent_repos": [...]
    }
  }
}
```

## Examples

```bash
# Quick status of your registry
python3 registry.py summary

# Filter by platform
python3 registry.py list --platform GitHub
python3 registry.py list --tag open-source

# Edit a creator
python3 registry.py edit @torvalds --heat 0.99 --tags linux,git,kernel

# Export for spreadsheet
python3 registry.py export --format csv > creators.csv

# Import from a file
python3 registry.py import new-creators.json

# JSON output for automation
python3 registry.py list --json
python3 registry.py report --json
```

## Dependencies

- **Python**: Standard library only (`urllib`, `json`, `argparse`, `csv`, `dataclasses`)
- **Node.js**: Built-in modules only (`fetch`, `node:fs`, `node:path`)

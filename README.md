# Creator Spark Registry

Micro-CRM for tracking micro-creators you want to cheer on. Stores handles, heat scores, boost history, and notes in a local JSON file. Available as both a Python and Node.js CLI.

## Quick Start

### Python (3.10+)

```bash
python3 registry.py list                    # List all creators sorted by heat
python3 registry.py summary                 # Quick stats
python3 registry.py add @handle YouTube "category" "note" 0.85
python3 registry.py boost @handle           # Log that you amplified them today
python3 registry.py agenda --window 7       # Who hasn't been boosted in 7+ days
python3 registry.py remove @handle          # Remove a creator
```

### Node.js (18+)

```bash
node src/index.js list                      # List all creators sorted by heat
node src/index.js summary                   # Quick stats
node src/index.js add @handle YouTube "category" "note" 0.85
node src/index.js boost @handle --note "Shared their reel"
node src/index.js agenda --window 14        # Who needs love
node src/index.js remove @handle            # Remove a creator
```

## Commands

| Command   | Description                                  | Key flags                           |
|-----------|----------------------------------------------|-------------------------------------|
| `list`    | List creators in a table                     | `--sort heat\|staleness`, `--limit` |
| `summary` | Average heat, top lead, stalest creator      | —                                   |
| `add`     | Add a new creator                            | positional: handle platform cat note heat |
| `boost`   | Mark a creator as boosted today              | `--note`                            |
| `agenda`  | Creators not boosted within N days           | `--window N`, `--limit N`           |
| `remove`  | Remove a creator from the registry           | —                                   |

## Data

All data lives in `creators.json` — a flat JSON array. Each entry:

```json
{
  "handle": "@fjordsketch",
  "platform": "Instagram",
  "category": "watercolor timelapses",
  "note": "Uploads 60-second coastal watercolor loops.",
  "heat": 0.87,
  "last_seen": "2026-02-12",
  "last_boosted": "2026-02-04"
}
```

- **heat** (0–1): How promising/interesting the creator is
- **last_boosted**: When you last amplified their content
- **last_seen**: When you last encountered their work

## Dependencies

- **Python**: Standard library only (no pip install needed)
- **Node.js**: No npm dependencies (uses built-in `node:fs`, `node:path`)

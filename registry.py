"""Creator Spark Registry v2.0 — Micro-CRM with live data enrichment for tracking creators.

Data Sources:
  GitHub API (public)       — profile, repos, followers, stars, activity
  DEV.to API (public)       — articles, reactions, comments
  Hacker News Algolia API   — mentions, points, discussions
  Mastodon API (public)     — profile, followers, statuses

Commands:
  list       List creators with optional filtering and sorting
  summary    Quick stats overview
  add        Add a new creator
  boost      Log that you amplified a creator
  enrich     Fetch live data from platform APIs
  agenda     See who needs engagement next
  report     Full enrichment report across all creators
  edit       Update a creator's fields
  remove     Remove a creator
  export     Export creators as JSON or CSV
  import     Import creators from JSON or CSV
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import Sequence
from urllib.error import URLError
from urllib.request import Request, urlopen

# ── Version ──────────────────────────────────────────────────────────────────

VERSION = "2.0.0"
USER_AGENT = f"CreatorSparkRegistry/{VERSION} github.com/egkristi/creator-spark-registry"
DATA_PATH = Path(__file__).with_name("creators.json")

# ── Platform Definitions ─────────────────────────────────────────────────────

PLATFORMS = {
    "github": {"name": "GitHub", "api": "api.github.com", "prefix": ""},
    "devto": {"name": "DEV.to", "api": "dev.to/api", "prefix": ""},
    "hackernews": {"name": "Hacker News", "api": "hn.algolia.com", "prefix": ""},
    "mastodon": {"name": "Mastodon", "api": "mastodon.social/api", "prefix": "@"},
    "youtube": {"name": "YouTube", "api": None, "prefix": "@"},
    "instagram": {"name": "Instagram", "api": None, "prefix": "@"},
    "x": {"name": "X", "api": None, "prefix": "@"},
    "twitch": {"name": "Twitch", "api": None, "prefix": ""},
    "tiktok": {"name": "TikTok", "api": None, "prefix": "@"},
    "linkedin": {"name": "LinkedIn", "api": None, "prefix": ""},
    "bluesky": {"name": "Bluesky", "api": None, "prefix": "@"},
}


# ── API Helpers ──────────────────────────────────────────────────────────────


def _fetch_json(url: str, timeout: int = 10) -> dict | list | None:
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except (URLError, OSError, json.JSONDecodeError, ValueError):
        return None


def enrich_github(username: str) -> dict | None:
    username = username.lstrip("@")
    data = _fetch_json(f"https://api.github.com/users/{username}")
    if not data or "login" not in data:
        return None
    repos = _fetch_json(
        f"https://api.github.com/users/{username}/repos?per_page=5&sort=updated"
    )
    total_stars = 0
    recent_repos = []
    if repos and isinstance(repos, list):
        total_stars = sum(r.get("stargazers_count", 0) for r in repos)
        recent_repos = [
            {"name": r["name"], "stars": r.get("stargazers_count", 0),
             "updated": r.get("pushed_at", "")[:10]}
            for r in repos[:5]
        ]
    return {
        "source": "github",
        "name": data.get("name"),
        "bio": data.get("bio"),
        "followers": data.get("followers", 0),
        "following": data.get("following", 0),
        "public_repos": data.get("public_repos", 0),
        "total_stars": total_stars,
        "location": data.get("location"),
        "company": data.get("company"),
        "recent_repos": recent_repos,
        "fetched": datetime.now().isoformat(),
    }


def enrich_devto(username: str) -> dict | None:
    username = username.lstrip("@")
    articles = _fetch_json(
        f"https://dev.to/api/articles?username={username}&per_page=10"
    )
    if not articles or not isinstance(articles, list):
        return None
    total_reactions = sum(a.get("positive_reactions_count", 0) for a in articles)
    total_comments = sum(a.get("comments_count", 0) for a in articles)
    recent = [
        {"title": a["title"][:60], "reactions": a.get("positive_reactions_count", 0),
         "published": a.get("published_at", "")[:10]}
        for a in articles[:5]
    ]
    return {
        "source": "devto",
        "articles_count": len(articles),
        "total_reactions": total_reactions,
        "total_comments": total_comments,
        "recent_articles": recent,
        "fetched": datetime.now().isoformat(),
    }


def enrich_hackernews(query: str) -> dict | None:
    query = query.lstrip("@")
    data = _fetch_json(
        f"https://hn.algolia.com/api/v1/search?query={query}&tags=story&hitsPerPage=10"
    )
    if not data:
        return None
    hits = data.get("hits", [])
    total_points = sum(h.get("points", 0) for h in hits)
    total_comments = sum(h.get("num_comments", 0) for h in hits)
    recent = [
        {"title": h["title"][:60], "points": h.get("points", 0),
         "date": h.get("created_at", "")[:10]}
        for h in hits[:5]
    ]
    return {
        "source": "hackernews",
        "mentions": data.get("nbHits", 0),
        "total_points": total_points,
        "total_comments": total_comments,
        "recent_mentions": recent,
        "fetched": datetime.now().isoformat(),
    }


def enrich_mastodon(username: str, instance: str = "mastodon.social") -> dict | None:
    username = username.lstrip("@")
    if "@" in username:
        parts = username.split("@")
        username = parts[0]
        instance = parts[1] if len(parts) > 1 else instance
    data = _fetch_json(
        f"https://{instance}/api/v1/accounts/lookup?acct={username}"
    )
    if not data or "id" not in data:
        return None
    return {
        "source": "mastodon",
        "display_name": data.get("display_name"),
        "note": data.get("note", "")[:200],
        "followers": data.get("followers_count", 0),
        "following": data.get("following_count", 0),
        "statuses": data.get("statuses_count", 0),
        "instance": instance,
        "fetched": datetime.now().isoformat(),
    }


ENRICHERS = {
    "github": enrich_github,
    "devto": enrich_devto,
    "hackernews": enrich_hackernews,
    "mastodon": enrich_mastodon,
}


# ── Data Model ───────────────────────────────────────────────────────────────


@dataclass
class Creator:
    handle: str
    platform: str
    category: str
    note: str
    heat: float
    last_seen: date
    last_boosted: date
    tags: list[str] = field(default_factory=list)
    url: str = ""
    enrichment: dict = field(default_factory=dict)

    @property
    def staleness_days(self) -> int:
        return (date.today() - self.last_boosted).days

    @property
    def activity_score(self) -> float:
        """0–1 score derived from enrichment data."""
        if not self.enrichment:
            return 0.0
        scores = []
        e = self.enrichment
        if "github" in e:
            g = e["github"]
            followers = min(g.get("followers", 0) / 1000, 1.0)
            repos = min(g.get("public_repos", 0) / 50, 1.0)
            scores.append((followers + repos) / 2)
        if "devto" in e:
            d = e["devto"]
            reactions = min(d.get("total_reactions", 0) / 100, 1.0)
            articles = min(d.get("articles_count", 0) / 20, 1.0)
            scores.append((reactions + articles) / 2)
        if "hackernews" in e:
            h = e["hackernews"]
            points = min(h.get("total_points", 0) / 500, 1.0)
            mentions = min(h.get("mentions", 0) / 50, 1.0)
            scores.append((points + mentions) / 2)
        if "mastodon" in e:
            m = e["mastodon"]
            followers = min(m.get("followers", 0) / 1000, 1.0)
            statuses = min(m.get("statuses", 0) / 1000, 1.0)
            scores.append((followers + statuses) / 2)
        return round(mean(scores), 2) if scores else 0.0

    def to_payload(self) -> dict:
        return {
            "handle": self.handle,
            "platform": self.platform,
            "category": self.category,
            "note": self.note,
            "heat": round(self.heat, 2),
            "last_seen": self.last_seen.isoformat(),
            "last_boosted": self.last_boosted.isoformat(),
            "tags": self.tags,
            "url": self.url,
            "enrichment": self.enrichment,
        }


# ── Data I/O ─────────────────────────────────────────────────────────────────


def format_row(columns: Sequence[str], widths: Sequence[int]) -> str:
    return "  ".join(f"{v:<{w}}" for v, w in zip(columns, widths))


def load_creators() -> list[Creator]:
    if not DATA_PATH.exists():
        return []
    raw = json.loads(DATA_PATH.read_text())
    creators = []
    for entry in raw:
        creators.append(
            Creator(
                handle=entry["handle"],
                platform=entry["platform"],
                category=entry.get("category", ""),
                note=entry.get("note", ""),
                heat=float(entry.get("heat", 0)),
                last_seen=_coerce_date(entry.get("last_seen")),
                last_boosted=_coerce_date(entry.get("last_boosted")),
                tags=entry.get("tags", []),
                url=entry.get("url", ""),
                enrichment=entry.get("enrichment", {}),
            )
        )
    return creators


def save_creators(creators: Sequence[Creator]) -> None:
    payload = [creator.to_payload() for creator in creators]
    DATA_PATH.write_text(json.dumps(payload, indent=2))


def _coerce_date(value: str | None) -> date:
    if not value:
        return date.today()
    return datetime.fromisoformat(value).date()


def _normalize_handle(handle: str) -> str:
    handle = handle.strip()
    if not handle.startswith("@"):
        handle = f"@{handle}"
    return handle


def _find_creator(creators: list[Creator], handle: str) -> Creator:
    handle = _normalize_handle(handle)
    for c in creators:
        if c.handle.lower() == handle.lower():
            return c
    raise SystemExit(f"No creator named {handle} in the registry.")


# ── Commands ─────────────────────────────────────────────────────────────────


def cmd_list(args: argparse.Namespace) -> None:
    creators = load_creators()
    if not creators:
        print("Registry is empty. Add creators with: registry.py add")
        return

    filtered = [c for c in creators if c.heat >= args.min_heat]
    if args.platform:
        filtered = [c for c in filtered if c.platform.lower() == args.platform.lower()]
    if args.tag:
        filtered = [c for c in filtered if args.tag.lower() in [t.lower() for t in c.tags]]

    if args.sort == "heat":
        filtered.sort(key=lambda c: c.heat, reverse=True)
    elif args.sort == "activity":
        filtered.sort(key=lambda c: c.activity_score, reverse=True)
    else:
        filtered.sort(key=lambda c: c.staleness_days, reverse=True)

    if args.limit:
        filtered = filtered[: args.limit]

    if not filtered:
        print("No creators match the current filters.")
        return

    widths = (18, 12, 6, 6, 18, 44)
    header = ("Handle", "Platform", "Heat", "Act.", "Last boosted", "Note")
    print(format_row(header, widths))
    print("─" * 110)

    for c in filtered:
        act = f"{c.activity_score:.2f}" if c.enrichment else "  — "
        tags_str = f" [{', '.join(c.tags)}]" if c.tags else ""
        row = (
            c.handle,
            c.platform,
            f"{c.heat:.2f}",
            act,
            f"{c.last_boosted.isoformat()} ({c.staleness_days}d)",
            (c.note[:40] + tags_str)[:44],
        )
        print(format_row(row, widths))

    if args.json:
        print(json.dumps([c.to_payload() for c in filtered], indent=2))


def cmd_summary(args: argparse.Namespace) -> None:
    creators = load_creators()
    if not creators:
        print("Registry is empty.")
        return

    avg_heat = mean(c.heat for c in creators)
    hottest = max(creators, key=lambda c: c.heat)
    stalest = max(creators, key=lambda c: c.staleness_days)

    platforms: dict[str, int] = {}
    for c in creators:
        platforms[c.platform] = platforms.get(c.platform, 0) + 1

    enriched = [c for c in creators if c.enrichment]

    print("═" * 40)
    print("Creator Spark Registry")
    print("═" * 40)
    print(f"  Total creators: {len(creators)}")
    print(f"  Average heat: {avg_heat:.2f}")
    print(f"  Enriched: {len(enriched)}/{len(creators)}")
    print(f"  Platforms: {', '.join(f'{k} ({v})' for k, v in sorted(platforms.items()))}")
    print(f"\n  Top lead: {hottest.handle} ({hottest.heat:.2f}) — {hottest.category} on {hottest.platform}")
    print(f"  Needs love: {stalest.handle} (last boost {stalest.staleness_days} days ago)")

    if enriched:
        best_activity = max(enriched, key=lambda c: c.activity_score)
        print(f"  Most active: {best_activity.handle} (activity score: {best_activity.activity_score:.2f})")

    if args.json:
        print(json.dumps({
            "total": len(creators), "avg_heat": round(avg_heat, 2),
            "enriched": len(enriched), "platforms": platforms,
            "top_lead": hottest.handle, "needs_love": stalest.handle,
        }, indent=2))


def cmd_add(args: argparse.Namespace) -> None:
    creators = load_creators()
    handle = _normalize_handle(args.handle)
    if any(c.handle.lower() == handle.lower() for c in creators):
        raise SystemExit(f"Handle {handle} already exists.")

    today = date.today()
    tags = [t.strip() for t in args.tags.split(",")] if args.tags else []
    creator = Creator(
        handle=handle,
        platform=args.platform,
        category=args.category,
        note=args.note,
        heat=float(args.heat),
        last_seen=_coerce_date(args.last_seen),
        last_boosted=_coerce_date(args.last_boosted) if args.last_boosted else today,
        tags=tags,
        url=args.url or "",
    )
    creators.append(creator)
    save_creators(creators)
    print(f"Added {handle} ({creator.platform}, heat {creator.heat:.2f}).")


def cmd_boost(args: argparse.Namespace) -> None:
    creators = load_creators()
    creator = _find_creator(creators, args.handle)
    creator.last_boosted = date.today()
    creator.last_seen = date.today()
    if args.note:
        creator.note = args.note
    if args.heat:
        creator.heat = min(1.0, max(0.0, args.heat))
    save_creators(creators)
    print(f"Logged boost for {creator.handle} ({creator.category}).")


def cmd_enrich(args: argparse.Namespace) -> None:
    creators = load_creators()
    targets = creators if args.all else [_find_creator(creators, args.handle)]

    for creator in targets:
        platform_key = creator.platform.lower().replace(".", "").replace(" ", "")
        handle_clean = creator.handle.lstrip("@")

        print(f"\n{creator.handle} ({creator.platform})")
        enriched_any = False

        if args.source:
            sources = [args.source]
        elif platform_key in ENRICHERS:
            sources = [platform_key]
        else:
            sources = ["hackernews"]

        for source in sources:
            enricher = ENRICHERS.get(source)
            if not enricher:
                print(f"  {source}: no enricher available")
                continue

            print(f"  Fetching {source}...", end=" ", flush=True)
            result = enricher(handle_clean)
            if result:
                creator.enrichment[source] = result
                enriched_any = True
                _print_enrichment_summary(source, result)
            else:
                print("no data found")

        if enriched_any:
            creator.last_seen = date.today()
            print(f"  Activity score: {creator.activity_score:.2f}")

    save_creators(creators)


def _print_enrichment_summary(source: str, data: dict) -> None:
    if source == "github":
        print(f"✓ {data.get('name', '?')} | {data['public_repos']} repos, "
              f"{data['followers']} followers, {data['total_stars']} stars")
    elif source == "devto":
        print(f"✓ {data['articles_count']} articles, "
              f"{data['total_reactions']} reactions, {data['total_comments']} comments")
    elif source == "hackernews":
        print(f"✓ {data['mentions']} mentions, "
              f"{data['total_points']} total points")
    elif source == "mastodon":
        print(f"✓ {data.get('display_name', '?')} | "
              f"{data['followers']} followers, {data['statuses']} statuses")
    else:
        print(f"✓ enriched")


def cmd_agenda(args: argparse.Namespace) -> None:
    creators = load_creators()
    if not creators:
        print("Registry is empty.")
        return

    cutoff = date.today() - timedelta(days=args.window)
    queued = [c for c in creators if c.last_boosted <= cutoff]
    queued.sort(key=lambda c: (c.staleness_days, c.heat), reverse=True)

    if not queued:
        print(f"All creators were boosted within the last {args.window} days. 🎉")
        return

    widths = (18, 6, 6, 6, 55)
    header = ("Handle", "Heat", "Act.", "Days", "Note")
    print(f"Boost agenda (older than {args.window} days)")
    print(format_row(header, widths))
    print("─" * 96)

    for c in queued[: args.limit]:
        act = f"{c.activity_score:.2f}" if c.enrichment else "  — "
        row = (
            c.handle,
            f"{c.heat:.2f}",
            act,
            str(c.staleness_days),
            c.note[:55],
        )
        print(format_row(row, widths))

    if args.json:
        print(json.dumps([c.to_payload() for c in queued[:args.limit]], indent=2))


def cmd_report(args: argparse.Namespace) -> None:
    creators = load_creators()
    if not creators:
        print("Registry is empty.")
        return

    today = date.today()
    print("═" * 60)
    print(f"Creator Spark Report — {today.isoformat()}")
    print("═" * 60)

    for c in creators:
        platform_key = c.platform.lower().replace(".", "").replace(" ", "")
        handle_clean = c.handle.lstrip("@")

        print(f"\n{'─' * 50}")
        print(f"{c.handle}  ({c.platform}, {c.category})")
        print(f"  Heat: {c.heat:.2f} | Staleness: {c.staleness_days}d | Last boost: {c.last_boosted}")
        if c.tags:
            print(f"  Tags: {', '.join(c.tags)}")
        if c.note:
            print(f"  Note: {c.note}")

        enriched_any = False
        if args.source:
            sources = [args.source]
        elif platform_key in ENRICHERS:
            sources = [platform_key]
        else:
            sources = ["hackernews"]

        for source in sources:
            enricher = ENRICHERS.get(source)
            if not enricher:
                continue
            print(f"  Fetching {source}...", end=" ", flush=True)
            result = enricher(handle_clean)
            if result:
                c.enrichment[source] = result
                enriched_any = True
                _print_enrichment_summary(source, result)
                _print_enrichment_detail(source, result)
            else:
                print("no data found")

        if enriched_any:
            c.last_seen = today
            print(f"  Activity score: {c.activity_score:.2f}")

    save_creators(creators)
    print(f"\n{'═' * 60}")
    print(f"Report complete. {len(creators)} creators checked.")

    if args.json:
        print(json.dumps([c.to_payload() for c in creators], indent=2))


def _print_enrichment_detail(source: str, data: dict) -> None:
    if source == "github" and data.get("recent_repos"):
        for r in data["recent_repos"][:3]:
            print(f"    → {r['name']} ★{r['stars']} (updated {r['updated']})")
    elif source == "devto" and data.get("recent_articles"):
        for a in data["recent_articles"][:3]:
            print(f"    → {a['title']} ({a['reactions']} reactions, {a['published']})")
    elif source == "hackernews" and data.get("recent_mentions"):
        for h in data["recent_mentions"][:3]:
            print(f"    → {h['title']} ({h['points']} pts, {h['date']})")
    elif source == "mastodon":
        if data.get("note"):
            import re
            clean = re.sub(r"<[^>]+>", "", data["note"])[:100]
            if clean:
                print(f"    Bio: {clean}")


def cmd_edit(args: argparse.Namespace) -> None:
    creators = load_creators()
    creator = _find_creator(creators, args.handle)

    changes = []
    if args.note is not None:
        creator.note = args.note
        changes.append("note")
    if args.heat is not None:
        creator.heat = min(1.0, max(0.0, args.heat))
        changes.append("heat")
    if args.category is not None:
        creator.category = args.category
        changes.append("category")
    if args.platform is not None:
        creator.platform = args.platform
        changes.append("platform")
    if args.tags is not None:
        creator.tags = [t.strip() for t in args.tags.split(",")]
        changes.append("tags")
    if args.url is not None:
        creator.url = args.url
        changes.append("url")

    if not changes:
        print("No changes specified. Use --note, --heat, --category, --platform, --tags, or --url.")
        return

    save_creators(creators)
    print(f"Updated {creator.handle}: {', '.join(changes)}.")


def cmd_remove(args: argparse.Namespace) -> None:
    creators = load_creators()
    handle = _normalize_handle(args.handle)
    before = len(creators)
    creators = [c for c in creators if c.handle.lower() != handle.lower()]
    if len(creators) == before:
        raise SystemExit(f"No creator named {handle} in the registry.")
    save_creators(creators)
    print(f"Removed {handle} from the registry.")


def cmd_export(args: argparse.Namespace) -> None:
    creators = load_creators()
    if not creators:
        print("Registry is empty.")
        return

    if args.format == "json":
        print(json.dumps([c.to_payload() for c in creators], indent=2))
    elif args.format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["handle", "platform", "category", "note", "heat",
                         "last_seen", "last_boosted", "tags", "url", "activity_score"])
        for c in creators:
            writer.writerow([
                c.handle, c.platform, c.category, c.note, f"{c.heat:.2f}",
                c.last_seen.isoformat(), c.last_boosted.isoformat(),
                "|".join(c.tags), c.url, f"{c.activity_score:.2f}",
            ])
        print(buf.getvalue())


def cmd_import(args: argparse.Namespace) -> None:
    path = Path(args.file)
    if not path.exists():
        raise SystemExit(f"File not found: {path}")

    creators = load_creators()
    existing = {c.handle.lower() for c in creators}
    added = 0

    if path.suffix == ".json":
        raw = json.loads(path.read_text())
        for entry in raw:
            handle = _normalize_handle(entry.get("handle", ""))
            if handle.lower() in existing:
                continue
            creators.append(Creator(
                handle=handle,
                platform=entry.get("platform", "unknown"),
                category=entry.get("category", ""),
                note=entry.get("note", ""),
                heat=float(entry.get("heat", 0.5)),
                last_seen=_coerce_date(entry.get("last_seen")),
                last_boosted=_coerce_date(entry.get("last_boosted")),
                tags=entry.get("tags", []),
                url=entry.get("url", ""),
            ))
            existing.add(handle.lower())
            added += 1
    elif path.suffix == ".csv":
        reader = csv.DictReader(path.read_text().splitlines())
        for row in reader:
            handle = _normalize_handle(row.get("handle", ""))
            if handle.lower() in existing:
                continue
            tags = row.get("tags", "").split("|") if row.get("tags") else []
            creators.append(Creator(
                handle=handle,
                platform=row.get("platform", "unknown"),
                category=row.get("category", ""),
                note=row.get("note", ""),
                heat=float(row.get("heat", 0.5)),
                last_seen=_coerce_date(row.get("last_seen")),
                last_boosted=_coerce_date(row.get("last_boosted")),
                tags=tags,
                url=row.get("url", ""),
            ))
            existing.add(handle.lower())
            added += 1
    else:
        raise SystemExit("Unsupported format. Use .json or .csv.")

    save_creators(creators)
    print(f"Imported {added} new creator(s). Total: {len(creators)}.")


# ── CLI ──────────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Creator Spark Registry — Micro-CRM with live data enrichment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    sub = parser.add_subparsers(dest="command")

    # list
    p = sub.add_parser("list", help="List creators")
    p.add_argument("--limit", type=int, default=None)
    p.add_argument("--sort", choices=["heat", "staleness", "activity"], default="heat")
    p.add_argument("--min-heat", type=float, default=0.0)
    p.add_argument("--platform", default=None)
    p.add_argument("--tag", default=None)
    p.add_argument("--json", action="store_true")

    # summary
    p = sub.add_parser("summary", help="Quick stats")
    p.add_argument("--json", action="store_true")

    # add
    p = sub.add_parser("add", help="Add a creator")
    p.add_argument("handle")
    p.add_argument("platform")
    p.add_argument("category")
    p.add_argument("note")
    p.add_argument("heat", type=float)
    p.add_argument("--last-seen", default=date.today().isoformat())
    p.add_argument("--last-boosted", default=None)
    p.add_argument("--tags", default="")
    p.add_argument("--url", default="")

    # boost
    p = sub.add_parser("boost", help="Log a boost for a creator")
    p.add_argument("handle")
    p.add_argument("--note", default=None)
    p.add_argument("--heat", type=float, default=None)

    # enrich
    p = sub.add_parser("enrich", help="Fetch live data from platform APIs")
    p.add_argument("handle", nargs="?", default=None)
    p.add_argument("--all", action="store_true", help="Enrich all creators")
    p.add_argument("--source", choices=list(ENRICHERS.keys()), default=None)

    # agenda
    p = sub.add_parser("agenda", help="Who needs engagement next")
    p.add_argument("--window", type=int, default=7)
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--json", action="store_true")

    # report
    p = sub.add_parser("report", help="Full enrichment report")
    p.add_argument("--source", choices=list(ENRICHERS.keys()), default=None)
    p.add_argument("--json", action="store_true")

    # edit
    p = sub.add_parser("edit", help="Update a creator's fields")
    p.add_argument("handle")
    p.add_argument("--note", default=None)
    p.add_argument("--heat", type=float, default=None)
    p.add_argument("--category", default=None)
    p.add_argument("--platform", default=None)
    p.add_argument("--tags", default=None)
    p.add_argument("--url", default=None)

    # remove
    p = sub.add_parser("remove", help="Remove a creator")
    p.add_argument("handle")

    # export
    p = sub.add_parser("export", help="Export as JSON or CSV")
    p.add_argument("--format", choices=["json", "csv"], default="json")

    # import
    p = sub.add_parser("import", help="Import from JSON or CSV file")
    p.add_argument("file")

    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        args.command = "list"
        args.limit = None
        args.sort = "heat"
        args.min_heat = 0.0
        args.platform = None
        args.tag = None
        args.json = False

    cmds = {
        "list": cmd_list,
        "summary": cmd_summary,
        "add": cmd_add,
        "boost": cmd_boost,
        "enrich": cmd_enrich,
        "agenda": cmd_agenda,
        "report": cmd_report,
        "edit": cmd_edit,
        "remove": cmd_remove,
        "export": cmd_export,
        "import": cmd_import,
    }

    if args.command == "enrich" and not args.handle and not args.all:
        parser.error("Specify a handle or use --all to enrich all creators.")

    try:
        cmds[args.command](args)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(0)


if __name__ == "__main__":
    main()

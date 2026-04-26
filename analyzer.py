"""Creator Spark Registry
Micro-CRM for tracking which creators to cheer on.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import mean
from typing import List, Sequence

DATA_PATH = Path(__file__).with_name("creators.json")
DEFAULT_DATA = [
    {
        "handle": "@fjordsketch",
        "platform": "Instagram",
        "category": "watercolor timelapses",
        "note": "Uploads 60-second coastal watercolor loops.",
        "heat": 0.87,
        "last_seen": "2026-02-12",
        "last_boosted": "2026-02-04",
    },
    {
        "handle": "@auroraaudio",
        "platform": "YouTube",
        "category": "field recordings",
        "note": "Ambient expeditions with crisp thumbnails.",
        "heat": 0.92,
        "last_seen": "2026-02-11",
        "last_boosted": "2026-01-29",
    },
    {
        "handle": "@northernknots",
        "platform": "X",
        "category": "macro weaving",
        "note": "Threading reels pair textile close-ups w/ founder tips.",
        "heat": 0.74,
        "last_seen": "2026-02-08",
        "last_boosted": "2026-02-01",
    },
]


def format_row(columns: Sequence[str], widths: Sequence[int]) -> str:
    padded = []
    for value, width, align in zip(columns, widths, ("<", "<", ">", ">", "<")):
        padded.append(f"{value:{align}{width}}")
    return "  ".join(padded)


@dataclass
class Creator:
    handle: str
    platform: str
    category: str
    note: str
    heat: float
    last_seen: date
    last_boosted: date

    @property
    def staleness_days(self) -> int:
        return (date.today() - self.last_boosted).days

    def to_payload(self) -> dict:
        return {
            "handle": self.handle,
            "platform": self.platform,
            "category": self.category,
            "note": self.note,
            "heat": round(self.heat, 2),
            "last_seen": self.last_seen.isoformat(),
            "last_boosted": self.last_boosted.isoformat(),
        }


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _ensure_dataset() -> None:
    if DATA_PATH.exists():
        return
    DATA_PATH.write_text(json.dumps(DEFAULT_DATA, indent=2))


def load_creators() -> List[Creator]:
    _ensure_dataset()
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


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------

def cmd_list(args: argparse.Namespace) -> None:
    creators = load_creators()
    filtered = [c for c in creators if c.heat >= args.min_heat]

    if args.sort == "heat":
        filtered.sort(key=lambda c: c.heat, reverse=True)
    else:
        filtered.sort(key=lambda c: c.staleness_days, reverse=True)

    if args.limit:
        filtered = filtered[: args.limit]

    if not filtered:
        print("No creators match the current filters.")
        return

    widths = (16, 10, 6, 18, 50)
    header = ("Handle", "Platform", "Heat", "Last boosted", "Note")
    print(format_row(header, widths))
    print("-" * 120)

    for creator in filtered:
        row = (
            creator.handle,
            creator.platform,
            f"{creator.heat:.2f}",
            f"{creator.last_boosted.isoformat()} ({creator.staleness_days}d)",
            creator.note,
        )
        print(format_row(row, widths))


def cmd_summary(_: argparse.Namespace) -> None:
    creators = load_creators()
    avg_heat = mean(c.heat for c in creators)
    hottest = max(creators, key=lambda c: c.heat)
    stalest = max(creators, key=lambda c: c.staleness_days)

    print("=== Creator Spark Registry ===")
    print(f"Average heat: {avg_heat:.2f}")
    print(
        f"Top lead: {hottest.handle} ({hottest.heat:.2f}) — {hottest.category} on {hottest.platform}"
    )
    print(
        f"Needs love: {stalest.handle} (last boost {stalest.staleness_days} days ago, note: {stalest.note})"
    )


def cmd_add(args: argparse.Namespace) -> None:
    creators = load_creators()
    handle = _normalize_handle(args.handle)
    if any(c.handle.lower() == handle.lower() for c in creators):
        raise SystemExit(f"Handle {handle} already exists.")

    today = date.today()
    creator = Creator(
        handle=handle,
        platform=args.platform,
        category=args.category,
        note=args.note,
        heat=float(args.heat),
        last_seen=_coerce_date(args.last_seen),
        last_boosted=_coerce_date(args.last_boosted) if args.last_boosted else today,
    )
    creators.append(creator)
    save_creators(creators)
    print(f"Added {handle} with heat {creator.heat:.2f}.")


def cmd_boost(args: argparse.Namespace) -> None:
    creators = load_creators()
    handle = _normalize_handle(args.handle)
    try:
        creator = next(c for c in creators if c.handle.lower() == handle.lower())
    except StopIteration:
        raise SystemExit(f"No creator named {handle} in the registry.")

    creator.last_boosted = date.today()
    if args.note:
        creator.note = args.note
    save_creators(creators)
    print(f"Logged boost for {creator.handle} ({creator.category}).")


def cmd_agenda(args: argparse.Namespace) -> None:
    creators = load_creators()
    cutoff = date.today() - timedelta(days=args.window)
    queued = [c for c in creators if c.last_boosted <= cutoff]
    queued.sort(key=lambda c: (c.staleness_days, c.heat), reverse=True)

    if not queued:
        print(f"All creators were boosted within the last {args.window} days.")
        return

    widths = (16, 6, 6, 60)
    header = ("Handle", "Heat", "Days", "Focus note")
    print("Boost agenda (older than", args.window, "days)")
    print(format_row(header, widths))
    print("-" * 96)

    for creator in queued[: args.limit]:
        row = (
            creator.handle,
            f"{creator.heat:.2f}",
            str(creator.staleness_days),
            creator.note,
        )
        print(format_row(row, widths))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Creator Spark Registry CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list", help="List creators")
    list_parser.add_argument("--limit", type=int, default=None)
    list_parser.add_argument(
        "--sort", choices=["heat", "staleness"], default="heat", help="Sort order"
    )
    list_parser.add_argument("--min-heat", type=float, default=0.0)
    list_parser.set_defaults(func=cmd_list)

    summary_parser = sub.add_parser("summary", help="Show quick stats")
    summary_parser.set_defaults(func=cmd_summary)

    add_parser = sub.add_parser("add", help="Add a new creator")
    add_parser.add_argument("handle")
    add_parser.add_argument("platform")
    add_parser.add_argument("category")
    add_parser.add_argument("note")
    add_parser.add_argument("heat", type=float)
    add_parser.add_argument("--last-seen", default=date.today().isoformat())
    add_parser.add_argument("--last-boosted", default=None)
    add_parser.set_defaults(func=cmd_add)

    boost_parser = sub.add_parser("boost", help="Log that you amplified a creator")
    boost_parser.add_argument("handle")
    boost_parser.add_argument("--note", default=None)
    boost_parser.set_defaults(func=cmd_boost)

    agenda_parser = sub.add_parser("agenda", help="See who needs love next")
    agenda_parser.add_argument("--window", type=int, default=7)
    agenda_parser.add_argument("--limit", type=int, default=5)
    agenda_parser.set_defaults(func=cmd_agenda)

    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()

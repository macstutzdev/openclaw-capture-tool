#!/usr/bin/env python3
"""Read things back out.

Handles the retrieval side: "show my shopping list", "what work tasks are due
this week", "find anything about the inspector". Prints clean human-readable
text (no hidden metadata) that Cindy can relay straight to Telegram.

Examples:
    python3 query.py --bucket shopping
    python3 query.py --bucket work --due-within 7d
    python3 query.py --search inspector
    python3 query.py --bucket work --include-done
"""

import argparse
import re
from datetime import datetime, timedelta

import lib


def _within(record, now, cutoff):
    due = record.get("due_time")
    if not due:
        return False
    try:
        dt = datetime.fromisoformat(due).astimezone()
    except (ValueError, TypeError):
        return False
    return now <= dt <= cutoff


def _parse_window(s):
    m = re.fullmatch(r"(\d+)\s*([dhw])", s.strip().lower())
    if not m:
        raise ValueError("use forms like 7d, 24h, 2w")
    n, unit = int(m.group(1)), m.group(2)
    return {"d": timedelta(days=n), "h": timedelta(hours=n), "w": timedelta(weeks=n)}[unit]


def list_bucket(root, bucket, include_done, window):
    now = datetime.now().astimezone()
    records = lib.read_entries(root, bucket)
    lines = []
    for r in records:
        if not include_done and r.get("status") == "done":
            continue
        if window is not None and not _within(r, now, now + window):
            continue
        lines.append(lib.visible_text(r))
    return lines


def search(root, term):
    term = term.lower()
    out = {}
    for b in lib.BUCKETS:
        hits = [lib.visible_text(r) for r in lib.read_entries(root, b)
                if term in lib.format_line(r).lower()]
        if hits:
            out[b] = hits
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=lib.default_root())
    ap.add_argument("--bucket", choices=lib.BUCKETS)
    ap.add_argument("--search")
    ap.add_argument("--due-within", help="e.g. 7d, 24h, 2w (work tasks with a due time)")
    ap.add_argument("--include-done", action="store_true")
    args = ap.parse_args()

    if args.search:
        results = search(args.root, args.search)
        if not results:
            print(f'Nothing found for "{args.search}".')
            return
        for b, hits in results.items():
            print(f"{b}:")
            for h in hits:
                print(f"  {h}")
        return

    if not args.bucket:
        ap.error("give --bucket or --search")

    window = _parse_window(args.due_within) if args.due_within else None
    lines = list_bucket(args.root, args.bucket, args.include_done, window)
    if not lines:
        print(f"({args.bucket}: nothing to show)")
        return
    for ln in lines:
        print(ln)


if __name__ == "__main__":
    main()

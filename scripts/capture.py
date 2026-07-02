#!/usr/bin/env python3
"""Write one captured item into the right bucket file.

This script does the deterministic part — building the record and appending it
safely. It does NOT decide the bucket: Cindy decides that (see SKILL.md) and
passes it in via --bucket, along with any fields she extracted.

It prints back the stored record and a ready-to-send confirmation message so
Cindy can reply to Cormac immediately.

Examples:
    python3 capture.py --bucket shopping --text "chlorine tablets" --qty 2
    python3 capture.py --bucket work --text "Call the pool inspector" \
        --due 2026-07-01T15:00 --priority high
    python3 capture.py --bucket ideas --text "Photo upload for test logs" \
        --description "let staff attach a photo to each reading" --tags ui,logging
    python3 capture.py --bucket inbox --text "the thing about the thing" \
        --confidence 0.3 --suggested work
"""

import argparse
import json
import sys

import lib


CONFIRM = {
    "work": "Added to your work tasks ✅",
    "shopping": "Added to your shopping list ✅",
    "ideas": "Filed under website ideas ✅",
    "inbox": "Put this in your inbox — wasn't sure where it fits ✅",
}


def build_record(args):
    b = args.bucket
    if b == "work":
        return lib.new_record(
            b, title=args.text, due_time=args.due,
            priority=args.priority or "normal", status="open", notes=args.notes,
        )
    if b == "shopping":
        return lib.new_record(
            b, item=args.text, quantity=args.qty, category=args.category,
            urgency=args.urgency, status="open",
        )
    if b == "ideas":
        tags = [t.strip() for t in args.tags.split(",")] if args.tags else None
        return lib.new_record(
            b, title=args.text, description=args.description,
            tags=tags, status="open",
        )
    # inbox
    return lib.new_record(
        b, raw_input=args.text, confidence_score=args.confidence,
        suggested_category=args.suggested, notes=args.notes,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=lib.default_root())
    ap.add_argument("--bucket", required=True, choices=lib.BUCKETS)
    ap.add_argument("--text", required=True, help="the task / item / idea / raw message")
    ap.add_argument("--due", help="ISO 8601 due time for work tasks, e.g. 2026-07-01T15:00")
    ap.add_argument("--priority", choices=["low", "normal", "high"])
    ap.add_argument("--qty")
    ap.add_argument("--category")
    ap.add_argument("--urgency", choices=["low", "normal", "high"])
    ap.add_argument("--description")
    ap.add_argument("--tags", help="comma-separated")
    ap.add_argument("--confidence", type=float, help="inbox: 0–1 classifier confidence")
    ap.add_argument("--suggested", choices=lib.BUCKETS, help="inbox: best-guess bucket")
    ap.add_argument("--notes")
    args = ap.parse_args()

    try:
        record = build_record(args)
        record["id"] = lib.next_id(args.root, args.bucket)
        lib.append_line(lib.paths(args.root)[args.bucket], lib.format_line(record))
    except Exception as e:  # surface a clear failure Cindy can relay
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(1)

    reminder_needed = bool(args.bucket == "work" and args.due)
    print(json.dumps({
        "ok": True,
        "record": record,
        "confirmation": CONFIRM[args.bucket],
        "reminder_needed": reminder_needed,
    }, indent=2))


if __name__ == "__main__":
    main()

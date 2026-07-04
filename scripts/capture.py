#!/usr/bin/env python3
"""Write one captured item into the right bucket file.

This script does the deterministic part — building the record and appending it
safely. It does NOT decide the bucket: Cindy decides that (see SKILL.md) and
passes it in via --bucket, along with any fields she extracted.

It prints back the stored record and a ready-to-send confirmation message so
Cindy can reply to Cormac immediately.

Examples:
    python3 capture.py --bucket personal_shopping --text "chlorine tablets" --qty 2
    python3 capture.py --bucket work_shopping --text "printer ink" --qty 1
    python3 capture.py --bucket work_todo --text "Call the pool inspector" \
        --due 2026-07-01T15:00 --reminder-at 2026-07-01T14:30 --priority high
    python3 capture.py --bucket personal_todo --text "Book the dentist" \
        --due 2026-07-03T09:00 --reminder-at 2026-07-02T18:00
    python3 capture.py --bucket mypooldash --type idea --text "Photo upload for test logs" \
        --description "let staff attach a photo to each reading" --tags ui,logging
    python3 capture.py --bucket mypooldash --type bug --text "Login form 500s on mobile Safari"
    python3 capture.py --bucket mypooldash --type todo --text "Fix the login bug" \
        --due 2026-07-03T09:00 --reminder-at 2026-07-02T17:00 \
        --reminder-at 2026-07-03T08:30 --priority high
    python3 capture.py --bucket inbox --text "the thing about the thing" \
        --confidence 0.3 --suggested work_todo
"""

import argparse
import json
import sys

import lib


CONFIRM = {
    "work_todo": "Added to your work to-do list ✅",
    "personal_todo": "Added to your personal to-do list ✅",
    "work_shopping": "Added to your work shopping list ✅",
    "personal_shopping": "Added to your personal shopping list ✅",
    "mypooldash": "Filed under MyPoolDashboard ✅",
    "inbox": "Put this in your inbox — wasn't sure where it fits ✅",
}


def _split_csv(value):
    return [item.strip() for item in value.split(",") if item.strip()] if value else None


def _normalize_times(args, warnings):
    """Give --due and every --reminder-at an explicit UTC offset.

    Cron needs an absolute instant, but times often arrive naive (e.g.
    '2026-07-02T15:00'). A naive value is interpreted in America/New_York and
    a warning is recorded so the ambiguity is visible rather than silent."""
    if args.due:
        try:
            args.due, was_naive = lib.normalize_iso(args.due)
            if was_naive:
                warnings.append(f"--due had no timezone; assumed {lib.DEFAULT_TZ} → {args.due}")
        except ValueError:
            raise ValueError(f"--due is not a valid ISO 8601 time: {args.due!r}")
    if args.reminder_at:
        fixed = []
        for t in args.reminder_at:
            try:
                norm, was_naive = lib.normalize_iso(t)
            except ValueError:
                raise ValueError(f"--reminder-at is not a valid ISO 8601 time: {t!r}")
            if was_naive:
                warnings.append(f"--reminder-at had no timezone; assumed {lib.DEFAULT_TZ} → {norm}")
            fixed.append(norm)
        args.reminder_at = fixed


def build_record(args):
    b = args.bucket
    if b in lib.TODO_BUCKETS:
        fields = dict(
            title=args.text, due_time=args.due,
            reminder_times=args.reminder_at,
            priority=args.priority or "normal", urgency=args.urgency,
            status="open", notes=args.notes, tags=_split_csv(args.tags),
            context=args.context,
        )
        return lib.new_record(b, **fields)
    if b in lib.SHOPPING_BUCKETS:
        return lib.new_record(
            b, item=args.text, quantity=args.qty, category=args.category,
            urgency=args.urgency, status="open", tags=_split_csv(args.tags),
            notes=args.notes,
        )
    if b == "mypooldash":
        tags = _split_csv(args.tags)
        kind = args.type or "idea"
        fields = dict(title=args.text, type=kind, description=args.description,
                      tags=tags, status="open", context=args.context)
        if kind == "todo":
            fields.update(
                due_time=args.due, reminder_times=args.reminder_at,
                priority=args.priority or "normal",
            )
        return lib.new_record(b, **fields)
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
    ap.add_argument("--reminder-at", action="append",
                    help="ISO 8601 reminder time; repeat for multiple reminders")
    ap.add_argument("--priority", choices=["low", "normal", "high"])
    ap.add_argument("--qty")
    ap.add_argument("--category")
    ap.add_argument("--urgency", choices=["low", "normal", "high"])
    ap.add_argument("--description")
    ap.add_argument("--tags", help="comma-separated")
    ap.add_argument("--type", choices=["idea", "todo", "bug"],
                     help="mypooldash: what kind of entry this is (default idea)")
    ap.add_argument("--confidence", type=float, help="inbox: 0–1 classifier confidence")
    ap.add_argument("--suggested", choices=lib.BUCKETS, help="inbox: best-guess bucket")
    ap.add_argument("--notes")
    ap.add_argument("--context", help="optional free-form context label")
    args = ap.parse_args()

    warnings = []
    try:
        _normalize_times(args, warnings)
        record = build_record(args)
        record["id"] = lib.next_id(args.root, args.bucket)
        lib.append_line(lib.paths(args.root)[args.bucket], lib.format_line(record))
    except Exception as e:  # surface a clear failure Cindy can relay
        print(json.dumps({"ok": False, "error": str(e)}))
        sys.exit(1)

    reminder_needed = lib.reminds(args.bucket, record) and bool(
        record.get("reminder_times") or record.get("due_time")
    )
    print(json.dumps({
        "ok": True,
        "record": record,
        "confirmation": CONFIRM[args.bucket],
        "reminder_needed": reminder_needed,
        "warnings": warnings,
    }, indent=2))


if __name__ == "__main__":
    main()

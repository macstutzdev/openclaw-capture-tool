#!/usr/bin/env python3
"""Emit the canonical, delivering cron job spec for one Telegram reminder.

This exists so the reminder cron payload is never assembled by hand. Feed it an
id, a reminder time, and the reminder text; it prints the exact JSON to hand to
the cron tool. The spec always uses explicit Telegram *announce* delivery — the
one shape proven to actually reach Cormac. A cron job that merely fires (status
"ok") without a delivery block reports deliveryStatus "not-requested" and sends
nothing; this script makes that mistake impossible.

Usage:
    python3 reminder_cron_spec.py \
        --id wt-20260702-0001 \
        --at 2026-07-04T09:00:00-04:00 \
        --message "⏰ Reminder: Call the pool inspector"

    # or let it build the message from a title + optional due time:
    python3 reminder_cron_spec.py --id wt-20260702-0001 \
        --at 2026-07-04T09:00:00-04:00 --title "Call the pool inspector"

The reminder time may be naive (e.g. 2026-07-04T09:00); it is interpreted in
America/New_York and converted to the absolute UTC instant cron needs.
"""

import argparse
import json
import sys

import lib


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="the reminder id (task id, or task::rN)")
    ap.add_argument("--at", required=True, help="reminder time, ISO 8601 (offset optional)")
    ap.add_argument("--message", help="the exact reminder body to deliver")
    ap.add_argument("--title", help="build the message from this title instead of --message")
    ap.add_argument("--to", help="override the Telegram delivery target")
    args = ap.parse_args()

    try:
        reminder_at, _ = lib.normalize_iso(args.at)
    except ValueError as e:
        print(json.dumps({"ok": False, "error": f"bad --at time: {e}"}))
        sys.exit(1)

    if args.message:
        message = args.message
    elif args.title:
        message = lib.reminder_message(args.title)
    else:
        print(json.dumps({"ok": False, "error": "provide --message or --title"}))
        sys.exit(1)

    spec = lib.reminder_cron_spec(args.id, reminder_at, message, telegram_to=args.to)
    print(json.dumps(spec, indent=2))


if __name__ == "__main__":
    main()

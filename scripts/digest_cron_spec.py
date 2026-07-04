#!/usr/bin/env python3
"""Emit recurring cron specs for proactive Telegram digests.

A digest is a scheduled OpenClaw cron job that wakes an isolated agent (with the
capture-tool skill loaded) to run a review and push it to Cormac unprompted — a
morning checklist, an evening wrap-up, and a Sunday-night weekly review. The
agent sends an interactive `review.py --buttons` checklist itself, so unlike a
reminder these use `delivery.mode: "none"` and full context (not lightContext).

Create these once with your cron tool. They recur on an Eastern-time schedule.

Usage:
    python3 digest_cron_spec.py                 # all three (JSON array)
    python3 digest_cron_spec.py --preset morning
    python3 digest_cron_spec.py --preset evening --to 8688841600
"""

import argparse
import json

import lib


# Off-the-hour minutes on purpose: everyone who asks for "8am" lands on :00 and
# hammers the API at once. A few minutes off is invisible to Cormac.
PRESETS = {
    "morning": {
        "slug": "morning",
        "expr": "57 7 * * *",
        "message": (
            "Morning capture digest. Using the capture-tool skill:\n"
            "1. Run `review.py --mode today --buttons` and send that payload to "
            "Cormac on Telegram so he can tap items done.\n"
            "2. Run `reconcile_crons.py`; if it lists `to_nudge` items, add one "
            "short line chasing the most overdue, then run "
            "`reconcile_crons.py --mark-nudged`.\n"
            "3. Add one brief line of judgement about what's most urgent today.\n"
            "If nothing is due or overdue, just send a short 'all clear for "
            "today' note. Do nothing else."
        ),
    },
    "evening": {
        "slug": "evening",
        "expr": "3 18 * * *",
        "message": (
            "Evening capture wrap-up. Using the capture-tool skill:\n"
            "1. Run `review.py --mode today --buttons` and send the checklist to "
            "Cormac on Telegram — this is what's still open at end of day.\n"
            "2. Run `reconcile_crons.py`; if it lists `to_nudge` items, chase "
            "them in one short line, then run `reconcile_crons.py --mark-nudged`.\n"
            "3. Mention anything due tomorrow so he can prep.\n"
            "If everything is done, send a short 'you're clear for tonight' note. "
            "Do nothing else."
        ),
    },
    "weekly": {
        "slug": "weekly",
        "expr": "7 19 * * 0",
        "message": (
            "Weekly capture review (Sunday night). Using the capture-tool skill:\n"
            "1. Run `review.py --mode week --buttons` and send the checklist to "
            "Cormac on Telegram.\n"
            "2. Run `review.py --mode stale` and ask, in one short line, whether "
            "any stale open items should be done, snoozed, delegated, or dropped.\n"
            "3. Add a brief judgement on the week ahead.\n"
            "Do nothing else."
        ),
    },
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", choices=list(PRESETS), help="one digest (default: all)")
    ap.add_argument("--tz", help=f"IANA timezone (default {lib.DEFAULT_TZ})")
    ap.add_argument("--to", help="Telegram target (informational; the agent sends the checklist)")
    args = ap.parse_args()

    names = [args.preset] if args.preset else list(PRESETS)
    specs = []
    for name in names:
        p = PRESETS[name]
        message = p["message"]
        if args.to:
            message += f"\n\nSend to Telegram chat {args.to}."
        specs.append(lib.digest_cron_spec(p["slug"], p["expr"], message, tz=args.tz))

    print(json.dumps(specs[0] if args.preset else specs, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

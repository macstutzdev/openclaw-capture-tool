#!/usr/bin/env python3
"""Build practical review briefs from captured items.

This is the planning counterpart to capture.py. It reads every bucket and
prints a clean brief the agent can relay or use to guide a planning
conversation: today, week, stale, inbox, or full cleanup review.
"""

import argparse
from datetime import datetime, time, timedelta

import lib


ACTIVE_STATUSES = ("open", "waiting", "blocked", "delegated", "snoozed")


def _parse_dt(value):
    try:
        return datetime.fromisoformat(value).astimezone()
    except (TypeError, ValueError):
        return None


def _all_records(root):
    records = []
    for bucket in lib.BUCKETS:
        for record in lib.read_entries(root, bucket):
            records.append(record)
    return records


def _is_active(record):
    return record.get("status", "open") in ACTIVE_STATUSES


def _due_between(record, start, end):
    due = _parse_dt(record.get("due_time"))
    return due is not None and start <= due <= end


def _overdue(record, now):
    due = _parse_dt(record.get("due_time"))
    return due is not None and due < now and record.get("status", "open") != "done"


def _created_before(record, cutoff):
    created = _parse_dt(record.get("created_at"))
    return created is not None and created < cutoff


def _section(title, records):
    lines = [f"{title}:"]
    if not records:
        lines.append("  Nothing.")
        return lines
    for record in records:
        lines.append(f"  {record['bucket']}: {lib.visible_text(record)}")
    return lines


def _shopping(records):
    return [
        r for r in records
        if r["bucket"] in lib.SHOPPING_BUCKETS and _is_active(r)
    ]


def _inbox(records):
    return [
        r for r in records
        if r["bucket"] == "inbox" and r.get("status", "open") != "done"
    ]


def _state(records, status):
    return [r for r in records if r.get("status", "open") == status]


def _stale(records, now, days):
    cutoff = now - timedelta(days=days)
    return [
        r for r in records
        if _is_active(r)
        and r["bucket"] != "inbox"
        and _created_before(r, cutoff)
        and not r.get("due_time")
    ]


def build_review(root, mode, stale_days):
    now = datetime.now().astimezone()
    today_end = datetime.combine(now.date(), time.max, tzinfo=now.tzinfo)
    week_end = today_end + timedelta(days=7)
    records = _all_records(root)

    overdue = [r for r in records if _overdue(r, now)]
    due_today = [r for r in records if _is_active(r) and _due_between(r, now, today_end)]
    due_week = [r for r in records if _is_active(r) and _due_between(r, now, week_end)]

    if mode == "today":
        sections = [
            _section("Overdue", overdue),
            _section("Due today", due_today),
            _section("Blocked", _state(records, "blocked")),
            _section("Waiting", _state(records, "waiting")),
            _section("Inbox", _inbox(records)),
        ]
    elif mode == "week":
        sections = [
            _section("Overdue", overdue),
            _section("Due in the next 7 days", due_week),
            _section("Delegated", _state(records, "delegated")),
            _section("Waiting", _state(records, "waiting")),
            _section("Stale open items", _stale(records, now, stale_days)),
        ]
    elif mode == "stale":
        sections = [
            _section(f"Open items older than {stale_days} days with no due date",
                     _stale(records, now, stale_days)),
            _section("Snoozed", _state(records, "snoozed")),
            _section("Blocked", _state(records, "blocked")),
            _section("Waiting", _state(records, "waiting")),
        ]
    elif mode == "inbox":
        sections = [_section("Inbox", _inbox(records))]
    else:
        sections = [
            _section("Overdue", overdue),
            _section("Due today", due_today),
            _section("Due in the next 7 days", due_week),
            _section("Shopping", _shopping(records)),
            _section("Inbox", _inbox(records)),
            _section("Stale open items", _stale(records, now, stale_days)),
            _section("Blocked", _state(records, "blocked")),
            _section("Waiting", _state(records, "waiting")),
            _section("Delegated", _state(records, "delegated")),
        ]

    out = [f"Capture review: {mode}"]
    for section in sections:
        out.extend(section)
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=lib.default_root())
    ap.add_argument(
        "--mode",
        choices=["today", "week", "stale", "inbox", "all"],
        default="today",
    )
    ap.add_argument("--stale-days", type=int, default=14)
    args = ap.parse_args()
    print(build_review(args.root, args.mode, args.stale_days))


if __name__ == "__main__":
    main()

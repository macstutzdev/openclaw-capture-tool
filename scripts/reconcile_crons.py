#!/usr/bin/env python3
"""Work out which Telegram reminders should exist right now.

Important boundary: this script does NOT create cron jobs or send Telegram
messages itself — those are Cindy's own tools, which this script has no access
to. Instead it reads work.md and the record of what's already scheduled, then
prints a *plan*: which reminders to schedule and which to cancel. Cindy carries
out the plan with her cron tool, then runs this again with --commit to record
what she did (so nothing gets double-scheduled next time).

The loop Cindy follows:
    1. python3 reconcile_crons.py                 # see the plan (dry run)
    2. create / cancel the jobs with the cron tool
    3. python3 reconcile_crons.py --commit         # record the new state

A task earns a reminder when it is in work.md, still open, and has a due_time
in the future. A previously-scheduled reminder is cancelled when its task is
gone, marked done, or its due time has passed.
"""

import argparse
import json
from datetime import datetime

import lib


def _parse_dt(s):
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def build_plan(root):
    now = datetime.now().astimezone()
    meta = lib.load_metadata(root)
    scheduled = meta["scheduled"]

    tasks = {r["id"]: r for r in lib.read_entries(root, "work")}
    to_schedule, to_cancel = [], []

    # New reminders needed.
    for tid, rec in tasks.items():
        due = _parse_dt(rec.get("due_time", ""))
        if not due:
            continue
        if due.tzinfo is None:
            due = due.astimezone()
        if rec.get("status") == "open" and due > now and tid not in scheduled:
            to_schedule.append({
                "id": tid,
                "due_time": rec["due_time"],
                "message": f"⏰ Reminder: {rec['title']}",
            })

    # Reminders that no longer apply.
    for tid, info in scheduled.items():
        rec = tasks.get(tid)
        due = _parse_dt(info.get("due_time", ""))
        past = due is not None and (due.astimezone() if due.tzinfo is None else due) <= now
        if rec is None or rec.get("status") == "done" or past:
            to_cancel.append({"id": tid, "cron_note": info.get("cron_note")})

    return meta, {"to_schedule": to_schedule, "to_cancel": to_cancel}


def commit(root, meta, plan):
    scheduled = meta["scheduled"]
    for item in plan["to_schedule"]:
        scheduled[item["id"]] = {
            "due_time": item["due_time"],
            "message": item["message"],
            "cron_note": item.get("cron_note"),
        }
    for item in plan["to_cancel"]:
        scheduled.pop(item["id"], None)
    lib.save_metadata(root, meta)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=lib.default_root())
    ap.add_argument("--commit", action="store_true",
                    help="record the plan as done (run AFTER creating/cancelling jobs)")
    args = ap.parse_args()

    meta, plan = build_plan(args.root)
    if args.commit:
        commit(args.root, meta, plan)
        plan["committed"] = True
    print(json.dumps(plan, indent=2))


if __name__ == "__main__":
    main()

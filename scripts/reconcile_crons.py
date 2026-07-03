#!/usr/bin/env python3
"""Work out which Telegram reminders should exist right now.

Important boundary: this script does NOT create cron jobs or send Telegram
messages itself — those are Cindy's own tools, which this script has no access
to. Instead it reads work_todo.md, personal_todo.md, and any mypooldash entries
filed as type "todo", plus the record of what's already scheduled, then prints
a *plan*: which reminders to schedule and which to cancel. Cindy carries out
the plan with her cron tool, then runs this again with --commit to record what
she did (so nothing gets double-scheduled next time).

The loop Cindy follows:
    1. python3 reconcile_crons.py                 # see the plan (dry run)
    2. create / cancel the jobs with the cron tool
    3. python3 reconcile_crons.py --commit         # record the new state

A task earns reminders when it is in work_todo.md, personal_todo.md, or is a
mypooldash entry with type "todo", still open, and has reminder_times in the
future. Older records without reminder_times fall back to a single reminder at
due_time. A previously-scheduled reminder is cancelled when its task is gone,
leaves open status, removed from reminder_times, or its reminder time has
passed.
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


def _as_local(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.astimezone()
    return dt


def _short_dt(s):
    dt = _as_local(_parse_dt(s))
    if dt is None:
        return s
    hour = dt.hour % 12 or 12
    minute = f":{dt.minute:02d}" if dt.minute else ""
    ampm = "am" if dt.hour < 12 else "pm"
    return f"{dt.strftime('%a')}, {dt.month}/{dt.day} @ {hour}{minute}{ampm}"


def _reminder_message(record):
    due = record.get("due_time")
    suffix = f" (due {_short_dt(due)})" if due else ""
    return f"⏰ Reminder: {record['title']}{suffix}"


def _reminder_times(record):
    times = record.get("reminder_times")
    if isinstance(times, list):
        return [t for t in times if t]
    if isinstance(times, str):
        return [times]
    due = record.get("due_time")
    return [due] if due else []


def _reminder_id(task_id, index, total):
    return task_id if total == 1 else f"{task_id}::r{index + 1}"


def _task_id_from_schedule(reminder_id, info):
    return info.get("task_id") or reminder_id.split("::", 1)[0]


def _reminder_time_from_schedule(info):
    return info.get("reminder_time") or info.get("due_time")


def build_plan(root):
    now = datetime.now().astimezone()
    meta = lib.load_metadata(root)
    scheduled = meta["scheduled"]

    tasks = lib.all_remindable_entries(root)
    to_schedule, to_cancel = [], []
    active_reminder_ids = set()

    # New reminders needed.
    for tid, rec in tasks.items():
        reminder_times = _reminder_times(rec)
        total = len(reminder_times)
        for index, reminder_time in enumerate(reminder_times):
            reminder_at = _as_local(_parse_dt(reminder_time))
            if not reminder_at:
                continue
            rid = _reminder_id(tid, index, total)
            active_reminder_ids.add(rid)
            if rec.get("status") != "open" or reminder_at <= now or rid in scheduled:
                continue
            to_schedule.append({
                "id": rid,
                "task_id": tid,
                "reminder_time": reminder_time,
                "due_time": rec.get("due_time"),
                "message": _reminder_message(rec),
            })

    # Reminders that no longer apply.
    for rid, info in scheduled.items():
        tid = _task_id_from_schedule(rid, info)
        rec = tasks.get(tid)
        reminder_at = _as_local(_parse_dt(_reminder_time_from_schedule(info)))
        past = reminder_at is not None and reminder_at <= now
        stale = rid not in active_reminder_ids
        if rec is None or rec.get("status", "open") != "open" or past or stale:
            to_cancel.append({"id": rid, "task_id": tid, "cron_note": info.get("cron_note")})

    return meta, {"to_schedule": to_schedule, "to_cancel": to_cancel}


def commit(root, meta, plan):
    scheduled = meta["scheduled"]
    for item in plan["to_schedule"]:
        scheduled[item["id"]] = {
            "task_id": item["task_id"],
            "reminder_time": item["reminder_time"],
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

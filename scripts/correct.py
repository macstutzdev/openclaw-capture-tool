#!/usr/bin/env python3
"""Apply a correction: move an item to another bucket, or mark it done.

Cindy figures out *which* item Cormac means from his phrasing ("move the
inspector one to work", "I bought the chlorine") — she identifies the id, then
calls this script to make the edit safely. Working by id avoids editing the
wrong line when two entries look similar.

Examples:
    python3 correct.py --id x-20260701-0002 --move work_todo
    python3 correct.py --id ps-20260701-0005 --done
    python3 correct.py --id wt-20260701-0001 --undone
    python3 correct.py --id wt-20260701-0003 --status waiting --waiting-on "Alex"
    python3 correct.py --id pt-20260701-0004 --status snoozed --snooze-until 2026-07-08T09:00:00-04:00
"""

import argparse
import json
import sys

import lib


LIFECYCLE_FIELDS = ("snooze_until", "waiting_on", "delegated_to", "blocked_reason")


def find(root, entry_id):
    for b in lib.BUCKETS:
        recs = lib.read_entries(root, b)
        for i, r in enumerate(recs):
            if r.get("id") == entry_id:
                return b, recs, i
    return None, None, None


def _clear_lifecycle(record):
    for field in LIFECYCLE_FIELDS:
        record.pop(field, None)


def _split_csv(values):
    out = []
    for value in values or []:
        out.extend(item.strip() for item in value.split(",") if item.strip())
    return out


def _apply_tags(record, add_tags, remove_tags):
    tags = list(record.get("tags") or [])
    for tag in _split_csv(add_tags):
        if tag not in tags:
            tags.append(tag)
    remove = set(_split_csv(remove_tags))
    if remove:
        tags = [tag for tag in tags if tag not in remove]
    if tags:
        record["tags"] = tags
    else:
        record.pop("tags", None)


def apply_lifecycle(record, args):
    if args.done:
        record["status"] = "done"
        _clear_lifecycle(record)
    elif args.undone:
        record["status"] = "open"
        _clear_lifecycle(record)
    elif args.status:
        record["status"] = args.status
        if args.status in ("open", "done", "dropped"):
            _clear_lifecycle(record)
    if args.snooze_until:
        record["snooze_until"] = args.snooze_until
    if args.waiting_on:
        record["waiting_on"] = args.waiting_on
    if args.delegated_to:
        record["delegated_to"] = args.delegated_to
    if args.blocked_reason:
        record["blocked_reason"] = args.blocked_reason
    if args.priority:
        record["priority"] = args.priority
    if args.urgency:
        record["urgency"] = args.urgency
    if args.notes:
        record["notes"] = args.notes
    if args.context:
        record["context"] = args.context
    _apply_tags(record, args.add_tag, args.remove_tag)


def move_record(record, target):
    """Carry a record into a new bucket, translating the text field and
    dropping fields that don't apply to the target."""
    text = (record.get("title") or record.get("item")
            or record.get("raw_input") or "")
    fields = {}
    if target in lib.TODO_BUCKETS:
        fields = {
            "title": text,
            "due_time": record.get("due_time"),
            "reminder_times": record.get("reminder_times"),
            "priority": record.get("priority", "normal"),
            "urgency": record.get("urgency"),
            "tags": record.get("tags"),
            "context": record.get("context"),
            "status": "open",
        }
    elif target in lib.SHOPPING_BUCKETS:
        fields = {
            "item": text,
            "urgency": record.get("urgency"),
            "tags": record.get("tags"),
            "context": record.get("context"),
            "status": "open",
        }
    elif target == "mypooldash":
        # Coming from a todo bucket with a due time carries over as a
        # mypooldash to-do; otherwise it lands as a plain idea.
        if record.get("due_time"):
            fields = {"title": text, "type": "todo",
                      "due_time": record["due_time"],
                      "reminder_times": record.get("reminder_times"),
                      "priority": record.get("priority", "normal"),
                      "urgency": record.get("urgency"),
                      "tags": record.get("tags"),
                      "context": record.get("context"),
                      "status": "open"}
        else:
            fields = {"title": text, "type": record.get("type", "idea"),
                      "tags": record.get("tags"),
                      "context": record.get("context"),
                      "status": "open"}
    else:
        fields = {"raw_input": text, "tags": record.get("tags"),
                  "context": record.get("context")}
    new = lib.new_record(target, **fields)
    new["created_at"] = record.get("created_at", new["created_at"])  # keep original time
    return new


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=lib.default_root())
    ap.add_argument("--id", required=True)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--move", choices=lib.BUCKETS)
    g.add_argument("--done", action="store_true")
    g.add_argument("--undone", action="store_true")
    g.add_argument("--status", choices=lib.STATUSES)
    g.add_argument("--update", action="store_true")
    ap.add_argument("--snooze-until")
    ap.add_argument("--waiting-on")
    ap.add_argument("--delegated-to")
    ap.add_argument("--blocked-reason")
    ap.add_argument("--priority", choices=["low", "normal", "high"])
    ap.add_argument("--urgency", choices=["low", "normal", "high"])
    ap.add_argument("--notes")
    ap.add_argument("--context")
    ap.add_argument("--add-tag", action="append")
    ap.add_argument("--remove-tag", action="append")
    args = ap.parse_args()

    bucket, recs, idx = find(args.root, args.id)
    if bucket is None:
        print(json.dumps({"ok": False, "error": f"id {args.id} not found"}))
        sys.exit(1)

    record = recs[idx]

    if args.done or args.undone or args.status or args.update:
        apply_lifecycle(record, args)
        lib.rewrite_bucket(args.root, bucket, recs)
        if args.done:
            msg = "Marked done ✅"
        elif args.undone:
            msg = "Reopened ✅"
        elif args.status:
            msg = f"Marked {args.status} ✅"
        else:
            msg = "Updated ✅"
        print(json.dumps({
            "ok": True, "action": "update", "confirmation": msg,
            "record": record,
        }, indent=2))
        return

    # move
    if args.move == bucket:
        print(json.dumps({"ok": True, "note": "already in that bucket"}))
        return
    moved = move_record(record, args.move)
    moved["id"] = lib.next_id(args.root, args.move)
    recs.pop(idx)
    lib.rewrite_bucket(args.root, bucket, recs)
    lib.append_line(lib.paths(args.root)[args.move], lib.format_line(moved))
    print(json.dumps({
        "ok": True, "action": "move",
        "from": bucket, "to": args.move, "record": moved,
        "confirmation": f"Moved to {args.move} ✅",
    }, indent=2))


if __name__ == "__main__":
    main()

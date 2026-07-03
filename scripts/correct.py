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
"""

import argparse
import json
import sys

import lib


def find(root, entry_id):
    for b in lib.BUCKETS:
        recs = lib.read_entries(root, b)
        for i, r in enumerate(recs):
            if r.get("id") == entry_id:
                return b, recs, i
    return None, None, None


def move_record(record, target):
    """Carry a record into a new bucket, translating the text field and
    dropping fields that don't apply to the target."""
    text = (record.get("title") or record.get("item")
            or record.get("raw_input") or "")
    fields = {}
    if target in lib.TODO_BUCKETS:
        fields = {"title": text, "priority": "normal", "status": "open"}
    elif target in lib.SHOPPING_BUCKETS:
        fields = {"item": text, "status": "open"}
    elif target == "mypooldash":
        # Coming from a todo bucket with a due time carries over as a
        # mypooldash to-do; otherwise it lands as a plain idea.
        if record.get("due_time"):
            fields = {"title": text, "type": "todo",
                      "due_time": record["due_time"],
                      "priority": record.get("priority", "normal"),
                      "status": "open"}
        else:
            fields = {"title": text, "type": record.get("type", "idea"),
                      "status": "open"}
    else:
        fields = {"raw_input": text}
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
    args = ap.parse_args()

    bucket, recs, idx = find(args.root, args.id)
    if bucket is None:
        print(json.dumps({"ok": False, "error": f"id {args.id} not found"}))
        sys.exit(1)

    record = recs[idx]

    if args.done or args.undone:
        record["status"] = "done" if args.done else "open"
        lib.rewrite_bucket(args.root, bucket, recs)
        msg = "Marked done ✅" if args.done else "Reopened ✅"
        print(json.dumps({"ok": True, "action": "status", "confirmation": msg,
                          "record": record}, indent=2))
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

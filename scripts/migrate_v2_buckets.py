#!/usr/bin/env python3
"""One-time migration from the v1 bucket layout to v2.

v1 had four buckets: work, shopping, ideas, inbox.
v2 splits work and shopping by domain: work_todo, personal_todo,
work_shopping, personal_shopping, plus the unchanged ideas and inbox.

This script only touches the two buckets that were renamed:
  - capture/work.md      -> capture/work_todo.md       (id prefix w- -> wt-)
  - capture/shopping.md  -> capture/personal_shopping.md (id prefix s- -> ps-)

personal_todo.md and work_shopping.md are brand new — they start empty.
ideas.md and inbox.md are untouched.

Like reconcile_crons.py, this is dry-run by default so you can see the plan
before anything is written:

    python3 migrate_v2_buckets.py                # see the plan
    python3 migrate_v2_buckets.py --commit        # actually migrate

Safe to run once. After a successful --commit, the old work.md and
shopping.md are renamed to *.v1.bak (not deleted) and the script becomes a
no-op on a second run, since it only acts when those files still exist.
"""

import argparse
import json
import os

import lib

_OLD_HEADERS = {
    "work": "# Work tasks\n\n",
    "shopping": "# Shopping\n\n",
}
_RENAME = {"work": "work_todo", "shopping": "personal_shopping"}
_OLD_PREFIX = {"work": "w", "shopping": "s"}


def _read_old_bucket(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            rec = lib.parse_line(line)
            if rec:
                out.append(rec)
    return out


def build_plan(root):
    cap = os.path.join(root, "capture")
    old_paths = {b: os.path.join(cap, f"{b}.md") for b in _RENAME}

    old_records = {b: _read_old_bucket(p) for b, p in old_paths.items()}
    id_map = {}
    migrated = {}
    for old_bucket, new_bucket in _RENAME.items():
        prefix = _ID_PREFIX_FOR(new_bucket)
        recs = []
        for rec in old_records[old_bucket]:
            old_id = rec.get("id", "")
            suffix = old_id.split("-", 1)[1] if "-" in old_id else old_id
            new_id = f"{prefix}-{suffix}"
            id_map[old_id] = new_id
            rec = dict(rec)
            rec["bucket"] = new_bucket
            rec["id"] = new_id
            recs.append(rec)
        migrated[new_bucket] = recs

    old_meta_path = os.path.join(cap, "metadata.json")
    old_meta = {"counters": {}, "scheduled": {}}
    if os.path.exists(old_meta_path):
        with open(old_meta_path, encoding="utf-8") as f:
            old_meta = json.load(f)

    old_counters = old_meta.get("counters", {})
    new_counters = {
        "work_todo": old_counters.get("work", 0),
        "personal_todo": 0,
        "work_shopping": 0,
        "personal_shopping": old_counters.get("shopping", 0),
        "ideas": old_counters.get("ideas", 0),
        "inbox": old_counters.get("inbox", 0),
    }

    new_scheduled = {}
    unmapped_scheduled = []
    for old_id, info in old_meta.get("scheduled", {}).items():
        new_id = id_map.get(old_id)
        if new_id:
            new_scheduled[new_id] = info
        else:
            unmapped_scheduled.append(old_id)
            new_scheduled[old_id] = info  # keep rather than drop silently

    nothing_to_do = not old_records["work"] and not old_records["shopping"] \
        and not any(os.path.exists(p) for p in old_paths.values())

    return {
        "old_paths": old_paths,
        "migrated": migrated,
        "id_map": id_map,
        "new_counters": new_counters,
        "new_scheduled": new_scheduled,
        "unmapped_scheduled": unmapped_scheduled,
        "nothing_to_do": nothing_to_do,
    }


def _ID_PREFIX_FOR(new_bucket):
    # Keep in sync with lib._ID_PREFIX; duplicated read-only here so this
    # script doesn't reach into lib's private table.
    return {"work_todo": "wt", "personal_shopping": "ps"}[new_bucket]


def commit(root, plan):
    cap = os.path.join(root, "capture")
    os.makedirs(cap, exist_ok=True)

    for new_bucket, recs in plan["migrated"].items():
        lib.rewrite_bucket(root, new_bucket, recs)

    for b in ("personal_todo", "work_shopping"):
        p = lib.paths(root)[b]
        if not os.path.exists(p):
            with open(p, "w", encoding="utf-8") as f:
                f.write(lib.HEADERS[b])

    lib.save_metadata(root, {
        "counters": plan["new_counters"],
        "scheduled": plan["new_scheduled"],
    })

    backed_up = []
    for old_bucket, old_path in plan["old_paths"].items():
        if os.path.exists(old_path):
            bak = old_path + ".v1.bak"
            os.replace(old_path, bak)
            backed_up.append(bak)
    return backed_up


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=lib.default_root())
    ap.add_argument("--commit", action="store_true",
                     help="actually migrate (default is dry-run)")
    args = ap.parse_args()

    plan = build_plan(args.root)

    if plan["nothing_to_do"]:
        print(json.dumps({
            "ok": True,
            "note": "no v1 work.md or shopping.md found — nothing to migrate",
        }, indent=2))
        return

    summary = {
        "ok": True,
        "committed": False,
        "work_todo_count": len(plan["migrated"].get("work_todo", [])),
        "personal_shopping_count": len(plan["migrated"].get("personal_shopping", [])),
        "id_map": plan["id_map"],
        "new_counters": plan["new_counters"],
        "unmapped_scheduled": plan["unmapped_scheduled"],
    }

    if args.commit:
        backed_up = commit(args.root, plan)
        summary["committed"] = True
        summary["backed_up_files"] = backed_up

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

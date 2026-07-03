#!/usr/bin/env python3
"""One-time migration: rename the `ideas` bucket to `mypooldash`.

v2 had a bucket called `ideas`, used only for MyPoolDashboard concepts.
v3 broadens it into `mypooldash`, which also holds to-dos and bug reports for
the project (see references/SCHEMAS.md for the new `type` field). This script
only touches that one bucket:

  - capture/ideas.md -> capture/mypooldash.md   (id prefix i- -> mpd-)

Every migrated record gets `"type": "idea"` (the only kind `ideas.md` could
hold), so nothing changes in what it means or how it's rendered beyond the
file name, id prefix, and the new field. All other buckets are untouched.

Dry-run by default, like the other migration script:

    python3 migrate_v3_mypooldash.py            # see the plan
    python3 migrate_v3_mypooldash.py --commit   # actually migrate

Safe to run once. After a successful --commit, ideas.md is renamed to
ideas.md.v2.bak (not deleted) and the script becomes a no-op on a second run,
since it only acts when ideas.md still exists.
"""

import argparse
import json
import os

import lib


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
    old_path = os.path.join(cap, "ideas.md")
    old_records = _read_old_bucket(old_path)

    id_map = {}
    migrated = []
    for rec in old_records:
        old_id = rec.get("id", "")
        suffix = old_id.split("-", 1)[1] if "-" in old_id else old_id
        new_id = f"mpd-{suffix}"
        id_map[old_id] = new_id
        rec = dict(rec)
        rec["bucket"] = "mypooldash"
        rec["id"] = new_id
        rec.setdefault("type", "idea")
        migrated.append(rec)

    old_meta_path = os.path.join(cap, "metadata.json")
    old_meta = {"counters": {}, "scheduled": {}}
    if os.path.exists(old_meta_path):
        with open(old_meta_path, encoding="utf-8") as f:
            old_meta = json.load(f)

    old_counters = old_meta.get("counters", {})
    new_counters = dict(old_meta.get("counters", {}))
    new_counters.pop("ideas", None)
    new_counters["mypooldash"] = old_counters.get("ideas", 0)
    for b in lib.BUCKETS:
        new_counters.setdefault(b, 0)

    nothing_to_do = not old_records and not os.path.exists(old_path)

    return {
        "old_path": old_path,
        "migrated": migrated,
        "id_map": id_map,
        "new_counters": new_counters,
        "nothing_to_do": nothing_to_do,
    }


def commit(root, plan):
    cap = os.path.join(root, "capture")
    os.makedirs(cap, exist_ok=True)

    lib.rewrite_bucket(root, "mypooldash", plan["migrated"])

    meta = lib.load_metadata(root)
    meta["counters"] = plan["new_counters"]
    lib.save_metadata(root, meta)

    backed_up = None
    if os.path.exists(plan["old_path"]):
        bak = plan["old_path"] + ".v2.bak"
        os.replace(plan["old_path"], bak)
        backed_up = bak
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
            "note": "no v2 ideas.md found — nothing to migrate",
        }, indent=2))
        return

    summary = {
        "ok": True,
        "committed": False,
        "mypooldash_count": len(plan["migrated"]),
        "id_map": plan["id_map"],
        "new_counters": plan["new_counters"],
    }

    if args.commit:
        backed_up = commit(args.root, plan)
        summary["committed"] = True
        summary["backed_up_file"] = backed_up

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

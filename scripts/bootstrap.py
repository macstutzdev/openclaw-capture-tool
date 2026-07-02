#!/usr/bin/env python3
"""One-time setup: create the capture/ folder, empty bucket files, and
metadata.json. Safe to run more than once — it never overwrites files that
already have content.

Usage:
    python3 bootstrap.py                 # uses the default workspace
    python3 bootstrap.py --root /some/path
"""

import argparse
import json
import os

import lib


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=lib.default_root())
    args = ap.parse_args()

    p = lib.paths(args.root)
    os.makedirs(p["capture_dir"], exist_ok=True)

    created = []
    for b in lib.BUCKETS:
        if not os.path.exists(p[b]):
            with open(p[b], "w", encoding="utf-8") as f:
                f.write(lib.HEADERS[b])
            created.append(os.path.basename(p[b]))

    if not os.path.exists(p["metadata"]):
        lib.save_metadata(args.root, {
            "counters": {b: 0 for b in lib.BUCKETS},
            "scheduled": {},
        })
        created.append("metadata.json")

    print(json.dumps({
        "ok": True,
        "capture_dir": p["capture_dir"],
        "created": created or "nothing (already set up)",
    }, indent=2))


if __name__ == "__main__":
    main()

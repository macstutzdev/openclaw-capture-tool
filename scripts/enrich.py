#!/usr/bin/env python3
"""Suggest capture enrichment: tags, urgency, and likely duplicates.

This is intentionally a hinting tool. The agent still decides what to file or
change, but this gives it a consistent second pass during cleanup and reviews.
"""

import argparse
import json

import lib


TAG_RULES = {
    "permit": ["permit", "county", "inspection", "inspector"],
    "client": ["client", "customer"],
    "finance": ["invoice", "payment", "expense", "receipt", "tax"],
    "health": ["doctor", "dentist", "appointment", "pharmacy"],
    "family": ["mom", "dad", "family", "kids", "school"],
    "pool": ["pool", "chlorine", "chemical", "facility", "reading"],
    "mypooldash": ["mypooldash", "dashboard", "app", "website", "site"],
    "bug": ["bug", "broken", "error", "500", "crash", "not working"],
    "followup": ["follow up", "reply", "call", "email", "ping"],
}

HIGH_URGENCY = [
    "urgent", "asap", "today", "tonight", "overdue", "deadline", "by end of day",
    "eod", "before close", "tomorrow morning",
]

NORMAL_URGENCY = ["tomorrow", "this week", "by friday", "next week"]


def _find_record(root, entry_id):
    for bucket in lib.BUCKETS:
        for record in lib.read_entries(root, bucket):
            if record.get("id") == entry_id:
                return record
    return None


def _suggest_tags(text):
    lower = text.lower()
    tags = []
    for tag, signals in TAG_RULES.items():
        if any(signal in lower for signal in signals):
            tags.append(tag)
    return tags


def _suggest_urgency(text):
    lower = text.lower()
    if any(signal in lower for signal in HIGH_URGENCY):
        return "high"
    if any(signal in lower for signal in NORMAL_URGENCY):
        return "normal"
    return "low"


def enrich(root, text, bucket=None, entry_id=None, min_score=0.55):
    tags = _suggest_tags(text)
    urgency = _suggest_urgency(text)
    return {
        "ok": True,
        "text": text,
        "suggested_tags": tags,
        "suggested_urgency": urgency,
        "duplicate_candidates": lib.duplicate_candidates(
            root, text, bucket, entry_id, min_score),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=lib.default_root())
    ap.add_argument("--text")
    ap.add_argument("--id")
    ap.add_argument("--bucket", choices=lib.BUCKETS)
    ap.add_argument("--min-score", type=float, default=0.55)
    args = ap.parse_args()

    text = args.text
    entry_id = args.id
    bucket = args.bucket
    if args.id:
        record = _find_record(args.root, args.id)
        if record is None:
            print(json.dumps({"ok": False, "error": f"id {args.id} not found"}))
            raise SystemExit(1)
        text = lib.record_text(record)
        bucket = record["bucket"]
        entry_id = record["id"]
    if not text:
        ap.error("give --text or --id")

    print(json.dumps(enrich(args.root, text, bucket, entry_id, args.min_score), indent=2))


if __name__ == "__main__":
    main()

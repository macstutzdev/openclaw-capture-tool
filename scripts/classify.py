#!/usr/bin/env python3
"""Rule-based fallback classifier.

Cindy (an LLM) is the *primary* classifier — she reads the message and uses the
heuristics in SKILL.md, which handles nuance far better than keyword matching.
This script exists for two narrower jobs:

  1. Offline testing — check sorting behaves sensibly on sample inputs without
     needing a model in the loop.
  2. A tie-breaker hint — if Cindy is unsure, she can run this for a second
     opinion and a rough confidence number.

Output: JSON {bucket, confidence, reasons}. Confidence is a rough 0–1 signal,
not a calibrated probability. Low confidence should push borderline items to
the inbox rather than a wrong bucket.

Usage:
    python3 classify.py --text "buy chlorine tablets"
"""

import argparse
import json
import re

# Signal words per bucket. Kept deliberately small and legible — tune freely.
SIGNALS = {
    "shopping": [
        "buy", "pick up", "pickup", "get some", "grocery", "groceries",
        "milk", "eggs", "bread", "coffee", "we need", "run out of", "out of",
        "restock", "order more", "shopping list",
    ],
    "work": [
        "call", "email", "send", "reply to", "follow up", "finish", "submit",
        "deadline", "due", "meeting", "report", "invoice", "client", "schedule",
        "deploy", "review", "fix", "inspector", "renew", "file the", "book a",
        "chase", "sign off", "ping",
    ],
    "ideas": [
        "idea", "what if", "wouldn't it be", "feature", "could we", "maybe the app",
        "the app should", "add a", "concept", "brainstorm", "it would be cool",
        "for the website", "for mypooldashboard", "dashboard could",
    ],
}

# Very light due-time sniffing. The LLM is the real extractor; this just flags
# that a time *looks* present so tests can exercise the reminder path.
_TIME_HINT = re.compile(
    r"\b(today|tomorrow|tonight|monday|tuesday|wednesday|thursday|friday|"
    r"saturday|sunday|next week|at \d{1,2}\s*(am|pm|:\d{2})|by \d{1,2})\b",
    re.IGNORECASE,
)


def classify(text):
    t = text.lower()
    scores = {b: 0 for b in SIGNALS}
    hits = {b: [] for b in SIGNALS}
    for bucket, words in SIGNALS.items():
        for w in words:
            if w in t:
                scores[bucket] += 1
                hits[bucket].append(w)

    best = max(scores, key=scores.get)
    top = scores[best]

    if top == 0:
        return {
            "bucket": "inbox",
            "confidence": 0.2,
            "reasons": ["no clear signal words matched"],
        }

    # Confidence rises with how decisively one bucket wins.
    ordered = sorted(scores.values(), reverse=True)
    margin = ordered[0] - (ordered[1] if len(ordered) > 1 else 0)
    confidence = min(0.95, 0.5 + 0.15 * top + 0.1 * margin)

    # A tie between buckets is a signal to be cautious.
    if margin == 0 and top > 0:
        return {
            "bucket": "inbox",
            "confidence": 0.35,
            "reasons": [f"tie between {', '.join(b for b in scores if scores[b] == top)}"],
        }

    reasons = [f"matched {best} words: {', '.join(hits[best])}"]
    if _TIME_HINT.search(text):
        reasons.append("a due time seems present")
    return {"bucket": best, "confidence": round(confidence, 2), "reasons": reasons}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True)
    args = ap.parse_args()
    print(json.dumps(classify(args.text), indent=2))


if __name__ == "__main__":
    main()

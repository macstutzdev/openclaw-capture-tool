#!/usr/bin/env python3
"""Rule-based fallback classifier.

Cindy (an LLM) is the *primary* classifier — she reads the message and uses the
heuristics in SKILL.md, which handles nuance far better than keyword matching.
This script exists for two narrower jobs:

  1. Offline testing — check sorting behaves sensibly on sample inputs without
     needing a model in the loop.
  2. A tie-breaker hint — if Cindy is unsure, she can run this for a second
     opinion and a rough confidence number.

Classification happens in two stages, kept separate for legibility:

  1. TYPE — is this a to-do, a shopping item, or an idea?
  2. DOMAIN — for a to-do or shopping item, is it work or personal? ("work"
     means any professional/job task, not limited to the pool business.)

Output: JSON {bucket, confidence, reasons}. Confidence is a rough 0–1 signal,
not a calibrated probability. Low confidence should push borderline items to
the inbox rather than a wrong bucket.

Usage:
    python3 classify.py --text "buy chlorine tablets"
"""

import argparse
import json
import re

# Stage 1 — what kind of thing is this? Kept deliberately small and legible —
# tune freely.
TYPE_SIGNALS = {
    "shopping": [
        "buy", "pick up", "pickup", "get some", "grocery", "groceries",
        "we need", "run out of", "out of", "restock", "order more",
        "shopping list", "order", "purchase",
    ],
    "todo": [
        "call", "email", "send", "reply to", "follow up", "finish", "submit",
        "deadline", "meeting", "schedule", "book", "chase",
        "sign off", "ping", "remind me", "renew", "file the", "review",
        "fix", "deploy",
    ],
    "ideas": [
        "idea", "what if", "wouldn't it be", "feature", "could we", "maybe the app",
        "the app should", "the app could", "add a", "concept", "brainstorm",
        "it would be cool", "for the website", "for mypooldashboard",
        "dashboard could",
    ],
}

# Stage 2 — work or personal? "Work" is any professional/job task, not
# limited to the pool business.
DOMAIN_SIGNALS = {
    "work": [
        "client", "invoice", "boss", "coworker", "colleague", "office",
        "meeting", "deadline", "project", "report", "inspector", "county",
        "permit", "business", "company", "quarterly", "standup",
        "presentation", "employer", "job", "shift", "conference call",
        "expense", "vendor", "work",
    ],
    "personal": [
        "mom", "dad", "family", "home", "kids", "dentist", "doctor", "vet",
        "haircut", "gym", "birthday", "anniversary", "spouse", "wife",
        "husband", "myself", "personal", "rent", "grocery", "groceries",
        "milk", "eggs", "bread", "coffee", "house", "car service", "school",
    ],
}

# Very light due-time sniffing. The LLM is the real extractor; this just flags
# that a time *looks* present so tests can exercise the reminder path.
_TIME_HINT = re.compile(
    r"\b(today|tomorrow|tonight|monday|tuesday|wednesday|thursday|friday|"
    r"saturday|sunday|next week|at \d{1,2}\s*(am|pm|:\d{2})|by \d{1,2})\b",
    re.IGNORECASE,
)


def _score(text, signals):
    scores = {k: 0 for k in signals}
    hits = {k: [] for k in signals}
    for key, words in signals.items():
        for w in words:
            if w in text:
                scores[key] += 1
                hits[key].append(w)
    return scores, hits


def classify(text):
    t = text.lower()

    type_scores, type_hits = _score(t, TYPE_SIGNALS)
    best_type = max(type_scores, key=type_scores.get)
    top = type_scores[best_type]

    if top == 0:
        return {
            "bucket": "inbox",
            "confidence": 0.2,
            "reasons": ["no clear signal words matched"],
        }

    ordered = sorted(type_scores.values(), reverse=True)
    margin = ordered[0] - (ordered[1] if len(ordered) > 1 else 0)

    if margin == 0:
        return {
            "bucket": "inbox",
            "confidence": 0.35,
            "reasons": [f"tie between {', '.join(k for k in type_scores if type_scores[k] == top)}"],
        }

    confidence = min(0.95, 0.5 + 0.15 * top + 0.1 * margin)
    reasons = [f"matched {best_type} words: {', '.join(type_hits[best_type])}"]
    if best_type == "todo" and _TIME_HINT.search(text):
        reasons.append("a due time seems present")

    if best_type == "ideas":
        return {"bucket": "ideas", "confidence": round(confidence, 2), "reasons": reasons}

    # Stage 2: which domain — work or personal? Ties (including no signal at
    # all) default to personal, since most everyday captures ("buy milk",
    # "call the plumber") carry no business cue and are personal by default.
    domain_scores, domain_hits = _score(t, DOMAIN_SIGNALS)
    if domain_scores["work"] > domain_scores["personal"]:
        domain = "work"
        reasons.append(f"matched work words: {', '.join(domain_hits['work'])}")
    else:
        domain = "personal"
        confidence = min(confidence, 0.7)  # default guess, so cap confidence
        if domain_scores["personal"] > 0:
            reasons.append(f"matched personal words: {', '.join(domain_hits['personal'])}")
        else:
            reasons.append("no domain words matched — defaulting to personal")

    bucket = f"{domain}_{best_type}"
    return {"bucket": bucket, "confidence": round(confidence, 2), "reasons": reasons}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True)
    args = ap.parse_args()
    print(json.dumps(classify(args.text), indent=2))


if __name__ == "__main__":
    main()

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

  1. TYPE — is this a to-do, a shopping item, an idea, or a bug report?
  2. DOMAIN — for a to-do or shopping item, is it work or personal, or does it
     mention the MyPoolDashboard project (in which case it goes to
     `mypooldash` instead, regardless of work/personal)? ("work" means any
     professional/job task, not limited to the pool business.)

Output: JSON {bucket, confidence, reasons} (mypooldash items also get a
"type": "idea"/"todo"/"bug"). Confidence is a rough 0–1 signal, not a
calibrated probability. Low confidence should push borderline items to the
inbox rather than a wrong bucket.

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
    "bug": [
        "bug", "broken", "crash", "crashes", "crashed", "glitch", "error",
        "doesn't work", "isn't working", "not working", "500", "throws",
        "stack trace",
    ],
}

# Any of these anywhere in the text means the message is about the
# MyPoolDashboard project specifically, so it should file to `mypooldash`
# rather than a generic work/personal bucket — regardless of which TYPE won.
PROJECT_SIGNALS = [
    "mypooldash", "mypooldashboard", "the dashboard", "the app", "the website",
    "the site",
]

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
    project_mentioned = any(sig in t for sig in PROJECT_SIGNALS)

    # mypooldash takes priority over every other bucket — ideas, work_todo,
    # personal_todo — for anything about the project. This is decided BEFORE
    # the generic tie-break/inbox logic below, so a message that scores as
    # both "todo" and "ideas" (or a bug with no other clear signal, or the
    # project name with no signal words at all) still lands in mypooldash
    # instead of falling through to inbox or a work/personal bucket. Shopping
    # is the one exception — mypooldash has no purchase schema, so a project
    # mention doesn't override a clear shopping signal.
    project_scores = {k: v for k, v in type_scores.items() if k != "shopping"}
    project_leader = max(project_scores, key=project_scores.get)
    project_leader_score = project_scores[project_leader]
    shopping_leads = type_scores["shopping"] > project_leader_score

    if (project_mentioned or type_scores["ideas"] > 0) and not shopping_leads:
        if project_leader_score == 0:
            # No specific type signal at all — just the project name. Default
            # to "idea" (the vaguest, lowest-commitment type) rather than
            # guessing it's an actionable to-do.
            project_leader = "ideas"
        kind = {"ideas": "idea", "todo": "todo", "bug": "bug"}[project_leader]
        hits = type_hits[project_leader]
        reasons = []
        if project_mentioned:
            reasons.append("mentions the MyPoolDashboard project — takes priority over ideas/work_todo")
        if hits:
            reasons.append(f"matched {project_leader} words: {', '.join(hits)}")
        else:
            reasons.append("no specific type words matched — defaulting to idea")
        if kind == "todo" and _TIME_HINT.search(text):
            reasons.append("a due time seems present")
        confidence = round(min(0.95, 0.55 + 0.15 * project_leader_score
                                + (0.15 if project_mentioned else 0)), 2)
        return {"bucket": "mypooldash", "type": kind,
                 "confidence": confidence, "reasons": reasons}

    # Not project-related (or shopping wins outright) — fall back to the
    # plain work/personal/shopping routing below. "ideas" can't appear here,
    # since any ideas signal is already handled above.
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
    if best_type == "bug":
        # A bug report with no project mention has nowhere specific to
        # live — treat it like any other actionable to-do.
        best_type = "todo"
    if best_type == "todo" and _TIME_HINT.search(text):
        reasons.append("a due time seems present")

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

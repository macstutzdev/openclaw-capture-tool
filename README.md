# capture-tool

An OpenClaw skill that turns your agent into a personal capture, review, and
follow-through loop. Send it things to remember over Telegram — tasks,
shopping, MyPoolDashboard ideas/bugs/todos — and it sorts each one into a
bucket, files it to a local markdown list, confirms what it did, sets one or
more judged Telegram reminders for time-sensitive tasks, and helps review or
clean up the system later. Everything
stays inside your OpenClaw workspace; nothing is pushed to outside apps.

## Install

From your OpenClaw agent, install straight from this repo:

```
openclaw skills install <this-repo-git-url>
```

(SKILL.md is at the repo root, as OpenClaw's git install expects.) Then run the
one-time setup:

```
python3 scripts/bootstrap.py
```

## What's here

- `SKILL.md` — how the agent uses the tool (buckets, classifying, filing,
  reminders, corrections, retrieval)
- `references/SCHEMAS.md` — the data shape of each bucket
- `examples/sample_inputs.txt` — test messages
- `WALKTHROUGH.md` — functional guide to the expanded capture/review workflow
- `scripts/` — Python (standard library only): bootstrap, capture, classify,
  correct, enrich, query, reconcile_crons, review, and shared lib

## The one boundary

The reminder script computes *which* reminders should exist and hands the agent
a plan; the agent creates the actual cron jobs and sends the Telegram pings with
its own tools. SKILL.md documents the three-step reconcile loop, including how
to handle vague times, exact confirmations, and multiple reminders.

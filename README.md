# capture-tool

An OpenClaw skill that turns your agent into a personal dictaphone. Send it
things to remember over Telegram — tasks, shopping, website ideas — and it
sorts each one into a bucket, files it to a local markdown list, confirms what
it did, and sets a Telegram reminder for any task with a due time. Everything
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
- `scripts/` — Python (standard library only): bootstrap, capture, classify,
  correct, reconcile_crons, query, and shared lib

## The one boundary

The reminder script computes *which* reminders should exist and hands the agent
a plan; the agent creates the actual cron jobs and sends the Telegram pings with
its own tools. SKILL.md documents the three-step reconcile loop.

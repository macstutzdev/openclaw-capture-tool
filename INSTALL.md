# Capture Tool — install note

Hand this whole folder to Cindy and tell her: **"Install this capture-tool
skill. Read SKILL.md, run the bootstrap, then let's test it."**

## What's in here

```
capture-tool/
├── SKILL.md                     ← how Cindy uses the tool (start here)
├── references/
│   └── SCHEMAS.md               ← the data shape of each bucket
├── examples/
│   └── sample_inputs.txt        ← test messages
└── scripts/                     ← Python (standard library only, no installs)
    ├── lib.py                   ← shared helpers
    ├── bootstrap.py             ← one-time setup
    ├── classify.py              ← fallback classifier / test aid
    ├── capture.py               ← file a classified item
    ├── correct.py               ← move / mark done
    ├── reconcile_crons.py       ← compute reminder schedule
    ├── query.py                 ← list / search / due-soon
    └── migrate_v2_buckets.py    ← one-time v1 → v2 bucket migration
```

## Install steps

1. Drop the `capture-tool/` folder wherever OpenClaw keeps its skills.
2. Cindy runs `python3 scripts/bootstrap.py` — this creates `capture/` and the
   six bucket files inside the workspace. (If this workspace already has the
   old four-bucket layout, run `python3 scripts/migrate_v2_buckets.py --commit`
   first instead — see SKILL.md.)
3. On your phone, turn on Telegram's voice-message transcription (Settings →
   your voice notes arrive to Cindy as text).
4. Send one test message per bucket and check the sorting, the confirmation
   reply, and (for a task with a time) the reminder.

## The one boundary to know

The reminder script works out *which* reminders should exist and hands Cindy a
plan. Cindy creates the actual cron jobs and sends the Telegram pings with her
own tools — the script can't reach those directly. SKILL.md spells out the
three-step reconcile loop she follows.

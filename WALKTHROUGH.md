# Capture Tool Walkthrough

This skill is now more than a dictaphone. It still captures Telegram notes into
local Markdown buckets, but it also helps Cormac review, prioritize, clean up,
and follow through.

## The mental model

There are three loops:

1. Capture the thing.
2. Review what matters.
3. Move each item to the right next state.

The agent makes judgement calls. The scripts keep the local files consistent.
OpenClaw handles the actual Telegram messages and scheduled jobs.

## Capture

Send a normal message such as:

```text
remind me to call the inspector tomorrow at 3pm
```

The agent decides the bucket, extracts the due time, chooses reminder lead time
from context, writes the item with `scripts/capture.py`, runs the reminder
reconcile loop, and confirms in compact form:

```text
Added to work to-do. Reminder: Fri, 7/3 @ 2:30pm.
```

For important or deadline-ish items, the agent can schedule multiple reminders:

```text
submit the permit renewal by Friday at 3pm
```

Possible confirmation:

```text
Added to work to-do. Reminders: Fri, 7/3 @ 9am; Fri, 7/3 @ 2pm.
```

If the time is vague, the agent proposes an exact time instead of quietly
guessing:

```text
I can set that for Fri, 7/3 @ 9am. Does that work?
```

## Review

Use review prompts when you want the system to help you work the list, not just
store it.

```text
plan my day
what's due this week?
show stale items
clear my inbox
give me a full review
```

The agent runs `scripts/review.py` with one of these modes:

```bash
python3 scripts/review.py --mode today
python3 scripts/review.py --mode week
python3 scripts/review.py --mode stale --stale-days 14
python3 scripts/review.py --mode inbox
python3 scripts/review.py --mode all
```

The brief groups items by practical attention: overdue, due today, due this
week, inbox, shopping, stale, blocked, waiting, and delegated.

## Lifecycle

Items no longer have to be only `open` or `done`.

Use plain language:

```text
mark the permit one waiting on Alex
snooze dentist until next Wednesday morning
that dashboard bug is blocked on repro steps
Jordan owns the invoice follow-up now
drop the old chlorine idea
```

The agent translates that into `scripts/correct.py` calls:

```bash
python3 scripts/correct.py --id wt-20260702-0001 --status waiting --waiting-on "Alex"
python3 scripts/correct.py --id pt-20260702-0002 --status snoozed --snooze-until 2026-07-08T09:00:00-04:00
python3 scripts/correct.py --id mpd-20260702-0003 --status blocked --blocked-reason "needs repro steps"
python3 scripts/correct.py --id wt-20260702-0004 --status delegated --delegated-to "Jordan"
python3 scripts/correct.py --id x-20260702-0005 --status dropped
```

When an item leaves `open`, reminder reconciliation cancels any live reminders.

## Enrichment

Use enrichment during cleanup, before filing an important item, or when a new
message sounds like something already captured.

```bash
python3 scripts/enrich.py --text "follow up with the inspector about permit renewal" --bucket work_todo
python3 scripts/enrich.py --id wt-20260702-0001
```

The script suggests:

- tags, such as `permit`, `finance`, `pool`, or `followup`
- urgency, such as `low`, `normal`, or `high`
- duplicate candidates, with ids and similarity scores

The agent uses these as hints. It can add tags or urgency with:

```bash
python3 scripts/correct.py --id wt-20260702-0001 --update --add-tag permit --urgency high
```

## Local storage

Records still live in `capture/*.md` as readable checklist lines with hidden
JSON comments. The visible line now includes useful lifecycle details:

```markdown
- [ ] Submit permit renewal (due Fri 03 Jul, 3:00 PM, high, waiting on Alex)  [permit]
```

`capture/metadata.json` tracks counters and scheduled reminder jobs. It now
supports multiple reminders per task with ids like:

```text
wt-20260702-0001::r1
wt-20260702-0001::r2
```

## Smoke test

Use a throwaway root:

```bash
python3 scripts/bootstrap.py --root /tmp/capture-demo
python3 scripts/capture.py --root /tmp/capture-demo --bucket work_todo \
  --text "Submit permit renewal" \
  --due 2099-07-03T15:00:00-04:00 \
  --reminder-at 2099-07-03T09:00:00-04:00 \
  --reminder-at 2099-07-03T14:00:00-04:00 \
  --priority high --tags permit,followup
python3 scripts/review.py --root /tmp/capture-demo --mode all
python3 scripts/enrich.py --root /tmp/capture-demo \
  --text "follow up with the inspector about permit renewal" --bucket work_todo
python3 scripts/reconcile_crons.py --root /tmp/capture-demo
```

The expected result is a review brief, duplicate/enrichment suggestions, and a
reminder plan with two jobs.

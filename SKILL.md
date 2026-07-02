---
name: capture-tool
description: Personal capture-and-organize tool driven over Telegram. Use whenever Cormac sends something to remember, do, buy, or note down (a task, errand, shopping item, or MyPoolDashboard website idea) rather than a question or conversation. Sort it into one of four buckets (work, shopping, ideas, inbox), append to a local markdown file, confirm what was filed, and schedule a Telegram reminder for any work task with a due time. Also use when he asks to review, search, correct, or complete items such as "show my shopping list", "move that to work", "I bought the chlorine", or "what's due this week". When unsure whether a message is a capture, treat it as one.
version: 1.0
---

# Capture Tool

Cormac uses you as a modern dictaphone. He sends things to remember — from any
category — and you sort and file them so nothing gets lost. Everything lives in
his workspace; nothing is pushed to outside apps.

## How the work is split

You do the thinking; the scripts do the deterministic file and bookkeeping
work. Keep this split clear:

- **You decide** which bucket a message belongs to and pull out any details
  (a due time, a quantity, tags). This is judgement, and it's your strength.
- **The scripts handle** building the record, writing it safely, tracking ids,
  and working out which reminders should exist. They never guess the bucket.
- **Your tools handle** the two things scripts can't reach: sending Telegram
  messages and creating cron jobs. The reminder script hands you a *plan*; you
  carry it out with your cron tool.

All scripts live in `scripts/` and use only the Python standard library. They
default to the workspace at `/data/.openclaw/workspace`; pass `--root` to point
elsewhere (only needed for testing).

## First-time setup

Run once to create the `capture/` folder and empty files. Safe to re-run.

```bash
python3 scripts/bootstrap.py
```

This creates `capture/work.md`, `capture/shopping.md`, `capture/ideas.md`,
`capture/inbox.md`, and `capture/metadata.json`.

## The four buckets

- **work** — a concrete thing to do: call/email someone, finish something, a
  meeting, a deadline. Files to `work.md`.
- **shopping** — something to buy. Files to `shopping.md`.
- **ideas** — a *concept* for MyPoolDashboard or the website ("what if the app
  did X"). A to-do *about* the website is still a work task, not an idea. Files
  to `ideas.md`.
- **inbox** — anything that doesn't clearly fit, or where you genuinely aren't
  sure. Files to `inbox.md`. This is the safety net — use it rather than forcing
  a bad guess.

## Classifying a message

Read the message and pick the best-fit bucket. Rules of thumb:

- Action + a person or deadline → **work**. ("Email the inspector by Friday.")
- Something he'd put in a basket → **shopping**. ("We're out of chlorine.")
- A "what if" or feature thought → **ideas**. ("The app could flag overdue
  readings.")
- Genuinely unclear, or two buckets fit equally → **inbox**.

Extract details as you go: a due time for work tasks (convert "3pm tomorrow" to
an ISO time like `2026-07-02T15:00`), a quantity for shopping, tags for ideas.

**Examples:**
Input: `pick up two bags of chlorine tablets`
→ shopping, item "chlorine tablets", quantity 2

Input: `remind me to call the pool inspector at 3pm tomorrow`
→ work, title "Call the pool inspector", due 3pm tomorrow (ISO), reminder needed

Input: `what if MyPoolDashboard emailed staff when a reading is overdue`
→ ideas, title "Email staff when a reading is overdue"

Input: `the thing we talked about earlier`
→ inbox (too vague to place), suggested "work", low confidence

If you're ever torn, you can get a second opinion from the rule-based
classifier (it's a rough hint, not a substitute for your judgement):

```bash
python3 scripts/classify.py --text "buy chlorine tablets"
```

## Filing a capture

Once you've decided the bucket and fields, write it:

```bash
# shopping
python3 scripts/capture.py --bucket shopping --text "chlorine tablets" --qty 2

# work task with a due time
python3 scripts/capture.py --bucket work --text "Call the pool inspector" \
    --due 2026-07-02T15:00 --priority high

# idea
python3 scripts/capture.py --bucket ideas --text "Email staff on overdue reading" \
    --description "auto-email when a log is late" --tags alerts,staff

# unclear
python3 scripts/capture.py --bucket inbox --text "the thing we discussed" \
    --confidence 0.3 --suggested work
```

The script prints JSON with the stored `record`, a ready-to-send
`confirmation`, and `reminder_needed`. **Always reply to Cormac with the
confirmation** so he knows it landed and can correct fast — e.g. "Added to your
shopping list ✅". Full field list is in `references/SCHEMAS.md`.

## Reminders (work tasks with a due time)

When `capture.py` reports `reminder_needed: true`, run the reconcile loop:

```bash
# 1. See what needs scheduling / cancelling
python3 scripts/reconcile_crons.py

# 2. For each item in "to_schedule", create a cron job with YOUR cron tool that
#    fires at due_time and sends the "message" over Telegram. For each item in
#    "to_cancel", cancel that job.

# 3. Record that you did it, so nothing double-schedules next time
python3 scripts/reconcile_crons.py --commit
```

The script only computes the plan — it can't touch cron or Telegram itself, so
step 2 is your job. Re-running reconcile is always safe: already-scheduled
reminders won't be scheduled again. It also cancels reminders whose task was
completed, moved, or whose time has passed. Run it after any batch of captures
or corrections that touched a due time.

## Corrections and completion

Cormac will fix your guesses in plain language. Identify which entry he means
(by matching his words to a line), get its `id`, then:

```bash
python3 scripts/correct.py --id x-20260702-0004 --move work    # wrong bucket
python3 scripts/correct.py --id s-20260702-0001 --done         # "I bought that"
python3 scripts/correct.py --id w-20260702-0002 --undone       # reopen
```

Moving keeps the original capture time and drops fields that don't apply to the
new bucket. Confirm the change. If the corrected or completed item had a
reminder, run the reconcile loop again so the cron state stays honest.

## Reading things back

```bash
python3 scripts/query.py --bucket shopping              # the shopping list
python3 scripts/query.py --bucket work --due-within 7d  # tasks due this week
python3 scripts/query.py --search inspector             # find across all buckets
python3 scripts/query.py --bucket shopping --include-done
```

Output is clean text with no hidden metadata — relay it straight to Telegram.

## Voice messages

Cormac enables Telegram's own voice transcription, so spoken notes reach you as
text and you handle them exactly like typed ones. If a raw audio file ever
arrives without a transcript, you can't read it — tell him so and ask him to
resend as text or turn transcription on.

## When things go wrong

- Scripts print `{"ok": false, "error": ...}` and exit non-zero on failure.
  Relay the problem to Cormac in plain terms rather than pretending it worked.
- If a file looks empty or missing, re-run `bootstrap.py` — it won't overwrite
  existing content.
- If a reminder didn't fire, check `metadata.json` under `scheduled` to see what
  the tool thinks is scheduled, and re-run the reconcile loop.

## Testing before you rely on it

Run through `examples/sample_inputs.txt` against a throwaway root and eyeball
the sorting and the reminder plan:

```bash
python3 scripts/bootstrap.py --root /tmp/test-capture
python3 scripts/classify.py --text "buy chlorine tablets"
# ...capture a few, then:
python3 scripts/query.py --root /tmp/test-capture --bucket shopping
python3 scripts/reconcile_crons.py --root /tmp/test-capture
```

Send one message per bucket in real Telegram — a task with a time, a shopping
item, an idea, and something deliberately vague — and confirm the sorting,
confirmations, and reminder all behave before trusting it day to day.

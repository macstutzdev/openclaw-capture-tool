---
name: capture-tool
description: Personal capture-and-organize tool driven over Telegram. Use whenever Cormac sends something to remember, do, buy, or note down (a task, errand, shopping item, or something about his MyPoolDashboard project) rather than a question or conversation. Sort it into one of six buckets — work to-do, personal to-do, work shopping, personal shopping, mypooldash (ideas/to-dos/bugs for the project), inbox — append to a local markdown file, confirm what was filed, and schedule a Telegram reminder for any to-do item with a due time (work, personal, or mypooldash). Also use when he asks to review, search, correct, or complete items such as "show my shopping list", "move that to work", "I bought the chlorine", or "what's due this week". When unsure whether a message is a capture, treat it as one.
version: 3.0
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

This creates `capture/work_todo.md`, `capture/personal_todo.md`,
`capture/work_shopping.md`, `capture/personal_shopping.md`,
`capture/mypooldash.md`, `capture/inbox.md`, and `capture/metadata.json`.

If this workspace was set up with the old four-bucket layout (`work.md`,
`shopping.md`), run the one-time migration first instead — see "Migrating
from the old layout" below. If it has an older `ideas.md` instead of
`mypooldash.md`, see "Migrating from the v2 layout" further down.

## The six buckets

- **work_todo** — a concrete thing to do *for work*: any professional/job
  task, not just the pool business — call/email someone, finish something,
  a meeting, a deadline, an invoice. Files to `work_todo.md`.
- **personal_todo** — a concrete thing to do that *isn't* work: appointments,
  family, home admin, personal errands. Files to `personal_todo.md`.
- **work_shopping** — something to buy for work. Files to `work_shopping.md`.
- **personal_shopping** — something to buy for himself or the household.
  Files to `personal_shopping.md`.
- **mypooldash** — anything about the MyPoolDashboard project: a feature
  *idea* ("what if the app did X"), a *to-do* for the project (a dev task, a
  deploy, a piece of copy to write), or a *bug* report. Files to
  `mypooldash.md` with a `type` of `idea` / `todo` / `bug`. A to-do here still
  gets a reminder if it has a due time, exactly like work_todo/personal_todo.
- **inbox** — anything that doesn't clearly fit, or where you genuinely aren't
  sure. Files to `inbox.md`. This is the safety net — use it rather than forcing
  a bad guess.

## Classifying a message

Read the message and pick the best-fit bucket. Rules of thumb:

- Action + it's job-related (a client, a coworker, an invoice, a work
  deadline, an inspection) → **work_todo**. ("Email the inspector by Friday.")
- Action that isn't job-related (an appointment, family, home) →
  **personal_todo**. ("Book the dentist for Tuesday.")
- Something he'd buy for work → **work_shopping**. ("Order more business
  cards.")
- Something he'd put in a basket for himself or the house →
  **personal_shopping**. ("We're out of chlorine.")
- Anything about the MyPoolDashboard project → **mypooldash**, and pick a
  `type`:
  - A "what if" or feature thought → `type: idea`. ("The app could flag
    overdue readings.")
  - A concrete task for the project, with or without a due time → `type:
    todo`. ("Fix the login bug by Friday", "write the onboarding copy for the
    dashboard.") This is still MyPoolDashboard work, so it goes here rather
    than work_todo even though it's job-related.
  - Something broken → `type: bug`. ("The login form 500s on mobile
    Safari.")
- Genuinely unclear, or two buckets fit equally → **inbox**.

"Work" means any professional/job task — it isn't limited to the pool
business, so treat other job-related asks the same way. **mypooldash takes
priority over every other bucket for anything project-related** — if a
message is about MyPoolDashboard, it goes to mypooldash instead of work_todo
even though it's job-related, and instead of the inbox even if you're unsure
which `type` fits (default to `idea` in that case, the safest guess, rather
than parking it in the inbox).

Extract details as you go: a due time for to-do items (convert "3pm tomorrow"
to an ISO time like `2026-07-02T15:00`) — this applies to mypooldash `todo`
entries too — a quantity and optional subcategory for shopping items (e.g.
`pool`, `office`), tags for mypooldash entries.

**Examples:**
Input: `pick up two bags of chlorine tablets`
→ personal_shopping, item "chlorine tablets", quantity 2

Input: `order more business cards for the shop`
→ work_shopping, item "business cards"

Input: `remind me to call the pool inspector at 3pm tomorrow`
→ work_todo, title "Call the pool inspector", due 3pm tomorrow (ISO), reminder needed

Input: `book the dentist for next tuesday morning`
→ personal_todo, title "Book the dentist", due next Tuesday (ISO), reminder needed

Input: `what if MyPoolDashboard emailed staff when a reading is overdue`
→ mypooldash, type "idea", title "Email staff when a reading is overdue"

Input: `the login form on mypooldashboard 500s on mobile safari`
→ mypooldash, type "bug", title "Login form 500s on mobile Safari"

Input: `fix the login bug on the dashboard by friday`
→ mypooldash, type "todo", title "Fix the login bug", due Friday (ISO), reminder needed

Input: `the thing we talked about earlier`
→ inbox (too vague to place), suggested "work_todo", low confidence

If you're ever torn, you can get a second opinion from the rule-based
classifier (it's a rough hint, not a substitute for your judgement):

```bash
python3 scripts/classify.py --text "buy chlorine tablets"
```

## Filing a capture

Once you've decided the bucket and fields, write it:

```bash
# personal shopping
python3 scripts/capture.py --bucket personal_shopping --text "chlorine tablets" --qty 2

# work shopping
python3 scripts/capture.py --bucket work_shopping --text "business cards" --qty 500

# work to-do with a due time
python3 scripts/capture.py --bucket work_todo --text "Call the pool inspector" \
    --due 2026-07-02T15:00 --priority high

# personal to-do with a due time
python3 scripts/capture.py --bucket personal_todo --text "Book the dentist" \
    --due 2026-07-08T09:00

# mypooldash idea
python3 scripts/capture.py --bucket mypooldash --type idea \
    --text "Email staff on overdue reading" \
    --description "auto-email when a log is late" --tags alerts,staff

# mypooldash bug
python3 scripts/capture.py --bucket mypooldash --type bug \
    --text "Login form 500s on mobile Safari"

# mypooldash to-do with a due time
python3 scripts/capture.py --bucket mypooldash --type todo \
    --text "Fix the login bug" --due 2026-07-04T17:00 --priority high

# unclear
python3 scripts/capture.py --bucket inbox --text "the thing we discussed" \
    --confidence 0.3 --suggested work_todo
```

The script prints JSON with the stored `record`, a ready-to-send
`confirmation`, and `reminder_needed`. **Always reply to Cormac with the
confirmation** so he knows it landed and can correct fast — e.g. "Added to your
personal shopping list ✅". Full field list is in `references/SCHEMAS.md`.

## Reminders (to-do items with a due time)

When `capture.py` reports `reminder_needed: true`, run the reconcile loop.
This applies to `work_todo` and `personal_todo` items, and to `mypooldash`
entries filed with `type: todo` — any open to-do with a due time earns a
reminder, regardless of which bucket it's in.

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
python3 scripts/correct.py --id x-20260702-0004 --move work_todo    # wrong bucket
python3 scripts/correct.py --id ps-20260702-0001 --done             # "I bought that"
python3 scripts/correct.py --id wt-20260702-0002 --undone           # reopen
```

Moving keeps the original capture time and drops fields that don't apply to the
new bucket. Confirm the change. If the corrected or completed item had a
reminder, run the reconcile loop again so the cron state stays honest.

## Reading things back

```bash
python3 scripts/query.py --bucket personal_shopping           # the personal shopping list
python3 scripts/query.py --bucket work_todo --due-within 7d   # work tasks due this week
python3 scripts/query.py --search inspector                    # find across all buckets
python3 scripts/query.py --bucket personal_shopping --include-done
```

Output is clean text with no hidden metadata — relay it straight to Telegram.

## Voice messages

Cormac enables Telegram's own voice transcription, so spoken notes reach you as
text and you handle them exactly like typed ones. If a raw audio file ever
arrives without a transcript, you can't read it — tell him so and ask him to
resend as text or turn transcription on.

## Migrating from the old layout

The tool originally had four buckets (`work`, `shopping`, `ideas`, `inbox`).
If this workspace still has `capture/work.md` or `capture/shopping.md`, run
the migration once before doing anything else:

```bash
python3 scripts/migrate_v2_buckets.py            # see the plan (dry run)
python3 scripts/migrate_v2_buckets.py --commit   # actually migrate
```

It renames `work.md` → `work_todo.md` and `shopping.md` →
`personal_shopping.md`, remapping ids and `metadata.json` (including live
`scheduled` reminders) to match, and creates empty `personal_todo.md` /
`work_shopping.md`. The old files are backed up alongside as `*.v1.bak`, not
deleted. `ideas.md` and `inbox.md` are untouched. It's a no-op if there's
nothing to migrate. See `references/SCHEMAS.md` for details.

## Migrating from the v2 layout

If this workspace still has `capture/ideas.md` instead of
`capture/mypooldash.md`, run the v3 migration once:

```bash
python3 scripts/migrate_v3_mypooldash.py            # see the plan (dry run)
python3 scripts/migrate_v3_mypooldash.py --commit   # actually migrate
```

It renames `ideas.md` → `mypooldash.md`, remapping ids (`i-` → `mpd-`) and
`metadata.json` counters, tagging every migrated record `"type": "idea"`. The
old file is backed up as `ideas.md.v2.bak`, not deleted. It's a no-op if
there's nothing to migrate.

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
python3 scripts/query.py --root /tmp/test-capture --bucket personal_shopping
python3 scripts/reconcile_crons.py --root /tmp/test-capture
```

Send one message per bucket in real Telegram — a work task, a personal task,
a work shopping item, a personal shopping item, a MyPoolDashboard idea/todo/bug,
and something deliberately vague — and confirm the sorting, confirmations, and
reminders all behave before trusting it day to day.

---
name: capture-tool
description: Personal capture, review, and follow-through tool driven over Telegram. Use whenever Cormac sends something to remember, do, buy, review, clean up, defer, delegate, or note down (a task, errand, shopping item, or something about his MyPoolDashboard project) rather than a question or conversation. Sort captures into one of six buckets — work to-do, personal to-do, work shopping, personal shopping, mypooldash (ideas/to-dos/bugs for the project), inbox — append to a local markdown file, confirm what was filed, schedule judged Telegram reminders for time-sensitive to-dos, enrich items with useful tags/urgency/duplicate checks, and support reviews such as "plan my day", "what's stale", "clear my inbox", "mark that waiting on Alex", or "what's due this week". When unsure whether a message is a capture or cleanup command, treat it as one.
version: 4.0
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
  working out which reminders should exist, generating review briefs, and
  suggesting enrichment. They never guess the bucket.
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
to an ISO time like `2026-07-02T15:00-04:00`) — this applies to mypooldash
`todo` entries too — plus one or more reminder times, a quantity and optional
subcategory for shopping items (e.g. `pool`, `office`), and tags for mypooldash
entries.

## Time-sensitive communication rules

Use agentic judgement for reminders, but make the final schedule explicit.
Cormac prefers exact, compact confirmations and will usually avoid vague time
phrases. When time is fuzzy, do not silently guess and move on.

- **Timezone** — interpret natural-language times in `America/New_York` unless
  Cormac explicitly says otherwise. Store ISO times with an offset when you can
  (for example `2026-07-03T15:00:00-04:00`).
- **Due time vs reminder time** — `due_time` is when the task is due. Each
  `reminder_times` entry is when Telegram should ping him. These can be the
  same moment, but they do not have to be.
- **Lead time judgement** — choose reminder lead time based on context. A quick
  call might need a same-day reminder; an appointment might need the evening
  before plus travel-time warning; a hard deadline may deserve a morning-of and
  a final reminder. If you are not confident, ask before filing.
- **Vague phrases** — for "tomorrow morning", "tonight", "this afternoon",
  "by Friday", "next week", or similar, use any available context to propose an
  exact due/reminder time: "I can set that for Fri, 7/3 @ 9am. Does that work?"
  If context is too thin, ask for the time.
- **No time supplied** — if Cormac asks for a reminder but gives no usable time,
  propose a reasonable exact time from context. If there is no reasonable guess,
  ask for a time before scheduling. You may still file the item only if you make
  clear that no reminder has been scheduled yet.
- **Multiple reminders** — schedule more than one reminder when the task seems
  high priority, deadline-ish, appointment-like, travel-sensitive, or easy to
  miss. If multiple reminders feel useful but not obvious, ask.
- **Past or impossible times** — never schedule a reminder in the past. Ask for
  a corrected time or propose the next plausible future time.
- **Confirmation format** — after filing and scheduling, reply compactly using
  dates like `Fri, 7/3 @ 3pm`. For multiple reminders, list each one briefly:
  "Added to work to-do. Reminders: Thu, 7/2 @ 5pm; Fri, 7/3 @ 9am."
- **Failure handling** — if capture succeeds but cron scheduling fails or the
  created job doesn't pass the delivery contract (see "Mandatory Telegram
  reminder cron contract" below), say so plainly: the item was saved, but the
  reminder was not scheduled. Do not run `reconcile_crons.py --commit` until the
  cron jobs were actually created and validated.

**Examples:**
Input: `pick up two bags of chlorine tablets`
→ personal_shopping, item "chlorine tablets", quantity 2

Input: `order more business cards for the shop`
→ work_shopping, item "business cards"

Input: `remind me to call the pool inspector at 3pm tomorrow`
→ work_todo, title "Call the pool inspector", due 3pm tomorrow (ISO), choose a reminder time from context

Input: `book the dentist for next tuesday morning`
→ propose an exact time first, e.g. "I can set that for Tue, 7/7 @ 9am. Does that work?"

Input: `what if MyPoolDashboard emailed staff when a reading is overdue`
→ mypooldash, type "idea", title "Email staff when a reading is overdue"

Input: `the login form on mypooldashboard 500s on mobile safari`
→ mypooldash, type "bug", title "Login form 500s on mobile Safari"

Input: `fix the login bug on the dashboard by friday`
→ mypooldash, type "todo", title "Fix the login bug", due Friday (ISO), likely schedule one or more reminders before the deadline

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
    --due 2026-07-02T15:00:00-04:00 --reminder-at 2026-07-02T14:30:00-04:00 \
    --priority high

# personal to-do with a due time
python3 scripts/capture.py --bucket personal_todo --text "Book the dentist" \
    --due 2026-07-08T09:00:00-04:00 --reminder-at 2026-07-07T18:00:00-04:00

# mypooldash idea
python3 scripts/capture.py --bucket mypooldash --type idea \
    --text "Email staff on overdue reading" \
    --description "auto-email when a log is late" --tags alerts,staff

# mypooldash bug
python3 scripts/capture.py --bucket mypooldash --type bug \
    --text "Login form 500s on mobile Safari"

# mypooldash to-do with a due time
python3 scripts/capture.py --bucket mypooldash --type todo \
    --text "Fix the login bug" --due 2026-07-04T17:00:00-04:00 \
    --reminder-at 2026-07-04T09:00:00-04:00 \
    --reminder-at 2026-07-04T16:00:00-04:00 --priority high

# unclear
python3 scripts/capture.py --bucket inbox --text "the thing we discussed" \
    --confidence 0.3 --suggested work_todo
```

The script prints JSON with the stored `record`, a ready-to-send
`confirmation`, `reminder_needed`, and any `warnings`. Due and reminder times
are normalized to carry an explicit offset; if you pass a naive time (no
timezone), it's interpreted as `America/New_York` and a warning says so — glance
at `warnings` and correct the time if that assumption was wrong. **Always reply
to Cormac** so he knows it landed and can correct fast. If no reminder was
needed, the script confirmation is enough. If reminders were scheduled, include the exact reminder time(s) in
the compact format above, e.g. "Added to work to-do. Reminder: Fri, 7/3 @ 3pm."
Full field list is in `references/SCHEMAS.md`.

## Reminders (to-do items with a due time)

When `capture.py` reports `reminder_needed: true`, run the reconcile loop.
This applies to `work_todo` and `personal_todo` items, and to `mypooldash`
entries filed with `type: todo` — any open to-do with `reminder_times` earns
one or more reminders, regardless of which bucket it's in. Older records with a
`due_time` but no `reminder_times` fall back to one reminder at `due_time`.

**Reminder delivery is too important to improvise.** A cron job that merely
fires does *not* send anything to Telegram — it must carry an explicit
`delivery` block (see the contract below). This has silently failed before, so
the scripts now hand you the exact cron payload to create; do not hand-build it.

```bash
# 1. See what needs scheduling / cancelling. Each "to_schedule" item now
#    includes a ready-to-use "cron_spec" — the exact, delivering cron job.
python3 scripts/reconcile_crons.py

# 2. For each item in "to_schedule", create a cron job from its "cron_spec"
#    VERBATIM with your cron tool. (Equivalently, regenerate it with
#    reminder_cron_spec.py.) For each item in "to_cancel", cancel that job by
#    its cron id (stored earlier in metadata as cron_note).

# 3. VALIDATE each created job (see below), then record what you did — passing
#    the cron job id you got back so cancellation/debugging works later.
python3 scripts/reconcile_crons.py --commit \
    --cron-note wt-20260702-0001=<cron-job-id>
```

`--commit` refuses to record any `to_schedule` reminder unless you pass a
`--cron-note <id>=<cron-job-id>` for it — this stops the tool from believing a
reminder is live when the cron job was never really created. `--force` bypasses
the check for manual recovery only.

Re-running reconcile is always safe: already-scheduled reminders won't be
scheduled again. It also cancels reminders whose task was completed, moved, left
`open` status, removed from `reminder_times`, or whose reminder time has passed.
Run it after any batch of captures or corrections that touched a due time,
reminder time, or lifecycle state.

### Mandatory Telegram reminder cron contract

Every reminder cron job that must notify Cormac MUST use explicit announce
delivery. The `cron_spec` from `reconcile_crons.py` (and
`reminder_cron_spec.py`) already satisfies this — create it unchanged.

Required fields:

- `sessionTarget: "isolated"`
- `wakeMode: "now"`
- `payload.kind: "agentTurn"`
- `payload.lightContext: true`
- `payload.timeoutSeconds: 60`
- `payload.message` — an **"Output exactly this reminder text and nothing
  else:"** instruction wrapping the reminder body. Never phrase it as "send
  Cormac…"; the delivery layer does the sending, and telling the child agent to
  "send" makes it reach for messaging tools and narrate delivery failures.
- `delivery.mode: "announce"`
- `delivery.channel: "telegram"`
- `delivery.to: "8688841600"`
- `delivery.bestEffort: false`

Do NOT use, for a reminder meant to reach Cormac:

- `sessionTarget: "main"`
- `payload.kind: "systemEvent"`
- a cron job with no `delivery` block
- a reminder that relies only on the cron run `summary`

Canonical shape (this is exactly what the scripts emit):

```json
{
  "name": "Capture reminder: wt-20260702-0001",
  "schedule": { "kind": "at", "at": "2026-07-04T13:00:00.000Z" },
  "deleteAfterRun": true,
  "sessionTarget": "isolated",
  "wakeMode": "now",
  "payload": {
    "kind": "agentTurn",
    "message": "Output exactly this reminder text and nothing else:\n\n⏰ Reminder: Call the pool inspector",
    "timeoutSeconds": 60,
    "lightContext": true
  },
  "delivery": {
    "mode": "announce",
    "channel": "telegram",
    "to": "8688841600",
    "bestEffort": false
  }
}
```

### Validate before you commit

After creating each reminder cron job, inspect the job you got back and confirm:

- `sessionTarget == "isolated"`
- `payload.kind == "agentTurn"`
- `delivery.mode == "announce"`
- `delivery.channel == "telegram"`
- `delivery.to == "8688841600"`

If validation fails: do **not** run `reconcile_crons.py --commit`; delete or
replace the malformed job; and tell Cormac the item was captured but the
reminder was not safely scheduled. **Never commit reminder metadata until the
actual cron job has been validated for Telegram delivery.**

### `status: ok` is not proof of delivery

A cron run reporting `status: ok` only means the task ran. It does **not** mean
Telegram delivery happened. Always inspect `deliveryStatus`:

- `deliveryStatus: "delivered"` → the reminder actually reached Cormac. Good.
- `deliveryStatus: "not-requested"` → the job had no delivery block. **Treat as
  a failed reminder.**
- `deliveryStatus: "failed"` or `null` → also a failure.

A successful direct `message(action=send)` test proves only that Telegram
credentials and routing work. It does **not** prove cron reminders are
configured correctly — those need a separate cron-run delivery test.

### Reminder recovery

If a reminder did not arrive:

1. Check the cron run log (e.g. `/data/.openclaw/cron/runs/<job-id>.jsonl`).
2. If `deliveryStatus` is `not-requested` (or `failed`/`null`), the cron job was
   malformed — it fired but delivered nothing.
3. Recreate the reminder from a fresh `cron_spec` (explicit announce delivery).
4. `python3 scripts/reconcile_crons.py --commit --cron-note <id>=<new-job-id>`.
5. If the old job still exists, cancel it.
6. Tell Cormac whether the original item was saved and whether a replacement
   reminder was scheduled.

## Review and planning loop

Use review mode whenever Cormac asks to plan, triage, clean up, see what is due,
clear stale items, or get a daily/weekly overview. This is the productivity
counterpart to capture: do not just list everything; help him decide what needs
attention next.

```bash
python3 scripts/review.py --mode today
python3 scripts/review.py --mode week
python3 scripts/review.py --mode stale --stale-days 14
python3 scripts/review.py --mode inbox
python3 scripts/review.py --mode all
```

Relay the brief in a compact way and add useful judgement:

- For `today`, call out overdue, due today, blocked, waiting, and inbox items.
- For `week`, call out the next seven days, delegated/waiting items, and stale
  open work that should be handled or dropped.
- For `stale`, ask whether old open items should be completed, snoozed,
  delegated, moved, or dropped.
- For `inbox`, classify each inbox item if possible, then move it or ask a
  focused clarification.

If a review reveals time-sensitive work without reminders, propose exact
reminder times using the time-sensitive communication rules above.

## Lifecycle management

Items now have richer states than just `open` and `done`. Use these states when
Cormac gives lifecycle language, or when a review makes the next state obvious:

- `open` — active and owned by Cormac.
- `done` — completed, bought, fixed, shipped, or no longer needs action.
- `snoozed` — intentionally hidden until a future time.
- `waiting` — blocked on someone or something external.
- `blocked` — cannot move until a specific obstacle is resolved.
- `delegated` — someone else owns the next action.
- `dropped` — intentionally abandoned; not the same as completed.

```bash
python3 scripts/correct.py --id wt-20260702-0001 --status waiting --waiting-on "Alex"
python3 scripts/correct.py --id pt-20260702-0002 --status snoozed --snooze-until 2026-07-08T09:00:00-04:00
python3 scripts/correct.py --id mpd-20260702-0003 --status blocked --blocked-reason "needs repro steps"
python3 scripts/correct.py --id wt-20260702-0004 --status delegated --delegated-to "Jordan"
python3 scripts/correct.py --id x-20260702-0005 --status dropped
python3 scripts/correct.py --id wt-20260702-0006 --update --add-tag permit --priority high
```

When an item leaves `open`, run the reconcile loop if it had reminders so live
cron jobs are cancelled. Confirm lifecycle changes plainly: "Marked waiting on
Alex" or "Snoozed until Wed, 7/8 @ 9am."

## Enrichment and cleanup

Use enrichment when a capture looks similar to an existing item, when a review
is noisy, when Cormac asks to clean up the system, or before filing something
important where tags/urgency would help future retrieval.

```bash
python3 scripts/enrich.py --text "follow up with the inspector about permit renewal" --bucket work_todo
python3 scripts/enrich.py --id wt-20260702-0001
```

The script prints suggested tags, suggested urgency, and duplicate candidates.
Treat this as a hint, not a command. If there is a strong duplicate candidate,
ask before creating another item or update the existing item when Cormac's
intent is clear. If tags or urgency are useful, apply them with `correct.py
--update`.

Cleanup rules:

- Prefer merging or updating obvious duplicates over adding clutter.
- Add a small number of useful tags; do not over-tag routine items.
- Use `dropped` for abandoned work so completion history stays honest.
- Leave ambiguous inbox items in `inbox` only after asking or proposing a
  focused classification.

## Corrections and completion

Cormac will fix your guesses in plain language. Identify which entry he means
(by matching his words to a line), get its `id`, then:

```bash
python3 scripts/correct.py --id x-20260702-0004 --move work_todo    # wrong bucket
python3 scripts/correct.py --id ps-20260702-0001 --done             # "I bought that"
python3 scripts/correct.py --id wt-20260702-0002 --undone           # reopen
python3 scripts/correct.py --id wt-20260702-0003 --status waiting --waiting-on "Alex"
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
python3 scripts/query.py --bucket work_todo --status waiting
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
  the tool thinks is scheduled (the `cron_note` there is the cron job id), check
  that job's run log for `deliveryStatus`, and follow "Reminder recovery" above.
  Remember: `status: ok` with `deliveryStatus: not-requested` means the reminder
  silently failed to send.

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

For reminders specifically, do a real cron-run delivery test — schedule one a
minute or two out from a `cron_spec`, let it fire, and confirm the run log shows
`deliveryStatus: delivered` and that the Telegram message actually arrived. A
direct `message(action=send)` test is not a substitute: it only proves routing
works, not that the cron job is shaped correctly.

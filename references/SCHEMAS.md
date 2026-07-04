# Data schemas

Every captured item is stored as a human-readable line in its bucket's markdown
file, with the full record as compact JSON inside a trailing HTML comment
(`<!-- ... -->`). The comment is invisible when the markdown is rendered, so the
lists stay clean for Cormac while remaining exactly parseable for the scripts.

Do not hand-edit the JSON comments. Use `capture.py` and `correct.py`, which
keep the visible line and the record in sync and manage ids.

## Shared fields (all buckets)

| field        | type   | notes                                                                    |
|--------------|--------|---------------------------------------------------------------------------|
| `bucket`     | string | one of `work_todo`, `personal_todo`, `work_shopping`, `personal_shopping`, `mypooldash`, `inbox` |
| `id`         | string | e.g. `wt-20260702-0001`; prefix marks the bucket (`wt`/`pt`/`ws`/`ps`/`mpd`/`x`) |
| `created_at` | string | ISO 8601, set at capture; preserved across a move                       |
| `status`     | string | `open` / `done` / `snoozed` / `waiting` / `blocked` / `delegated` / `dropped`; bucket records default to `open` |
| `tags`       | array  | optional lightweight labels inferred or chosen by the agent             |
| `context`    | string | optional free-form context such as `phone`, `errand`, `computer`, `office` |

## Lifecycle fields

These optional fields can appear on any bucket when useful. They are managed by
`correct.py` and shown in the visible Markdown line.

| field            | type   | notes                                                   |
|------------------|--------|---------------------------------------------------------|
| `snooze_until`   | string | ISO 8601 time when the item should become relevant again |
| `waiting_on`     | string | person, company, or dependency the item is waiting on   |
| `delegated_to`   | string | person responsible for the next action                  |
| `blocked_reason` | string | concise reason the item is blocked                      |

## work_todo / personal_todo

Same schema for both — only the bucket (and therefore the id prefix) differs.
`work_todo` is for professional/job tasks; `personal_todo` is everything else.

| field       | type   | notes                                              |
|-------------|--------|----------------------------------------------------|
| `title`     | string | the task                                           |
| `due_time`  | string | ISO 8601 deadline/due time. Optional.              |
| `reminder_times` | array | Optional ISO 8601 reminder times chosen by agentic judgement; repeat entries for multiple Telegram reminders. |
| `priority`  | string | `low` / `normal` / `high` (default `normal`)       |
| `urgency`   | string | optional `low` / `normal` / `high`; useful for review and cleanup |
| `notes`     | string | optional                                           |

## work_shopping / personal_shopping

Same schema for both — only the bucket (and therefore the id prefix) differs.
`work_shopping` is for things to buy for work; `personal_shopping` is
everything else (household, personal errands).

| field      | type   | notes                                                          |
|------------|--------|-----------------------------------------------------------------|
| `item`     | string | what to buy                                                    |
| `quantity` | string | optional (e.g. `2`, `500g`)                                    |
| `category` | string | optional free-form subcategory (e.g. `pool`, `food`, `office`) |
| `urgency`  | string | optional `low`/`normal`/`high`                                 |
| `notes`    | string | optional                                                       |

## mypooldash

Everything about the MyPoolDashboard project — ideas, to-dos, and bug
reports — in one bucket, distinguished by `type`.

| field         | type   | notes                                                          |
|---------------|--------|-------------------------------------------------------------------|
| `type`        | string | `idea` / `todo` / `bug` (default `idea`)                       |
| `title`       | string | the idea, task, or bug in a line                               |
| `description` | string | optional, a sentence of detail                                 |
| `due_time`    | string | ISO 8601 deadline/due time; only meaningful when `type` is `todo`. |
| `reminder_times` | array | Optional ISO 8601 reminder times; only meaningful when `type` is `todo`. |
| `priority`    | string | `low` / `normal` / `high` (default `normal`); only meaningful when `type` is `todo` |
| `urgency`     | string | optional `low` / `normal` / `high`                             |

## inbox

| field               | type   | notes                                                              |
|---------------------|--------|----------------------------------------------------------------------|
| `raw_input`         | string | the message as received                                             |
| `confidence_score`  | number | 0–1, how unsure the classification was                              |
| `suggested_category`| string | best-guess bucket, if any (one of the six bucket names)             |
| `notes`             | string | optional                                                             |

## metadata.json

Not a bucket — the tool's bookkeeping.

```json
{
  "counters": {
    "work_todo": 3, "personal_todo": 1,
    "work_shopping": 1, "personal_shopping": 5,
    "mypooldash": 2, "inbox": 1
  },
  "scheduled": {
    "wt-20260702-0001::r1": {
      "task_id": "wt-20260702-0001",
      "reminder_time": "2026-07-02T14:30:00-04:00",
      "due_time": "2026-07-02T15:00:00-04:00",
      "message": "⏰ Reminder: Call the pool inspector",
      "cron_note": null
    }
  },
  "nudged": {
    "wt-20260702-0001": "2026-07-03"
  }
}
```

- `counters` — per-bucket id counters, so ids never collide.
- `nudged` — `task_id -> YYYY-MM-DD` of the last overdue follow-through nudge,
  so `reconcile_crons.py` chases an overdue open item at most once a day. Written
  by `reconcile_crons.py --mark-nudged` after a nudge is actually sent; an item
  drops out of `to_nudge` on its own once completed or rescheduled into the
  future.
- `scheduled` — reminders the tool believes are live. A single-reminder task
  may be keyed by task id; multi-reminder tasks use ids like
  `wt-20260702-0001::r1`. `task_id` points back to the captured item from
  `work_todo`, `personal_todo`, or a `mypooldash` entry with `type: todo`.
  `reminder_time` is when Telegram should ping; `due_time` is the task's
  deadline. This is what prevents double-scheduling. Reminders are only kept
  for records whose status is `open`; moving an item to `waiting`, `blocked`,
  `delegated`, `snoozed`, `done`, or `dropped` cancels live reminder jobs on the
  next reconcile. `cron_note` holds the id of the cron job you created for this
  reminder — `reconcile_crons.py --commit` requires it (via
  `--cron-note <id>=<cron-job-id>`) so the reminder can later be found and
  cancelled. Times are stored with an explicit UTC offset; naive times captured
  in the past are normalized to `America/New_York` on capture.

## Reminder cron spec (reconcile_crons.py / reminder_cron_spec.py)

Each `to_schedule` item from `reconcile_crons.py` carries a `cron_spec`: the
exact, delivering cron job to create. `reminder_cron_spec.py` emits the same
shape for a single reminder. It is the single source of truth for the mandatory
Telegram reminder contract — create it verbatim, never hand-build a reminder
job. Every spec has `sessionTarget: "isolated"`, `payload.kind: "agentTurn"`
(whose `message` says "Output exactly this reminder text and nothing else…"),
and an explicit `delivery` block (`mode: "announce"`, `channel: "telegram"`,
`to: "8688841600"`, `bestEffort: false`). Without that `delivery` block a cron
job fires but reports `deliveryStatus: not-requested` and sends nothing. The
`schedule.at` is the reminder instant in UTC. See SKILL.md → "Mandatory Telegram
reminder cron contract" for the validation and delivery-check rules.

## Enrichment output

`scripts/enrich.py` does not write records. It prints JSON with:

| field                  | type  | notes                                           |
|------------------------|-------|-------------------------------------------------|
| `suggested_tags`       | array | rule-based tags the agent may apply             |
| `suggested_urgency`    | string| `low` / `normal` / `high` hint                  |
| `duplicate_candidates` | array | likely duplicate active items with id, bucket, score, and visible text |

## Migrating from the v1 layout

The original version of this tool had four buckets: `work`, `shopping`,
`ideas`, `inbox`. If you have a workspace from before the work/personal split,
run `scripts/migrate_v2_buckets.py --commit` once — see its docstring for
details. It renames `work.md` → `work_todo.md` and `shopping.md` →
`personal_shopping.md` (remapping ids and `metadata.json` accordingly), and
creates empty `personal_todo.md` / `work_shopping.md`. `ideas.md` and
`inbox.md` are untouched.

## Migrating from the v2 layout

v2 had a dedicated `ideas` bucket for MyPoolDashboard concepts. v3 broadens it
into `mypooldash`, which also holds to-dos and bug reports for the project. If
this workspace still has `capture/ideas.md`, run
`scripts/migrate_v3_mypooldash.py --commit` once — see its docstring for
details. It renames `ideas.md` → `mypooldash.md` (id prefix `i-` → `mpd-`),
tagging every migrated record `"type": "idea"`. The old file is backed up
alongside as `ideas.md.v2.bak`, not deleted.

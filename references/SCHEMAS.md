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

## work_todo / personal_todo

Same schema for both — only the bucket (and therefore the id prefix) differs.
`work_todo` is for professional/job tasks; `personal_todo` is everything else.

| field       | type   | notes                                              |
|-------------|--------|----------------------------------------------------|
| `title`     | string | the task                                           |
| `due_time`  | string | ISO 8601; presence triggers a reminder. Optional.  |
| `priority`  | string | `low` / `normal` / `high` (default `normal`)       |
| `status`    | string | `open` / `done`                                    |
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
| `status`   | string | `open` / `done`                                                |

## mypooldash

Everything about the MyPoolDashboard project — ideas, to-dos, and bug
reports — in one bucket, distinguished by `type`.

| field         | type   | notes                                                          |
|---------------|--------|-------------------------------------------------------------------|
| `type`        | string | `idea` / `todo` / `bug` (default `idea`)                       |
| `title`       | string | the idea, task, or bug in a line                               |
| `description` | string | optional, a sentence of detail                                 |
| `due_time`    | string | ISO 8601; only meaningful when `type` is `todo`. Presence triggers a reminder, same as work_todo/personal_todo. |
| `priority`    | string | `low` / `normal` / `high` (default `normal`); only meaningful when `type` is `todo` |
| `tags`        | array  | optional list of strings                                       |
| `status`      | string | `open` / `done` (done = shipped/dropped/fixed/completed)        |

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
    "wt-20260702-0001": {
      "due_time": "2026-07-02T15:00:00+01:00",
      "message": "⏰ Reminder: Call the pool inspector",
      "cron_note": null
    }
  }
}
```

- `counters` — per-bucket id counters, so ids never collide.
- `scheduled` — reminders the tool believes are live, keyed by task id (from
  `work_todo`, `personal_todo`, or a `mypooldash` entry with `type: todo`).
  This is what prevents double-scheduling. `cron_note` is a free slot to
  record your cron tool's own job reference if that helps you cancel later.

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

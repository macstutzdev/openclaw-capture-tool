# Data schemas

Every captured item is stored as a human-readable line in its bucket's markdown
file, with the full record as compact JSON inside a trailing HTML comment
(`<!-- ... -->`). The comment is invisible when the markdown is rendered, so the
lists stay clean for Cormac while remaining exactly parseable for the scripts.

Do not hand-edit the JSON comments. Use `capture.py` and `correct.py`, which
keep the visible line and the record in sync and manage ids.

## Shared fields (all buckets)

| field        | type   | notes                                             |
|--------------|--------|---------------------------------------------------|
| `bucket`     | string | one of `work`, `shopping`, `ideas`, `inbox`       |
| `id`         | string | e.g. `w-20260702-0001`; prefix marks the bucket   |
| `created_at` | string | ISO 8601, set at capture; preserved across a move |

## work

| field       | type   | notes                                              |
|-------------|--------|----------------------------------------------------|
| `title`     | string | the task                                           |
| `due_time`  | string | ISO 8601; presence triggers a reminder. Optional.  |
| `priority`  | string | `low` / `normal` / `high` (default `normal`)       |
| `status`    | string | `open` / `done`                                    |
| `notes`     | string | optional                                           |

## shopping

| field      | type   | notes                          |
|------------|--------|--------------------------------|
| `item`     | string | what to buy                    |
| `quantity` | string | optional (e.g. `2`, `500g`)    |
| `category` | string | optional (e.g. `pool`, `food`) |
| `urgency`  | string | optional `low`/`normal`/`high` |
| `status`   | string | `open` / `done`                |

## ideas

| field         | type   | notes                                    |
|---------------|--------|------------------------------------------|
| `title`       | string | the idea in a line                       |
| `description` | string | optional, a sentence of detail           |
| `tags`        | array  | optional list of strings                 |
| `status`      | string | `open` / `done` (done = shipped/dropped) |

## inbox

| field               | type   | notes                                       |
|---------------------|--------|---------------------------------------------|
| `raw_input`         | string | the message as received                     |
| `confidence_score`  | number | 0–1, how unsure the classification was      |
| `suggested_category`| string | best-guess bucket, if any                   |
| `notes`             | string | optional                                    |

## metadata.json

Not a bucket — the tool's bookkeeping.

```json
{
  "counters": { "work": 3, "shopping": 5, "ideas": 2, "inbox": 1 },
  "scheduled": {
    "w-20260702-0001": {
      "due_time": "2026-07-02T15:00:00+01:00",
      "message": "⏰ Reminder: Call the pool inspector",
      "cron_note": null
    }
  }
}
```

- `counters` — per-bucket id counters, so ids never collide.
- `scheduled` — reminders the tool believes are live, keyed by task id. This is
  what prevents double-scheduling. `cron_note` is a free slot to record your
  cron tool's own job reference if that helps you cancel later.

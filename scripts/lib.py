"""Shared helpers for the capture tool.

Design in one sentence: each captured thing is stored as a human-readable
line in a markdown file, with the full structured record tucked into a
trailing HTML comment (invisible when the markdown is rendered, but easy to
parse reliably). This keeps the lists readable for Cormac AND machine-parseable
for the reminder logic.

Standard library only — no pip installs needed.
"""

import json
import os
import re
from datetime import datetime, timezone

BUCKETS = (
    "work_todo", "personal_todo", "work_shopping", "personal_shopping",
    "mypooldash", "inbox",
)

# The two todo-style buckets share a schema (title/due_time/priority/status)
# and both participate in reminders. The two shopping-style buckets share a
# different schema (item/quantity/category/urgency/status). Scripts that need
# to treat "any todo" or "any shopping" uniformly should loop over these.
TODO_BUCKETS = ("work_todo", "personal_todo")
SHOPPING_BUCKETS = ("work_shopping", "personal_shopping")

# The visible header at the top of each file. parse_entries skips any line
# that has no structured record, so headers are ignored automatically.
HEADERS = {
    "work_todo": "# Work to-do\n\n",
    "personal_todo": "# Personal to-do\n\n",
    "work_shopping": "# Work shopping\n\n",
    "personal_shopping": "# Personal shopping\n\n",
    "mypooldash": "# MyPoolDashboard (ideas, to-dos, bugs)\n\n",
    "inbox": "# Inbox (unsorted / unclear)\n\n",
}

_ID_PREFIX = {
    "work_todo": "wt", "personal_todo": "pt",
    "work_shopping": "ws", "personal_shopping": "ps",
    "mypooldash": "mpd", "inbox": "x",
}

_COMMENT_RE = re.compile(r"<!--(\{.*\})-->\s*$")


def default_root():
    """Where OpenClaw's workspace lives. Override with --root or the
    OPENCLAW_WORKSPACE env var (handy for testing)."""
    return os.environ.get("OPENCLAW_WORKSPACE", "/data/.openclaw/workspace")


def paths(root):
    cap = os.path.join(root, "capture")
    p = {"capture_dir": cap, "metadata": os.path.join(cap, "metadata.json")}
    for b in BUCKETS:
        p[b] = os.path.join(cap, f"{b}.md")
    return p


def now_iso():
    return datetime.now(timezone.utc).astimezone().replace(microsecond=0).isoformat()


# ---------- atomic file helpers ----------

def _atomic_write(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def append_line(path, line):
    """Append a single entry line, creating the file if missing."""
    if not os.path.exists(path):
        # Recreate with a header so the file is never a bare orphan.
        bucket = os.path.splitext(os.path.basename(path))[0]
        _atomic_write(path, HEADERS.get(bucket, ""))
    with open(path, "a", encoding="utf-8") as f:
        if not line.endswith("\n"):
            line += "\n"
        f.write(line)


# ---------- metadata ----------

def load_metadata(root):
    mp = paths(root)["metadata"]
    if not os.path.exists(mp):
        return {"counters": {b: 0 for b in BUCKETS}, "scheduled": {}}
    with open(mp, encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("counters", {b: 0 for b in BUCKETS})
    data.setdefault("scheduled", {})
    return data


def save_metadata(root, data):
    _atomic_write(paths(root)["metadata"], json.dumps(data, indent=2) + "\n")


def next_id(root, bucket):
    """Stable, sortable id like 'w-20260701-0003'. Persists a per-bucket
    counter in metadata so ids never collide, even across sessions."""
    meta = load_metadata(root)
    meta["counters"][bucket] = meta["counters"].get(bucket, 0) + 1
    n = meta["counters"][bucket]
    save_metadata(root, meta)
    return f"{_ID_PREFIX[bucket]}-{datetime.now().strftime('%Y%m%d')}-{n:04d}"


# ---------- entry formatting ----------

def _fmt_due(due_time):
    """Turn an ISO time into something friendly for the visible line."""
    try:
        dt = datetime.fromisoformat(due_time)
    except (ValueError, TypeError):
        return due_time
    if dt.hour == 0 and dt.minute == 0 and "T" not in due_time:
        return dt.strftime("%a %d %b")
    return dt.strftime("%a %d %b, %-I:%M %p")


def visible_text(record):
    """Build the human-facing part of a line from a record."""
    b = record["bucket"]
    if b in TODO_BUCKETS:
        box = "x" if record.get("status") == "done" else " "
        line = f"- [{box}] {record['title']}"
        bits = []
        if record.get("due_time"):
            bits.append(f"due {_fmt_due(record['due_time'])}")
        if record.get("priority") and record["priority"] != "normal":
            bits.append(record["priority"])
        if bits:
            line += f" ({', '.join(bits)})"
        return line
    if b in SHOPPING_BUCKETS:
        box = "x" if record.get("status") == "done" else " "
        line = f"- [{box}] {record['item']}"
        if record.get("quantity"):
            line += f" ×{record['quantity']}"
        if record.get("category"):
            line += f"  [{record['category']}]"
        return line
    if b == "mypooldash":
        kind = record.get("type", "idea")
        box = "x" if record.get("status") == "done" else " "
        line = f"- [{box}] [{kind}] {record['title']}"
        bits = []
        if kind == "todo" and record.get("due_time"):
            bits.append(f"due {_fmt_due(record['due_time'])}")
        if kind == "todo" and record.get("priority") and record["priority"] != "normal":
            bits.append(record["priority"])
        if bits:
            line += f" ({', '.join(bits)})"
        if record.get("description"):
            line += f" — {record['description']}"
        if record.get("tags"):
            line += f"  [{', '.join(record['tags'])}]"
        return line
    # inbox
    line = f"- {record['raw_input']}"
    sug = record.get("suggested_category")
    if sug:
        conf = record.get("confidence_score")
        conf_txt = f" {int(conf*100)}%" if isinstance(conf, (int, float)) else ""
        line += f"  (maybe {sug}?{conf_txt})"
    return line


def format_line(record):
    """Visible text + hidden structured record."""
    return f"{visible_text(record)} <!--{json.dumps(record, separators=(',', ':'))}-->"


def parse_line(line):
    m = _COMMENT_RE.search(line.strip())
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return None


def read_entries(root, bucket):
    p = paths(root)[bucket]
    if not os.path.exists(p):
        return []
    out = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            rec = parse_line(line)
            if rec:
                out.append(rec)
    return out


def rewrite_bucket(root, bucket, records):
    """Regenerate a whole file from records (used for corrections/edits)."""
    text = HEADERS.get(bucket, "")
    for rec in records:
        text += format_line(rec) + "\n"
    _atomic_write(paths(root)[bucket], text)


def new_record(bucket, **fields):
    rec = {"bucket": bucket, "created_at": now_iso()}
    rec.update({k: v for k, v in fields.items() if v is not None})
    return rec


def reminds(bucket, record):
    """Whether a record participates in the reminder system: either of the
    two todo buckets, or a mypooldash entry filed with type "todo"."""
    if bucket in TODO_BUCKETS:
        return True
    return bucket == "mypooldash" and record.get("type") == "todo"


def all_remindable_entries(root):
    """id -> record, across every bucket that can carry a due_time reminder."""
    tasks = {}
    for b in TODO_BUCKETS:
        for r in read_entries(root, b):
            tasks[r["id"]] = r
    for r in read_entries(root, "mypooldash"):
        if r.get("type") == "todo":
            tasks[r["id"]] = r
    return tasks

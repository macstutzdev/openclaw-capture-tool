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
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from difflib import SequenceMatcher

try:
    import fcntl
except ImportError:  # pragma: no cover - OpenClaw normally runs on macOS/Linux.
    fcntl = None

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python < 3.9
    ZoneInfo = None

# Where the reminder logic lives. Cormac thinks in Eastern time, so naive
# datetimes are interpreted here unless an explicit offset is supplied.
DEFAULT_TZ = os.environ.get("CAPTURE_TIMEZONE", "America/New_York")

# The Telegram chat reminders are delivered to. Override with the
# CAPTURE_TELEGRAM_TO env var if the account ever changes.
DEFAULT_TELEGRAM_TO = os.environ.get("CAPTURE_TELEGRAM_TO", "8688841600")

BUCKETS = (
    "work_todo", "personal_todo", "work_shopping", "personal_shopping",
    "mypooldash", "inbox",
)

STATUSES = (
    "open", "done", "snoozed", "waiting", "blocked", "delegated", "dropped",
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
    directory = os.path.dirname(path) or "."
    basename = os.path.basename(path)
    fd, tmp = tempfile.mkstemp(prefix=f"{basename}.", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


@contextmanager
def _metadata_lock(root):
    """Serialize metadata counter updates across concurrent captures."""
    p = paths(root)
    os.makedirs(p["capture_dir"], exist_ok=True)
    with open(p["metadata"] + ".lock", "w", encoding="utf-8") as lock:
        if fcntl is not None:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


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
    # task_id -> YYYY-MM-DD of the last overdue nudge, so follow-through pings
    # an item at most once a day.
    data.setdefault("nudged", {})
    return data


def save_metadata(root, data):
    _atomic_write(paths(root)["metadata"], json.dumps(data, indent=2) + "\n")


def next_id(root, bucket):
    """Stable, sortable id like 'w-20260701-0003'. Persists a per-bucket
    counter in metadata so ids never collide, even across sessions."""
    with _metadata_lock(root):
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


def _status_box(status):
    return "x" if status == "done" else " "


def _lifecycle_bits(record):
    bits = []
    status = record.get("status")
    has_detail = (
        (status == "snoozed" and record.get("snooze_until"))
        or (status == "waiting" and record.get("waiting_on"))
        or (status == "delegated" and record.get("delegated_to"))
        or (status == "blocked" and record.get("blocked_reason"))
    )
    if status and status not in ("open", "done") and not has_detail:
        bits.append(status)
    if record.get("snooze_until"):
        bits.append(f"snoozed until {_fmt_due(record['snooze_until'])}")
    if record.get("waiting_on"):
        bits.append(f"waiting on {record['waiting_on']}")
    if record.get("delegated_to"):
        bits.append(f"delegated to {record['delegated_to']}")
    if record.get("blocked_reason"):
        bits.append(f"blocked: {record['blocked_reason']}")
    if record.get("urgency") and record["urgency"] != "normal":
        bits.append(f"urgency {record['urgency']}")
    return bits


def _fmt_tags(record, exclude=None):
    excluded = set(exclude or [])
    tags = [tag for tag in record.get("tags") or [] if tag not in excluded]
    return f"  [{', '.join(tags)}]" if tags else ""


def visible_text(record):
    """Build the human-facing part of a line from a record."""
    b = record["bucket"]
    if b in TODO_BUCKETS:
        box = _status_box(record.get("status"))
        line = f"- [{box}] {record['title']}"
        bits = []
        if record.get("due_time"):
            bits.append(f"due {_fmt_due(record['due_time'])}")
        if record.get("priority") and record["priority"] != "normal":
            bits.append(record["priority"])
        bits.extend(_lifecycle_bits(record))
        if bits:
            line += f" ({', '.join(bits)})"
        line += _fmt_tags(record)
        return line
    if b in SHOPPING_BUCKETS:
        box = _status_box(record.get("status"))
        line = f"- [{box}] {record['item']}"
        if record.get("quantity"):
            line += f" ×{record['quantity']}"
        if record.get("category"):
            line += f"  [{record['category']}]"
        bits = _lifecycle_bits(record)
        if bits:
            line += f" ({', '.join(bits)})"
        line += _fmt_tags(record, exclude=[record.get("category")])
        return line
    if b == "mypooldash":
        kind = record.get("type", "idea")
        box = _status_box(record.get("status"))
        line = f"- [{box}] [{kind}] {record['title']}"
        bits = []
        if kind == "todo" and record.get("due_time"):
            bits.append(f"due {_fmt_due(record['due_time'])}")
        if kind == "todo" and record.get("priority") and record["priority"] != "normal":
            bits.append(record["priority"])
        bits.extend(_lifecycle_bits(record))
        if bits:
            line += f" ({', '.join(bits)})"
        if record.get("description"):
            line += f" — {record['description']}"
        line += _fmt_tags(record)
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


# ---------- time normalization ----------

def normalize_iso(value):
    """Return an ISO 8601 string that always carries a UTC offset.

    Cron needs an absolute instant, but Cormac (and the classifying agent)
    often writes naive times like '2026-07-02T15:00'. A naive value is
    interpreted in DEFAULT_TZ (America/New_York), so DST is handled correctly.
    Returns (normalized_iso, was_naive). Raises ValueError on unparseable input.
    """
    dt = datetime.fromisoformat(value)
    was_naive = dt.tzinfo is None
    if was_naive:
        tz = ZoneInfo(DEFAULT_TZ) if ZoneInfo is not None else None
        if tz is None:  # pragma: no cover - very old Python
            dt = dt.astimezone()
        else:
            dt = dt.replace(tzinfo=tz)
    return dt.replace(microsecond=0).isoformat(), was_naive


def _to_utc_z(value):
    """ISO string -> UTC instant formatted like '2026-07-04T13:00:00.000Z'."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        tz = ZoneInfo(DEFAULT_TZ) if ZoneInfo is not None else None
        dt = dt.replace(tzinfo=tz) if tz is not None else dt.astimezone()
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


# ---------- reminder cron spec ----------
#
# This is the single source of truth for the "mandatory Telegram reminder cron
# contract" (see SKILL.md). Every reminder cron job MUST use explicit announce
# delivery to Telegram; a job without it fires but delivers nothing. Both
# reminder_cron_spec.py and reconcile_crons.py build their specs here so the
# contract can never drift between them.

def reminder_message(title, due_short=None):
    """The one-line reminder body Cormac should receive."""
    suffix = f" (due {due_short})" if due_short else ""
    return f"⏰ Reminder: {title}{suffix}"


def reminder_cron_spec(reminder_id, reminder_time, message, telegram_to=None):
    """Build the canonical, delivering cron job spec for one reminder.

    The isolated child agent is told to *output* the text, never to "send" it —
    the delivery layer does the sending. Instructing it to send invites it to
    reach for messaging tools and narrate failures.
    """
    to = telegram_to or DEFAULT_TELEGRAM_TO
    return {
        "name": f"Capture reminder: {reminder_id}",
        "schedule": {"kind": "at", "at": _to_utc_z(reminder_time)},
        "deleteAfterRun": True,
        "sessionTarget": "isolated",
        "wakeMode": "now",
        "payload": {
            "kind": "agentTurn",
            "message": f"Output exactly this reminder text and nothing else:\n\n{message}",
            "timeoutSeconds": 60,
            "lightContext": True,
        },
        "delivery": {
            "mode": "announce",
            "channel": "telegram",
            "to": to,
            "bestEffort": False,
        },
    }


# The contract a created cron job must satisfy to count as a real reminder.
# Kept as data so both scripts and SKILL.md validation stay in lock-step.
REMINDER_CONTRACT = {
    "sessionTarget": "isolated",
    "payload.kind": "agentTurn",
    "delivery.mode": "announce",
    "delivery.channel": "telegram",
}


def validate_reminder_job(job, telegram_to=None):
    """Check a created cron job against the delivery contract.

    Returns a list of human-readable problems; empty means the job is a valid
    delivering Telegram reminder. Guards against the two observed failure
    shapes: sessionTarget "main" + systemEvent, and a missing delivery block.
    """
    to = telegram_to or DEFAULT_TELEGRAM_TO
    problems = []
    if not isinstance(job, dict):
        return ["cron job is not an object"]
    if job.get("sessionTarget") != "isolated":
        problems.append(f'sessionTarget must be "isolated" (got {job.get("sessionTarget")!r})')
    payload = job.get("payload") or {}
    if payload.get("kind") != "agentTurn":
        problems.append(f'payload.kind must be "agentTurn" (got {payload.get("kind")!r})')
    delivery = job.get("delivery") or {}
    if delivery.get("mode") != "announce":
        problems.append(f'delivery.mode must be "announce" (got {delivery.get("mode")!r})')
    if delivery.get("channel") != "telegram":
        problems.append(f'delivery.channel must be "telegram" (got {delivery.get("channel")!r})')
    if str(delivery.get("to")) != str(to):
        problems.append(f'delivery.to must be {to!r} (got {delivery.get("to")!r})')
    return problems


# ---------- proactive digest cron spec ----------
#
# A digest is a *recurring* OpenClaw cron job that wakes an isolated agent to
# run a review and push it to Telegram unprompted. Unlike a reminder (which just
# outputs fixed text and uses announce delivery), the digest agent needs the
# skill loaded so it can run review.py --buttons and send an interactive
# checklist itself — so lightContext is false and delivery.mode is "none".

def digest_cron_spec(slug, cron_expr, agent_message, tz=None):
    """Build a recurring cron job that runs a proactive digest.

    `cron_expr` is a standard 5-field expression interpreted in `tz` (defaults
    to DEFAULT_TZ, i.e. Eastern wall-clock). `agent_message` is the self-
    contained instruction the isolated agent runs at each fire.
    """
    return {
        "name": f"Capture digest: {slug}",
        "schedule": {"kind": "cron", "expr": cron_expr, "tz": tz or DEFAULT_TZ},
        "sessionTarget": "isolated",
        "wakeMode": "now",
        "payload": {
            "kind": "agentTurn",
            "message": agent_message,
            "timeoutSeconds": 120,
            "lightContext": False,
        },
        "delivery": {"mode": "none"},
    }


# ---------- duplicate detection ----------
#
# Shared by enrich.py (on request) and capture.py (automatically, before
# filing) so the same similarity scoring guards both paths.

_DUP_TEXT_FIELDS = ("title", "item", "raw_input", "description", "notes")

# capture.py refuses to silently file above this; enrich.py reports above 0.55.
STRONG_DUPLICATE_SCORE = 0.72


def record_text(record):
    """Flatten a record's human fields into one string for comparison."""
    return " ".join(
        str(record.get(field, "")) for field in _DUP_TEXT_FIELDS if record.get(field)
    )


def _dup_token_set(text):
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def duplicate_score(a, b):
    """0–1 similarity blending sequence ratio and token overlap."""
    ratio = SequenceMatcher(None, a.lower(), b.lower()).ratio()
    a_tokens, b_tokens = _dup_token_set(a), _dup_token_set(b)
    if not a_tokens or not b_tokens:
        return ratio
    overlap = len(a_tokens & b_tokens) / len(a_tokens | b_tokens)
    return round((ratio + overlap) / 2, 3)


def duplicate_candidates(root, text, bucket=None, entry_id=None, min_score=0.55):
    """Active records similar to `text`, best match first. Skips done/dropped."""
    matches = []
    for candidate_bucket in BUCKETS:
        if bucket and candidate_bucket != bucket:
            continue
        for record in read_entries(root, candidate_bucket):
            if record.get("id") == entry_id or record.get("status") in ("done", "dropped"):
                continue
            score = duplicate_score(text, record_text(record))
            if score >= min_score:
                matches.append({
                    "id": record.get("id"),
                    "bucket": candidate_bucket,
                    "score": score,
                    "text": visible_text(record),
                })
    return sorted(matches, key=lambda item: item["score"], reverse=True)

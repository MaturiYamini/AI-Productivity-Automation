import base64
import email
import imaplib
import json
import os
import re
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from io import BytesIO
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from dateutil import parser as date_parser
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from openai import OpenAI
from dotenv import load_dotenv

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

try:
    import docx
except Exception:
    docx = None

app = Flask(__name__)
CORS(app)
# Force override to ensure .env changes are always picked up immediately
load_dotenv(override=True)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'assistant.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "connect_args": {"timeout": 30},  # Increase SQLite timeout to 30s to avoid 'database is locked'
}
db = SQLAlchemy(app)


# ── Models ────────────────────────────────────────────────────────────────────

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    deadline = db.Column(db.DateTime, nullable=True)
    priority = db.Column(db.String(20), nullable=False, default="Low")
    time_remaining = db.Column(db.String(120), nullable=False, default="No deadline")
    status = db.Column(db.String(20), nullable=False, default="pending")
    source_text = db.Column(db.Text, nullable=True)
    reminded = db.Column(db.Boolean, default=False, nullable=False)


class SummaryHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    source_text = db.Column(db.Text, nullable=False)
    short_summary = db.Column(db.Text, nullable=False)
    bullets = db.Column(db.Text, nullable=False)
    highlights = db.Column(db.Text, nullable=False)


class ReminderAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, nullable=False)
    message = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    seen = db.Column(db.Boolean, default=False, nullable=False)
    alert_type = db.Column(db.String(20), nullable=False, default="upcoming")


class Notification(db.Model):
    """In-app notifications for deadline reminders shown in the bell panel."""
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, nullable=True)
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    notif_type = db.Column(db.String(20), nullable=False, default="reminder")  # reminder|due-soon|overdue
    seen = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class WorkItem(db.Model):
    """Manual work items added by the user in My Work."""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    deadline = db.Column(db.DateTime, nullable=True)
    priority = db.Column(db.String(20), nullable=False, default="Medium")
    status = db.Column(db.String(20), nullable=False, default="pending")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    reminded = db.Column(db.Boolean, default=False, nullable=False)


# ── Helpers ───────────────────────────────────────────────────────────────────

def now_utc() -> datetime:
    return datetime.utcnow()


def parse_deadline_from_text(text: str, created_time: datetime) -> Optional[datetime]:
    lower = text.lower()
    if "tomorrow" in lower:
        return created_time + timedelta(days=1)

    in_days = re.search(r"in\s+(\d+)\s+day", lower)
    if in_days:
        return created_time + timedelta(days=int(in_days.group(1)))

    in_hours = re.search(r"in\s+(\d+)\s+hour", lower)
    if in_hours:
        return created_time + timedelta(hours=int(in_hours.group(1)))

    by_weekday = re.search(
        r"by\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", lower
    )
    if by_weekday:
        weekdays = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
                    "friday": 4, "saturday": 5, "sunday": 6}
        target = weekdays[by_weekday.group(1)]
        days_ahead = (target - created_time.weekday()) % 7 or 7
        return created_time + timedelta(days=days_ahead)

    try:
        parsed = date_parser.parse(text, fuzzy=True, default=created_time)
        if parsed.year >= created_time.year and parsed != created_time:
            return parsed
    except Exception:
        pass
    return None


def format_time_remaining(deadline: Optional[datetime]) -> str:
    if not deadline:
        return "No deadline"
    seconds = int((deadline - now_utc()).total_seconds())
    if seconds < 0:
        return "Overdue"
    if seconds < 3600:
        return f"Due in {max(1, seconds // 60)} minutes"
    if seconds < 86400:
        return f"Due in {seconds // 3600} hours"
    return f"Due in {seconds // 86400} days"


def detect_priority(text: str, deadline: Optional[datetime]) -> str:
    lower = text.lower()
    if any(k in lower for k in ["urgent", "asap", "immediately"]):
        return "High"
    if deadline:
        hours_left = (deadline - now_utc()).total_seconds() / 3600
        if hours_left <= 24:
            return "High"
        if hours_left <= 72:
            return "Medium"
    if any(k in lower for k in ["important", "soon", "priority"]):
        return "Medium"
    return "Low"


def priority_rank(priority: str) -> int:
    return {"High": 0, "Medium": 1, "Low": 2}.get(priority, 2)


def split_candidate_lines(text: str) -> list[str]:
    """Split text into candidate lines, skipping noise like headings, short labels, and blank lines."""
    lines = []
    for line in text.splitlines():
        line = line.strip("-*•▪▸►→ \t")
        # Skip blank, very short (headings/labels), or very long lines (body paragraphs)
        # Conservative: Require at least 20 chars for a meaningful task line
        if len(line) < 20 or len(line) > 500:
            continue
        # Skip lines that are ALL CAPS (headings)
        if line.isupper() and len(line) > 20:
            continue
        # Skip lines ending with ':' (section headers like "Objectives:", "Summary:")
        if line.endswith(':') and len(line) < 30:
            continue
        # Skip lines that look like page numbers, dates-only, or figure captions
        if re.match(r'^(page\s*\d+|figure\s*\d+|table\s*\d+|\d+\.?\s*$)', line.lower()):
            continue
        lines.append(line)
    if lines:
        return lines
    # Fallback: split on sentence boundaries
    return [p.strip() for p in re.split(r'(?<=[.!?])\s+', text) if 10 <= len(p.strip()) <= 500]


def task_like(sentence: str) -> bool:
    """
    Returns True only for sentences that are personal actionable tasks —
    i.e. something the user themselves must DO, with a deadline or submission context.
    Rejects lecture notes, explanations, and passive/descriptive content.
    """
    lower = sentence.lower()
    stripped = lower.strip()

    # Too short or too long to be a task
    if len(stripped) < 8 or len(stripped) > 500:
        return False

    # Reject sentences that look like lecture/note content:
    passive_starts = ("the ", "a ", "an ", "this ", "these ", "those ", "it ",
                      "there ", "when ", "if ", "as ", "for ", "with ",
                      "during ", "after ", "before ", "since ", "because ")
    # Relaxed: only reject if it's clearly a long descriptive sentence
    if any(stripped.startswith(p) for p in passive_starts) and len(stripped) > 100:
        return False

    # Must have a first-person or imperative action signal
    personal_signals = [
        "i need to", "i must", "i have to", "i should", "i will",
        "need to", "must ", "have to", "don't forget", "remember to",
        "submit", "finish", "complete", "revise", "review",
        "schedule", "book", "register", "sign up",
        "can you", "please "
    ]
    has_personal_action = any(sig in lower for sig in personal_signals)
    
    # Also allow if it starts with a verb (imperative)
    # Simple check for verb-like start: not a common noun/pronoun
    common_non_verbs = ["my", "your", "his", "her", "their", "our", "the", "a", "an"]
    first_word = stripped.split()[0] if stripped.split() else ""
    is_imperative = first_word and first_word not in common_non_verbs and not first_word.endswith('ing')

    if not (has_personal_action or is_imperative):
        return False

    # Must ALSO have at least one of: a deadline signal OR a concrete task object
    deadline_signals = [
        "by ", "due ", "deadline", "tomorrow", "today", "tonight",
        "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
        "next week", "this week", "in \d", "asap", "urgent", "soon"
    ]
    task_objects = [
        "assignment", "homework", "project", "exam", "quiz", "test",
        "report", "presentation", "lab", "essay", "thesis",
        "form", "application", "invoice", "ticket", "pr", "pull request",
        "task", "action item"
    ]
    # Stricter: must have a clear deadline signal OR a clear task object
    has_deadline = any(sig in lower for sig in deadline_signals) or bool(
        re.search(r"\b(by|due|before|at)\s+\d", lower) or  # Requires a number after by/due/at
        re.search(r"\d{4}-\d{2}-\d{2}", lower) or
        re.search(r"in\s+\d+\s+(day|hour|week)", lower)
    )
    has_object = any(obj in lower for obj in task_objects)

    return has_deadline or has_object


def fallback_summarize(text: str) -> dict:
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
    if not sentences:
        return {"short_summary": "", "bullets": [], "highlights": []}
    short = " ".join(sentences[:2])[:400]
    bullets = sentences[:5]
    highlights = sorted(bullets, key=len, reverse=True)[:3]
    return {"short_summary": short, "bullets": bullets, "highlights": highlights}


def ai_summarize(text: str) -> dict:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return fallback_summarize(text)
    try:
        client = OpenAI(api_key=api_key)
        prompt = f"""You are a productivity assistant.
Return valid JSON with keys:
- short_summary (string, 2-4 lines)
- bullets (array of concise bullet strings, max 6)
- highlights (array of 3 key highlights)

Text:
{text}
"""
        response = client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            input=prompt,
            temperature=0.2,
        )
        raw = response.output_text
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return fallback_summarize(text)
        import json
        parsed = json.loads(match.group(0))
        return {
            "short_summary": parsed.get("short_summary", ""),
            "bullets": parsed.get("bullets", []),
            "highlights": parsed.get("highlights", []),
        }
    except Exception:
        return fallback_summarize(text)


def extract_text_from_uploaded_file(file_storage) -> str:
    filename = (file_storage.filename or "").lower()
    data = file_storage.read()
    file_storage.seek(0)
    if filename.endswith(".pdf"):
        if PdfReader is None:
            raise ValueError("PDF support not installed. Install pypdf.")
        reader = PdfReader(BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages).strip()
    if filename.endswith(".docx"):
        if docx is None:
            raise ValueError("DOCX support not installed. Install python-docx.")
        document = docx.Document(BytesIO(data))
        return "\n".join(paragraph.text for paragraph in document.paragraphs).strip()
    return data.decode("utf-8", errors="ignore").strip()


def extract_tasks(text: str, created_time: datetime) -> list[dict]:
    items = []
    for line in split_candidate_lines(text):
        if not task_like(line):
            continue
        deadline = parse_deadline_from_text(line, created_time)
        if not deadline:  # ONLY add if a deadline is detected
            continue
        priority = detect_priority(line, deadline)
        items.append({
            "title": line[:255],
            "created_at": created_time,
            "deadline": deadline,
            "priority": priority,
            "time_remaining": format_time_remaining(deadline),
            "status": "pending",
        })
    return items


def sorted_tasks_query():
    tasks = Task.query.all()
    for task in tasks:
        task.time_remaining = format_time_remaining(task.deadline)
    db.session.commit()
    return sorted(tasks, key=lambda t: (
        priority_rank(t.priority),
        t.deadline if t.deadline else datetime.max,
        t.created_at,
    ))


def task_to_dict(task: Task) -> dict:
    return {
        "id": task.id,
        "title": task.title,
        "created_at": task.created_at.isoformat(),
        "deadline": task.deadline.isoformat() if task.deadline else None,
        "priority": task.priority,
        "time_remaining": task.time_remaining,
        "status": task.status,
    }


def notif_to_dict(n: Notification) -> dict:
    return {
        "id": n.id,
        "task_id": n.task_id,
        "title": n.title,
        "message": n.message,
        "notif_type": n.notif_type,
        "seen": n.seen,
        "created_at": n.created_at.isoformat(),
    }


def _push_notif(task_id: int, title: str, message: str, notif_type: str):
    """Add a notification only if one of the same type for this task doesn't exist yet."""
    exists = Notification.query.filter_by(task_id=task_id, notif_type=notif_type).first()
    if not exists:
        db.session.add(Notification(task_id=task_id, title=title, message=message, notif_type=notif_type))


def work_to_dict(w: WorkItem) -> dict:
    return {
        "id": w.id,
        "title": w.title,
        "notes": w.notes or "",
        "deadline": w.deadline.isoformat() if w.deadline else None,
        "priority": w.priority,
        "time_remaining": format_time_remaining(w.deadline),
        "status": w.status,
        "created_at": w.created_at.isoformat(),
    }


# ── Background reminder job ───────────────────────────────────────────────────

def _check_item(item_id: int, title: str, deadline: datetime, reminded: bool, is_task: bool):
    """Fire reminders for any item (Task or WorkItem). Returns new reminded value."""
    remaining = (deadline - now_utc()).total_seconds()

    if 0 < remaining <= 86400 and not reminded:
        if is_task:
            db.session.add(ReminderAlert(
                task_id=item_id,
                message=f"⏰ Reminder: '{title}' is due within 24 hours.",
                alert_type="upcoming",
            ))
        _push_notif(item_id, f"⏰ Due in 24h: {title}", f"'{title}' is due within 24 hours.", "reminder")
        reminded = True

    if 0 < remaining <= 3600:
        if is_task and not ReminderAlert.query.filter_by(task_id=item_id, alert_type="due-soon").first():
            db.session.add(ReminderAlert(
                task_id=item_id,
                message=f"🔔 Due soon: '{title}' is due within 1 hour!",
                alert_type="due-soon",
            ))
        _push_notif(item_id, f"🔔 Due soon: {title}", f"'{title}' is due within 1 hour!", "due-soon")

    if remaining < 0:
        if is_task and not ReminderAlert.query.filter_by(task_id=item_id, alert_type="overdue").first():
            db.session.add(ReminderAlert(
                task_id=item_id,
                message=f"🚨 Overdue: '{title}' missed its deadline.",
                alert_type="overdue",
            ))
        _push_notif(item_id, f"🚨 Overdue: {title}", f"'{title}' missed its deadline.", "overdue")
        reminded = True

    return reminded


def reminder_job():
    with app.app_context():
        for task in Task.query.filter_by(status="pending").all():
            if not task.deadline:
                continue
            task.time_remaining = format_time_remaining(task.deadline)
            task.reminded = _check_item(task.id, task.title, task.deadline, task.reminded, True)

        for work in WorkItem.query.filter_by(status="pending").all():
            if not work.deadline:
                continue
            work.reminded = _check_item(work.id, work.title, work.deadline, work.reminded, False)

        db.session.commit()


# ── Gmail IMAP helpers ───────────────────────────────────────────────────────

class GmailMessage(db.Model):
    """Tracks processed Gmail message IDs to avoid duplicates."""
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.String(255), nullable=False, unique=True)
    subject = db.Column(db.String(500), nullable=True)
    sender = db.Column(db.String(255), nullable=True)
    snippet = db.Column(db.Text, nullable=True)
    tasks_added = db.Column(db.Integer, default=0)
    received_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


def _imap_connect():
    user = os.getenv("GMAIL_USER", "").strip()
    pwd = os.getenv("GMAIL_APP_PASSWORD", "").strip()
    if not user or not pwd:
        return None, "GMAIL_USER or GMAIL_APP_PASSWORD not set in .env"
    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
        mail.login(user, pwd)
        return mail, None
    except Exception as e:
        return None, str(e)


def _fetch_email_text(mail, uid: bytes) -> tuple[str, str, str, str, datetime]:
    """Returns (message_id, subject, sender, plain_text, received_at) for a given UID."""
    _, data = mail.uid("fetch", uid, "(RFC822)")
    raw = data[0][1]
    msg = email.message_from_bytes(raw)
    mid = msg.get("Message-ID", uid.decode())
    sender = msg.get("From", "")
    subject = msg.get("Subject", "")
    
    # Parse received date
    date_str = msg.get("Date")
    received_at = now_utc()
    if date_str:
        try:
            received_at = date_parser.parse(date_str)
            # Make naive if it's aware to match our now_utc()
            if received_at.tzinfo:
                received_at = received_at.astimezone(None).replace(tzinfo=None)
        except Exception:
            pass

    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get("Content-Disposition"):
                body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                break
    else:
        body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
    return mid, subject, sender, body, received_at


_openai_quota_exceeded_until = 0

def ai_extract_tasks(text: str, created_time: datetime) -> list[dict]:
    """Use AI to extract tasks from text. Returns a list of dicts with Task fields."""
    global _openai_quota_exceeded_until
    import time
    if time.time() < _openai_quota_exceeded_until:
        # Avoid redundant calls if quota is already known to be exceeded
        return []

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return []
    try:
        client = OpenAI(api_key=api_key)
        prompt = f"""You are a productivity assistant.
Extract any actionable tasks from the following text.
Each task should have a title (what to do), priority (High, Medium, or Low), and a deadline if one is mentioned.
Current time: {created_time.isoformat()}
Return valid JSON as an array of objects with keys:
- title (string)
- priority (string: High, Medium, Low)
- deadline (ISO string or null)

Text:
{text}
"""
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        raw = response.choices[0].message.content
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            return []
        import json
        parsed = json.loads(match.group(0))
        tasks = []
        for p in parsed:
            deadline = None
            if p.get("deadline"):
                try:
                    deadline = date_parser.parse(p["deadline"])
                except Exception:
                    pass
            tasks.append({
                "title": p.get("title", "")[:255],
                "created_at": created_time,
                "deadline": deadline,
                "priority": p.get("priority", "Medium"),
                "time_remaining": format_time_remaining(deadline),
                "status": "pending",
            })
        return tasks
    except Exception as e:
        print(f"AI task extraction failed: {e}")
        if "insufficient_quota" in str(e) or "429" in str(e):
            # Quota exceeded. Disable AI extraction for the next hour to speed up sync.
            _openai_quota_exceeded_until = time.time() + 3600
        return []


def _extract_email_tasks(subject: str, body: str, created_time: datetime) -> list[dict]:
    """Email-aware extraction: ONLY adds ONE task if a deadline is detected."""
    # Try AI extraction first for better quality
    combined_text = f"Subject: {subject}\n\n{body}"
    ai_tasks = ai_extract_tasks(combined_text, created_time)
    if ai_tasks:
        for t in ai_tasks:
            # Strictly only add the FIRST task with a deadline
            if t.get("deadline"):
                return [t]

    # Fallback 1: Run standard body extraction and take the FIRST one with a deadline
    body_tasks = extract_tasks(subject + "\n" + body, created_time)
    for entry in body_tasks:
        if entry.get("deadline"):
            return [entry]

    # Fallback 2: subject check with strict rules
    subj = subject.strip()
    if subj and len(subj) >= 5:
        subj_lower = subj.lower()
        action_words = [
            "assignment", "homework", "project", "exam", "quiz", "report",
            "presentation", "deadline", "due", "urgent", "reminder"
        ]
        if any(w in subj_lower for w in action_words):
            deadline = parse_deadline_from_text(subj + " " + body, created_time)
            if deadline:
                priority = detect_priority(subj, deadline)
                return [{
                    "title": subj[:255], "created_at": created_time,
                    "deadline": deadline, "priority": priority,
                    "time_remaining": format_time_remaining(deadline), "status": "pending",
                }]

    return []


def gmail_poll_job() -> tuple[int, Optional[str]]:
    """Fetch unread Gmail via IMAP from the last 10 minutes only."""
    with app.app_context():
        mail, err = _imap_connect()
        if not mail:
            return 0, err or "Connection failed"
        try:
            mail.select("INBOX")
            # Only process emails from the last 10 minutes
            ten_min_ago = now_utc() - timedelta(minutes=10)
            
            # IMAP search for UNSEEN. We will then manually filter by precise timestamp.
            today_str = ten_min_ago.strftime("%d-%b-%Y")
            _, uids = mail.uid("search", None, f'UNSEEN SINCE "{today_str}"')
            uid_list = uids[0].split()[-20:]
        except Exception as e:
            mail.logout()
            return 0, str(e)

        added = 0
        for uid in uid_list:
            try:
                mid, subject, sender, body, received_at = _fetch_email_text(mail, uid)
            except Exception:
                continue
            
            # STRICT: Ignore emails received more than 10 minutes ago
            if received_at < ten_min_ago:
                continue

            if GmailMessage.query.filter_by(message_id=mid).first():
                continue

            tasks = _extract_email_tasks(subject, body, received_at)
            task_count = 0
            for entry in tasks:
                db.session.add(Task(
                    title=entry["title"], created_at=entry["created_at"],
                    deadline=entry["deadline"], priority=entry["priority"],
                    time_remaining=entry["time_remaining"], status=entry["status"],
                    source_text=(subject + "\n" + body)[:500],
                ))
                task_count += 1
                added += 1
            
            try:
                mail.uid("store", uid, "+FLAGS", "\\Seen")
            except Exception:
                pass
                
            snippet = body.strip()[:200].replace("\n", " ")
            db.session.add(GmailMessage(
                message_id=mid, subject=subject[:500], sender=sender[:255],
                snippet=snippet, tasks_added=task_count,
                received_at=received_at
            ))

        db.session.commit()
        mail.logout()
        if added:
            reminder_job()
        return added, None


# ── Email helper ──────────────────────────────────────────────────────────────

def send_test_email() -> dict:
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_port = int(os.getenv("SMTP_PORT", "587").strip() or "587")
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_password = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_from = os.getenv("SMTP_FROM_EMAIL", smtp_user).strip()
    smtp_to = os.getenv("SMTP_TO_EMAIL", smtp_user).strip()
    use_tls = os.getenv("SMTP_USE_TLS", "true").strip().lower() == "true"
    if not smtp_host or not smtp_user or not smtp_password or not smtp_to:
        return {"ok": False, "error": "SMTP config missing."}
    msg = EmailMessage()
    msg["Subject"] = "AI Productivity Assistant - Mail Connection Test"
    msg["From"] = smtp_from
    msg["To"] = smtp_to
    msg.set_content("Mail integration is connected successfully.")
    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            if use_tls:
                server.starttls()
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
        return {"ok": True, "message": f"Test email sent to {smtp_to}"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/api/mail/test", methods=["POST"])
def mail_test():
    result = send_test_email()
    if not result["ok"]:
        return jsonify({"error": result["error"]}), 400
    return jsonify({"status": "connected", "message": result["message"]})


@app.route("/api/process", methods=["POST"])
def process_text():
    payload = request.json or {}
    text = (payload.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400

    created_time = now_utc()
    if payload.get("created_time"):
        try:
            created_time = date_parser.parse(payload["created_time"])
        except Exception:
            pass

    summary = ai_summarize(text)
    tasks = extract_tasks(text, created_time)

    for entry in tasks:
        db.session.add(Task(
            title=entry["title"], created_at=entry["created_at"],
            deadline=entry["deadline"], priority=entry["priority"],
            time_remaining=entry["time_remaining"], status=entry["status"],
            source_text=text,
        ))

    db.session.add(SummaryHistory(
        source_text=text, short_summary=summary["short_summary"],
        bullets="\n".join(summary["bullets"]), highlights="\n".join(summary["highlights"]),
    ))
    db.session.commit()
    # Run reminder check immediately after new tasks are added
    reminder_job()
    return jsonify({"summary": summary, "tasks": [task_to_dict(t) for t in sorted_tasks_query()]})


@app.route("/api/process-file", methods=["POST"])
def process_file():
    if "file" not in request.files:
        return jsonify({"error": "file is required"}), 400
    uploaded = request.files["file"]
    if not uploaded.filename:
        return jsonify({"error": "No file selected"}), 400
    try:
        text = extract_text_from_uploaded_file(uploaded)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception:
        return jsonify({"error": "Could not read file content"}), 400
    if not text.strip():
        return jsonify({"error": "No readable text found in uploaded file"}), 400

    created_time = now_utc()
    summary = ai_summarize(text)
    tasks = extract_tasks(text, created_time)
    for entry in tasks:
        db.session.add(Task(
            title=entry["title"], created_at=entry["created_at"],
            deadline=entry["deadline"], priority=entry["priority"],
            time_remaining=entry["time_remaining"], status=entry["status"],
            source_text=text,
        ))
    db.session.add(SummaryHistory(
        source_text=text, short_summary=summary["short_summary"],
        bullets="\n".join(summary["bullets"]), highlights="\n".join(summary["highlights"]),
    ))
    db.session.commit()
    reminder_job()
    return jsonify({"summary": summary, "tasks": [task_to_dict(t) for t in sorted_tasks_query()]})


@app.route("/api/tasks", methods=["GET"])
def get_tasks():
    return jsonify([task_to_dict(t) for t in sorted_tasks_query()])


@app.route("/api/tasks/<int:task_id>/complete", methods=["PATCH"])
def complete_task(task_id: int):
    task = Task.query.get_or_404(task_id)
    task.status = "completed"
    db.session.commit()
    return jsonify(task_to_dict(task))


@app.route("/api/tasks/<int:task_id>/calendar-link", methods=["GET"])
def task_calendar_link(task_id: int):
    from urllib.parse import urlencode
    task = Task.query.get_or_404(task_id)
    start_at = task.deadline or (now_utc() + timedelta(hours=1))
    end_at = start_at + timedelta(hours=1)
    fmt = lambda dt: dt.strftime("%Y%m%dT%H%M%SZ")
    params = urlencode({
        "action": "TEMPLATE", "text": task.title,
        "dates": f"{fmt(start_at)}/{fmt(end_at)}",
        "details": f"Priority: {task.priority}\nStatus: {task.status}",
    })
    return jsonify({"url": f"https://calendar.google.com/calendar/render?{params}"})


@app.route("/api/today", methods=["GET"])
def get_today_schedule():
    now = now_utc()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)

    today_tasks = Task.query.filter(
        Task.status == "pending",
        Task.deadline >= today_start,
        Task.deadline < today_end,
    ).all()

    if len(today_tasks) < 4:
        extra = sorted(
            Task.query.filter(Task.status == "pending",
                              db.or_(Task.deadline == None, Task.deadline >= today_end)).all(),
            key=lambda t: (priority_rank(t.priority), t.deadline if t.deadline else datetime.max),
        )
        seen_ids = {t.id for t in today_tasks}
        for t in extra:
            if len(today_tasks) >= 4:
                break
            if t.id not in seen_ids:
                today_tasks.append(t)

    for t in today_tasks:
        t.time_remaining = format_time_remaining(t.deadline)

    return jsonify([task_to_dict(t) for t in sorted(
        today_tasks,
        key=lambda t: (priority_rank(t.priority), t.deadline if t.deadline else datetime.max),
    )])


@app.route("/api/history", methods=["GET"])
def get_history():
    items = SummaryHistory.query.order_by(SummaryHistory.created_at.desc()).limit(20).all()
    return jsonify([{
        "id": s.id, "created_at": s.created_at.isoformat(),
        "source_text": s.source_text, "short_summary": s.short_summary,
        "bullets": [b for b in s.bullets.split("\n") if b],
        "highlights": [h for h in s.highlights.split("\n") if h],
    } for s in items])


@app.route("/api/alerts", methods=["GET"])
def get_alerts():
    alerts = ReminderAlert.query.filter_by(seen=False).order_by(ReminderAlert.created_at.desc()).all()
    return jsonify([{
        "id": a.id, "task_id": a.task_id, "message": a.message,
        "created_at": a.created_at.isoformat(),
    } for a in alerts])


@app.route("/api/alerts/<int:alert_id>/seen", methods=["PATCH"])
def mark_alert_seen(alert_id: int):
    alert = ReminderAlert.query.get_or_404(alert_id)
    alert.seen = True
    db.session.commit()
    return jsonify({"status": "ok"})


@app.route("/api/reminders", methods=["GET"])
def get_reminders():
    alerts = ReminderAlert.query.order_by(ReminderAlert.created_at.desc()).limit(50).all()
    return jsonify([{
        "id": a.id, "task_id": a.task_id, "message": a.message,
        "alert_type": a.alert_type, "created_at": a.created_at.isoformat(), "seen": a.seen,
    } for a in alerts])


@app.route("/api/reminders/schedule", methods=["POST"])
def schedule_reminder():
    payload = request.json or {}
    task_id = payload.get("task_id")
    message = (payload.get("message") or "").strip()
    if not task_id or not message:
        return jsonify({"error": "task_id and message are required"}), 400
    task = Task.query.get_or_404(task_id)
    alert = ReminderAlert(task_id=task.id, message=message, alert_type="manual")
    db.session.add(alert)
    # Also push as notification
    _push_notif(task.id, f"📌 Reminder: {task.title}", message, "reminder")
    db.session.commit()
    return jsonify({"status": "scheduled", "id": alert.id})


# ── My Work routes ───────────────────────────────────────────────────────────

@app.route("/api/work", methods=["GET"])
def get_work():
    items = WorkItem.query.order_by(WorkItem.created_at.desc()).all()
    return jsonify([work_to_dict(w) for w in sorted(
        items,
        key=lambda w: (priority_rank(w.priority), w.deadline if w.deadline else datetime.max)
    )])


@app.route("/api/work", methods=["POST"])
def create_work():
    payload = request.json or {}
    title = (payload.get("title") or "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    deadline = None
    if payload.get("deadline"):
        try:
            deadline = date_parser.parse(payload["deadline"])
        except Exception:
            return jsonify({"error": "invalid deadline"}), 400
    priority = payload.get("priority", "Medium")
    if priority not in ("High", "Medium", "Low"):
        priority = "Medium"
    w = WorkItem(
        title=title,
        notes=(payload.get("notes") or "").strip() or None,
        deadline=deadline,
        priority=priority,
    )
    db.session.add(w)
    db.session.commit()
    reminder_job()
    return jsonify(work_to_dict(w)), 201


@app.route("/api/work/<int:work_id>/complete", methods=["PATCH"])
def complete_work(work_id: int):
    w = WorkItem.query.get_or_404(work_id)
    w.status = "completed"
    db.session.commit()
    return jsonify(work_to_dict(w))


@app.route("/api/work/<int:work_id>", methods=["DELETE"])
def delete_work(work_id: int):
    w = WorkItem.query.get_or_404(work_id)
    db.session.delete(w)
    db.session.commit()
    return jsonify({"status": "deleted"})


# ── Gmail routes ─────────────────────────────────────────────────────────────

@app.route("/api/gmail/status", methods=["GET"])
def gmail_status():
    user = os.getenv("GMAIL_USER", "").strip()
    pwd = os.getenv("GMAIL_APP_PASSWORD", "").strip()
    if not user or not pwd:
        return jsonify({"connected": False, "error": "GMAIL_USER or GMAIL_APP_PASSWORD not set"})
    return jsonify({"connected": True, "email": user})


@app.route("/api/gmail/sync", methods=["POST"])
def gmail_sync():
    user = os.getenv("GMAIL_USER", "").strip()
    if not user:
        return jsonify({"error": "Gmail not configured"}), 400
    added, err = gmail_poll_job()
    if err:
        return jsonify({"error": err}), 400
    return jsonify({"status": "synced", "added": added})


@app.route("/api/gmail/emails", methods=["GET"])
def gmail_emails():
    # Only return emails that actually resulted in tasks being added
    emails = GmailMessage.query.filter(GmailMessage.tasks_added > 0).order_by(GmailMessage.received_at.desc()).limit(30).all()
    return jsonify([{
        "id": e.id, "subject": e.subject or "(no subject)",
        "sender": e.sender or "", "snippet": e.snippet or "",
        "tasks_added": e.tasks_added, "received_at": e.received_at.isoformat(),
    } for e in emails])


@app.route("/api/tasks/<int:task_id>/deadline", methods=["PATCH"])
def set_task_deadline(task_id: int):
    task = Task.query.get_or_404(task_id)
    payload = request.json or {}
    raw = (payload.get("deadline") or "").strip()
    if not raw:
        return jsonify({"error": "deadline is required"}), 400
    try:
        task.deadline = date_parser.parse(raw)
    except Exception:
        return jsonify({"error": "invalid deadline format"}), 400
    task.priority = detect_priority(task.title, task.deadline)
    task.time_remaining = format_time_remaining(task.deadline)
    db.session.commit()
    reminder_job()
    return jsonify(task_to_dict(task))


# ── Notification routes ───────────────────────────────────────────────────────

@app.route("/api/notifications", methods=["GET"])
def get_notifications():
    notifs = Notification.query.order_by(Notification.created_at.desc()).limit(100).all()
    return jsonify([notif_to_dict(n) for n in notifs])


@app.route("/api/notifications/unseen-count", methods=["GET"])
def unseen_count():
    return jsonify({"count": Notification.query.filter_by(seen=False).count()})


@app.route("/api/notifications/<int:notif_id>/seen", methods=["PATCH"])
def mark_notif_seen(notif_id: int):
    n = Notification.query.get_or_404(notif_id)
    n.seen = True
    db.session.commit()
    return jsonify({"status": "ok"})


@app.route("/api/notifications/mark-all-seen", methods=["PATCH"])
def mark_all_notifs_seen():
    Notification.query.filter_by(seen=False).update({"seen": True})
    db.session.commit()
    return jsonify({"status": "ok"})


@app.route("/api/notifications/clear", methods=["DELETE"])
def clear_notifications():
    Notification.query.filter_by(seen=True).delete()
    db.session.commit()
    return jsonify({"status": "cleared"})


# ── Init ──────────────────────────────────────────────────────────────────────

# Global sync baseline to ignore past emails.
# Only process emails received AFTER the server started.
APP_START_TIME = datetime.utcnow()

with app.app_context():
    db.create_all()

scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(reminder_job, "interval", seconds=60)
scheduler.add_job(gmail_poll_job, "interval", seconds=300)
scheduler.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

import re
from datetime import datetime
from typing import List, Optional

from app.models import TaskItem


ACTION_VERBS = {
    "submit",
    "finish",
    "complete",
    "prepare",
    "review",
    "read",
    "write",
    "build",
    "send",
    "call",
    "schedule",
    "meet",
}


def _detect_due_date(line: str) -> Optional[str]:
    patterns = [
        r"\b(\d{4}-\d{2}-\d{2})\b",
        r"\b(\d{1,2}/\d{1,2}/\d{2,4})\b",
        r"\b(by|before|due)\s+(tomorrow|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, line, flags=re.IGNORECASE)
        if match:
            return match.group(1) if match.lastindex else match.group(0)
    return None


def _detect_priority(line: str) -> str:
    lowered = line.lower()
    if any(k in lowered for k in ["urgent", "asap", "immediately", "high priority"]):
        return "high"
    if any(k in lowered for k in ["later", "optional", "low priority"]):
        return "low"
    return "medium"


def _detect_category(line: str) -> str:
    lowered = line.lower()
    if any(k in lowered for k in ["assignment", "homework", "submit"]):
        return "assignment"
    if any(k in lowered for k in ["exam", "test", "quiz", "midterm", "final"]):
        return "exam"
    if any(k in lowered for k in ["project", "presentation", "report"]):
        return "project"
    if any(k in lowered for k in ["read", "revise", "study", "practice"]):
        return "study"
    return "general"


def _detect_course(line: str) -> Optional[str]:
    # Examples: "CS101", "MATH-201", "phy102"
    match = re.search(r"\b([A-Za-z]{2,6}-?\d{2,4})\b", line)
    return match.group(1).upper() if match else None


def _estimate_minutes(category: str, priority: str) -> int:
    base = {
        "assignment": 90,
        "exam": 120,
        "project": 150,
        "study": 60,
        "general": 45,
    }.get(category, 45)
    if priority == "high":
        return base + 30
    if priority == "low":
        return max(25, base - 15)
    return base


def extract_tasks(text: str) -> List[TaskItem]:
    lines = [l.strip("-* \t") for l in text.splitlines() if l.strip()]
    tasks: List[TaskItem] = []
    seen = set()

    for line in lines:
        lowered = line.lower()
        looks_like_task = (
            lowered.startswith(("todo", "task", "action"))
            or any(v in lowered for v in ACTION_VERBS)
            or bool(re.search(r"\bmust\b|\bneed to\b|\bshould\b", lowered))
        )
        if not looks_like_task:
            continue

        cleaned = re.sub(r"^(todo|task|action)[:\- ]*", "", line, flags=re.IGNORECASE).strip()
        title = cleaned[:120]
        if not title or title.lower() in seen:
            continue

        due_date = _detect_due_date(line)
        priority = _detect_priority(line)
        category = _detect_category(line)
        course = _detect_course(line)
        tasks.append(
            TaskItem(
                title=title,
                due_date=due_date,
                priority=priority,
                category=category,
                course=course,
                estimated_minutes=_estimate_minutes(category, priority),
                source=f"extracted-{datetime.utcnow().date().isoformat()}",
            )
        )
        seen.add(title.lower())

    return tasks

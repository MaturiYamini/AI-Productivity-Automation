import uuid
from datetime import datetime, timedelta
from typing import Dict


class ReminderStore:
    def __init__(self) -> None:
        self._data: Dict[str, dict] = {}

    def create(self, title: str, due_date: datetime, remind_before_hours: int, channel: str) -> dict:
        reminder_id = str(uuid.uuid4())
        reminder_at = due_date - timedelta(hours=remind_before_hours)
        payload = {
            "reminder_id": reminder_id,
            "title": title,
            "due_date": due_date,
            "reminder_at": reminder_at,
            "channel": channel,
            "status": "scheduled",
        }
        self._data[reminder_id] = payload
        return payload

    def get(self, reminder_id: str) -> dict:
        return self._data[reminder_id]


reminder_store = ReminderStore()

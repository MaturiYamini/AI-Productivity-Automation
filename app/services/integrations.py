import uuid
from typing import Dict


class CalendarIntegration:
    def __init__(self) -> None:
        self._events: Dict[str, dict] = {}

    def create_event(self, platform: str, payload: dict) -> dict:
        # Mock event creation for demo; can be replaced with Google/Microsoft SDK calls.
        event_id = f"{platform}-{uuid.uuid4()}"
        self._events[event_id] = payload
        return {"event_id": event_id, "platform": platform, "status": "created"}


calendar_integration = CalendarIntegration()

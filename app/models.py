from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class SummarizeRequest(BaseModel):
    text: str = Field(..., min_length=20, description="Lecture/email/document text")
    max_sentences: int = Field(default=4, ge=1, le=10)


class SummarizeResponse(BaseModel):
    summary: str
    sentence_count: int


class TaskItem(BaseModel):
    title: str
    due_date: Optional[str] = None
    priority: str = "medium"
    category: str = "general"
    course: Optional[str] = None
    estimated_minutes: int = 45
    source: str = "auto"


class TaskExtractionRequest(BaseModel):
    text: str = Field(..., min_length=10)


class TaskExtractionResponse(BaseModel):
    tasks: List[TaskItem]


class ReminderRequest(BaseModel):
    title: str
    due_date: datetime
    remind_before_hours: int = Field(default=24, ge=1, le=168)
    channel: str = Field(default="console", description="console|webhook")
    webhook_url: Optional[str] = None


class ReminderResponse(BaseModel):
    reminder_id: str
    reminder_at: datetime
    status: str


class CalendarEventRequest(BaseModel):
    title: str
    start_time: datetime
    end_time: datetime
    description: Optional[str] = None
    platform: str = Field(default="mock", description="mock|google")


class CalendarEventResponse(BaseModel):
    event_id: str
    platform: str
    status: str


class StudentWorkflowRequest(BaseModel):
    text: str = Field(..., min_length=20, description="Class notes, announcements, or messages")
    max_summary_sentences: int = Field(default=3, ge=1, le=10)


class StudentWorkflowResponse(BaseModel):
    summary: str
    tasks: List[TaskItem]
    scheduled_reminders: List[ReminderResponse]

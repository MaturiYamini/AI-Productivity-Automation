from datetime import datetime

from fastapi import FastAPI, HTTPException

from app.models import (
    CalendarEventRequest,
    CalendarEventResponse,
    ReminderRequest,
    ReminderResponse,
    StudentWorkflowRequest,
    StudentWorkflowResponse,
    SummarizeRequest,
    SummarizeResponse,
    TaskExtractionRequest,
    TaskExtractionResponse,
)
from app.services.integrations import calendar_integration
from app.services.reminder_scheduler import reminder_store
from app.services.summarizer import summarize_text
from app.services.task_extractor import extract_tasks

app = FastAPI(title="TRAE Productivity Assistant", version="1.0.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/summarize", response_model=SummarizeResponse)
def summarize(payload: SummarizeRequest) -> SummarizeResponse:
    summary = summarize_text(payload.text, payload.max_sentences)
    return SummarizeResponse(summary=summary, sentence_count=len(summary.split(".")))


@app.post("/tasks/extract", response_model=TaskExtractionResponse)
def tasks_extract(payload: TaskExtractionRequest) -> TaskExtractionResponse:
    tasks = extract_tasks(payload.text)
    return TaskExtractionResponse(tasks=tasks)


@app.post("/reminders/schedule", response_model=ReminderResponse)
def schedule_reminder(payload: ReminderRequest) -> ReminderResponse:
    if payload.channel == "webhook" and not payload.webhook_url:
        raise HTTPException(status_code=400, detail="webhook_url is required for webhook channel")
    reminder = reminder_store.create(
        title=payload.title,
        due_date=payload.due_date,
        remind_before_hours=payload.remind_before_hours,
        channel=payload.channel,
    )
    return ReminderResponse(
        reminder_id=reminder["reminder_id"],
        reminder_at=reminder["reminder_at"],
        status=reminder["status"],
    )


@app.post("/integrations/calendar/events", response_model=CalendarEventResponse)
def create_calendar_event(payload: CalendarEventRequest) -> CalendarEventResponse:
    if payload.end_time <= payload.start_time:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")
    event = calendar_integration.create_event(
        platform=payload.platform,
        payload={
            "title": payload.title,
            "start_time": payload.start_time.isoformat(),
            "end_time": payload.end_time.isoformat(),
            "description": payload.description,
        },
    )
    return CalendarEventResponse(**event)


@app.post("/student/workflow", response_model=StudentWorkflowResponse)
def student_workflow(payload: StudentWorkflowRequest) -> StudentWorkflowResponse:
    summary = summarize_text(payload.text, payload.max_summary_sentences)
    tasks = extract_tasks(payload.text)
    scheduled_reminders = []

    for task in tasks:
        if not task.due_date:
            continue
        # Auto-schedule reminders for explicit YYYY-MM-DD due dates.
        try:
            due_date = datetime.strptime(task.due_date, "%Y-%m-%d")
        except ValueError:
            continue
        reminder = reminder_store.create(
            title=f"[Student] {task.title}",
            due_date=due_date,
            remind_before_hours=24,
            channel="console",
        )
        scheduled_reminders.append(
            ReminderResponse(
                reminder_id=reminder["reminder_id"],
                reminder_at=reminder["reminder_at"],
                status=reminder["status"],
            )
        )

    return StudentWorkflowResponse(
        summary=summary,
        tasks=tasks,
        scheduled_reminders=scheduled_reminders,
    )

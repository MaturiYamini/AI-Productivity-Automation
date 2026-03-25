
# AI-based-Productivity-and-Automation
# TRAE AI Productivity Assistant

This project implements an AI productivity assistant that automates everyday workflows:

1. Automatically summarize lectures, emails, or documents
2. Generate smart task lists from notes/messages
3. Schedule reminders from deadlines/conversations
4. Integrate with calendar workflows (mock-ready for real platforms)

## Student Perspective (Project Framing)

This implementation is tuned for students:

- Summarizes lecture notes, class announcements, and long study material.
- Extracts assignment/exam/project tasks from notes or teacher messages.
- Detects simple course codes (like `CS101`, `MATH-201`) in task lines.
- Auto-creates reminders for parsed `YYYY-MM-DD` due dates.
- Supports calendar event creation for class schedules and study sessions.

## Tech Stack

- Python 3.10+
- FastAPI
- Uvicorn

## Run Locally

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

API docs: `http://127.0.0.1:8000/docs`

## Feature 1: Auto Summarization

`POST /summarize`

```json
{
  "text": "Long lecture/email/document text here...",
  "max_sentences": 3
}
```

Returns a concise extractive summary.

## Feature 2: Smart Task List Generation

`POST /tasks/extract`

```json
{
  "text": "Need to submit assignment by 2026-03-30. Also review chapter 5 tomorrow. Urgent: prepare presentation."
}
```

Returns extracted tasks with priority and optional due hints.

## Feature 3: Reminder Scheduling

`POST /reminders/schedule`

```json
{
  "title": "Assignment submission",
  "due_date": "2026-03-30T20:00:00",
  "remind_before_hours": 24,
  "channel": "console"
}
```

Creates a scheduled reminder record.

## Feature 4: Calendar Integration

`POST /integrations/calendar/events`

```json
{
  "title": "Project review meeting",
  "start_time": "2026-03-28T14:00:00",
  "end_time": "2026-03-28T15:00:00",
  "description": "Weekly sync",
  "platform": "mock"
}
```

Creates a calendar event through a mock integration layer that can be upgraded to Google Calendar or Outlook.

## Student All-in-One Endpoint

`POST /student/workflow`

Use one endpoint for student note processing:
- summary generation
- smart task extraction with category/course/effort
- automatic reminder scheduling (when due date format is `YYYY-MM-DD`)

Example:

```json
{
  "text": "CS101 assignment: submit lab report by 2026-03-30. Need to revise for math quiz on monday. Urgent: prepare project presentation.",
  "max_summary_sentences": 3
}
```

## Suggested Next Upgrade

- Replace mock integration with Google Calendar API
- Add WhatsApp/Telegram/Slack reminder delivery
- Add LLM provider integration for abstractive summaries


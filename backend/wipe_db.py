
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'assistant.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Completely clear all tasks and Gmail logs for a fresh start
cursor.execute("DELETE FROM task")
cursor.execute("DELETE FROM gmail_message")
cursor.execute("DELETE FROM notification")
cursor.execute("DELETE FROM summary_history")
cursor.execute("DELETE FROM reminder_alert")
cursor.execute("DELETE FROM work_item")

print(f"Cleared all tables for a fresh start.")

conn.commit()
conn.close()
print("Wipe complete.")

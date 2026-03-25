
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'assistant.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Delete all tasks that came from Gmail (they have source_text containing email subject/body)
# Also clear the processed GmailMessage list to allow a fresh start from now
cursor.execute("DELETE FROM task WHERE source_text LIKE '%Subject:%' OR source_text LIKE '%\n%'")
print(f"Removed {cursor.rowcount} tasks derived from emails.")

cursor.execute("DELETE FROM gmail_message")
print(f"Cleared {cursor.rowcount} email records.")

conn.commit()
conn.close()
print("All past Gmail data cleared.")

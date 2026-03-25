
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'assistant.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Clean up noise emails that have no tasks
cursor.execute("DELETE FROM gmail_message WHERE tasks_added = 0")
print(f"Removed {cursor.rowcount} noise emails.")

conn.commit()
conn.close()
print("Cleanup complete.")

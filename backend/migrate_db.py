
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'assistant.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

def add_column(table, column, type):
    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {type}")
        print(f"Added column {column} to {table}")
    except sqlite3.OperationalError as e:
        print(f"Skipping {column} in {table}: {e}")

# Check columns for GmailMessage (table name is likely 'gmail_message')
add_column('gmail_message', 'subject', 'VARCHAR(500)')
add_column('gmail_message', 'sender', 'VARCHAR(255)')
add_column('gmail_message', 'snippet', 'TEXT')
add_column('gmail_message', 'tasks_added', 'INTEGER DEFAULT 0')
add_column('gmail_message', 'received_at', 'DATETIME')

conn.commit()
conn.close()
print("Migration complete.")

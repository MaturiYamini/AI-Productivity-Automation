
from app import app, gmail_poll_job
import os
import sys

# Ensure backend folder is in path
sys.path.append(os.path.dirname(__file__))

with app.app_context():
    print("Starting manual sync debug...")
    try:
        added, err = gmail_poll_job()
        if err:
            print(f"Sync failed with error: {err}")
        else:
            print(f"Sync successful. Added {added} tasks.")
    except Exception as e:
        import traceback
        print(f"Sync crashed with exception: {e}")
        traceback.print_exc()

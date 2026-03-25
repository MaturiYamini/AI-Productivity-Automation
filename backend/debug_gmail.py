import sys, os
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv()
import imaplib
import email as emaillib

user = os.getenv('GMAIL_USER', '').strip()
pwd  = os.getenv('GMAIL_APP_PASSWORD', '').strip()
print(f"User: {user}")
print(f"Pwd length: {len(pwd)}")

try:
    mail = imaplib.IMAP4_SSL('imap.gmail.com', 993)
    mail.login(user, pwd)
    print("Login OK")
    mail.select('INBOX')

    # Search ALL recent emails
    _, uids = mail.uid('search', None, 'ALL')
    uid_list = uids[0].split()[-10:]
    print(f"Total emails found: {len(uid_list)}")

    for uid in uid_list:
        _, data = mail.uid('fetch', uid, '(RFC822)')
        msg = emaillib.message_from_bytes(data[0][1])
        subject = msg.get('Subject', '')
        body = ''
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == 'text/plain':
                    body = part.get_payload(decode=True).decode('utf-8', 'ignore')
                    break
        else:
            try:
                body = msg.get_payload(decode=True).decode('utf-8', 'ignore')
            except Exception:
                body = str(msg.get_payload())

        print(f"\nSubject: {subject}")
        print(f"Body: {body[:150]}")

        # Test extraction logic
        subj_lower = subject.lower()
        action_words = [
            "submit", "complete", "finish", "prepare", "review", "send",
            "assignment", "homework", "project", "exam", "quiz", "report",
            "presentation", "deadline", "due", "urgent", "reminder", "task",
        ]
        matched = [w for w in action_words if w in subj_lower]
        print(f"Action words matched in subject: {matched}")
        print(f"Would extract task: {'YES' if matched else 'NO'}")

    mail.logout()
except Exception as e:
    print(f"ERROR: {e}")

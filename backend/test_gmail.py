import sys, os
sys.stdout.reconfigure(encoding='utf-8')
from dotenv import load_dotenv
load_dotenv()
import imaplib

user = os.getenv('GMAIL_USER', '').strip()
pwd  = os.getenv('GMAIL_APP_PASSWORD', '').strip()
print('User:', user)
print('Pwd length:', len(pwd))

try:
    mail = imaplib.IMAP4_SSL('imap.gmail.com', 993)
    r = mail.login(user, pwd)
    print('Login OK:', r)
    mail.select('INBOX')
    _, uids = mail.uid('search', None, 'UNSEEN')
    count = len(uids[0].split()) if uids[0] else 0
    print('Unread emails:', count)
    mail.logout()
except Exception as e:
    print('FAIL:', e)

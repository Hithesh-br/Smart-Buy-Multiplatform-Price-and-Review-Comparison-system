import imaplib
import os
import sys
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(override=True)
smtp_user = os.getenv("SMTP_USER")
smtp_pass = os.getenv("SMTP_PASSWORD")

try:
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(smtp_user, smtp_pass)
    mail.select('"[Gmail]/Sent Mail"')
    status, search_data = mail.search(None, 'TO', '"hitheshharsha6@gmail.com"')
    mids = search_data[0].split()
    print(f"Total sent emails to hitheshharsha6@gmail.com: {len(mids)}")
    for mid in mids[-10:]:
        status, mdata = mail.fetch(mid, '(BODY[HEADER.FIELDS (SUBJECT TO DATE MESSAGE-ID)])')
        header_text = mdata[0][1].decode("utf-8", errors="ignore").strip().replace("\r\n", " | ")
        print(f"{mid.decode()}: {header_text}")
    mail.logout()
except Exception as e:
    print(f"IMAP Error: {e}")

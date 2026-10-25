import imaplib
import os
import sys
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()
user = os.getenv("SMTP_USER")
pwd = os.getenv("SMTP_PASSWORD")

try:
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(user, pwd)
    mail.select('"[Gmail]/Sent Mail"')
    status, data = mail.search(None, 'TO', '"hitheshharsha486@gmail.com"')
    mids = data[0].split()
    print(f"Total emails sent to hitheshharsha486@gmail.com: {len(mids)}")

    for mid in mids[-10:]:
        status, mdata = mail.fetch(mid, "(BODY[HEADER.FIELDS (SUBJECT DATE)])")
        header = mdata[0][1].decode("utf-8", errors="ignore").strip().replace("\r\n", " | ")
        print(f"{mid.decode()}: {header}")

    mail.logout()
except Exception as e:
    print(f"IMAP Error: {e}")

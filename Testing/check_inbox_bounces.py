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
    mail.select("INBOX")
    status, data = mail.search(None, "ALL")
    mids = data[0].split()
    print(f"Total emails in buysmart260 INBOX: {len(mids)}")
    for mid in mids[-10:]:
        status, mdata = mail.fetch(mid, "(BODY[HEADER.FIELDS (FROM SUBJECT DATE)])")
        header = mdata[0][1].decode("utf-8", errors="ignore").strip().replace("\r\n", " | ")
        print(f"{mid.decode()}: {header}")
    mail.logout()
except Exception as e:
    print(f"Error checking inbox: {e}")

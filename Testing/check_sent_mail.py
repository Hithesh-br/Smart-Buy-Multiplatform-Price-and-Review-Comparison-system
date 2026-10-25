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
    print(f"IMAP Login Successful for {user}")

    # Select Sent folder
    status, count = mail.select('"[Gmail]/Sent Mail"')
    print(f"Sent folder status: {status}, Total count: {count}")

    # Fetch last 5 sent messages
    status, data = mail.search(None, "ALL")
    msg_ids = data[0].split()
    print(f"Total sent messages found: {len(msg_ids)}")

    for mid in msg_ids[-5:]:
        status, mdata = mail.fetch(mid, "(BODY[HEADER.FIELDS (TO FROM SUBJECT DATE)])")
        print("\n--- Message ID:", mid.decode())
        print(mdata[0][1].decode("utf-8", errors="ignore").strip())

    mail.logout()
except Exception as e:
    print(f"IMAP Error: {e}")

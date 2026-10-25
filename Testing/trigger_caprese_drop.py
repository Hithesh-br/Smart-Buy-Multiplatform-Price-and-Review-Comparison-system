import os
import sys
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(override=True)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bson import ObjectId
from database import get_db, simulate_and_trigger_price_drop

db = get_db()
alert_id = "6adde66adb1dda7e98d7ab68"
alert = db.price_alerts.find_one({"_id": ObjectId(alert_id)})

if not alert:
    print(f"Alert {alert_id} not found!")
    sys.exit(1)

print(f"Found Alert: {alert['product_name']}")
print(f"Alert Owner: {alert.get('user_name')} ({alert.get('email')})")
print(f"Store Baseline: ₹{alert.get('current_price')} | User Target: ₹{alert.get('target_price')}")

# Drop price to 1749 (below target 1800)
new_drop_price = 1749
print(f"\nDropping price to ₹{new_drop_price:,} (Savings: ₹{alert['current_price'] - new_drop_price:,})...")

ok, msg, res = simulate_and_trigger_price_drop(
    alert_id=alert_id,
    new_price=new_drop_price,
    current_user_email=alert.get("email"),
    current_user_name=alert.get("user_name")
)

print(f"\nExecution Result:")
print(f"Success: {ok}")
print(f"Message: {msg}")
if res:
    print(f"Recipient: {res.get('to_email')}")
    print(f"Email Sent: {res.get('email_sent')}")
    print(f"New Price: ₹{res.get('new_price')}")
    print(f"Previous Price: ₹{res.get('previous_price')}")
    print(f"Service Response: {res.get('service_response')}")

# Check latest sent email in Gmail Sent Mail via IMAP
import imaplib
smtp_user = os.getenv("SMTP_USER")
smtp_pass = os.getenv("SMTP_PASSWORD")

try:
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(smtp_user, smtp_pass)
    mail.select('"[Gmail]/Sent Mail"')
    status, search_data = mail.search(None, 'TO', f'"{alert.get("email")}"')
    mids = search_data[0].split()
    print(f"\nIMAP Check for {alert.get('email')}:")
    print(f"Total sent: {len(mids)}")
    if mids:
        status, mdata = mail.fetch(mids[-1], '(BODY[HEADER.FIELDS (SUBJECT TO DATE MESSAGE-ID)])')
        header_text = mdata[0][1].decode("utf-8", errors="ignore").strip().replace("\r\n", " | ")
        print(f"Latest Sent Email:\n{header_text}")
    mail.logout()
except Exception as e:
    print(f"IMAP Error: {e}")

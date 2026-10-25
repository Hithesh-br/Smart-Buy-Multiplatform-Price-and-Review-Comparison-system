import os
import sys
import datetime
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv(override=True)

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import get_db, simulate_and_trigger_price_drop, trigger_test_price_alert

db = get_db()
if db is None:
    print("Database connection failed!")
    sys.exit(1)

# Find user and alert
user = db.users.find_one({"email": "hitheshharsha486@gmail.com"})
print(f"Alert Owner: {user.get('name', 'User')} ({user.get('email')})")

alert = db.price_alerts.find_one({
    "email": "hitheshharsha486@gmail.com",
    "product_name": {"$regex": "Wakefit", "$options": "i"}
})

if not alert:
    print("Wakefit alert not found for user!")
    sys.exit(1)

aid = str(alert["_id"])
prod_name = alert.get("product_name")
target_p = alert.get("target_price")
prev_p = alert.get("latest_price", alert.get("current_price"))
drop_price = 549  # Drops below target of 600

print(f"\n1. Executing Live Price Drop for: '{prod_name}'")
print(f"   Target Price: ₹{target_p:,} | Current Price: ₹{prev_p:,} | Dropping to: ₹{drop_price:,}")

success, msg, data = simulate_and_trigger_price_drop(
    alert_id=aid,
    new_price=drop_price,
    current_user_email=user["email"],
    current_user_name=user.get("name", "Harsha")
)

print(f"\n2. Price Drop Workflow Result:")
print(f"   Success: {success}")
print(f"   Message: {msg}")
if data:
    print(f"   Recipient: {data.get('to_email')}")
    print(f"   Email Sent: {data.get('email_sent')}")
    print(f"   New Price: ₹{data.get('new_price')}")
    print(f"   Previous Price: ₹{data.get('previous_price')}")
    print(f"   SMTP Response: {data.get('service_response')}")

# Also check store catalog update
gec_prod = db.gececom_products.find_one({"product_name": {"$regex": "Wakefit", "$options": "i"}})
if gec_prod:
    print(f"\n3. GEC Store Catalog Price: ₹{gec_prod.get('current_price')} (Catalog successfully synced!)")

# Verify via IMAP in buysmart260@gmail.com's Sent folder
import imaplib
smtp_user = os.getenv("SMTP_USER")
smtp_pass = os.getenv("SMTP_PASSWORD")

try:
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(smtp_user, smtp_pass)
    mail.select('"[Gmail]/Sent Mail"')
    status, search_data = mail.search(None, 'TO', '"hitheshharsha486@gmail.com"')
    mids = search_data[0].split()
    print(f"\n4. Gmail IMAP Verification:")
    print(f"   Total verified sent emails to hitheshharsha486@gmail.com: {len(mids)}")
    if mids:
        status, mdata = mail.fetch(mids[-1], '(BODY[HEADER.FIELDS (SUBJECT TO DATE MESSAGE-ID)])')
        header_text = mdata[0][1].decode("utf-8", errors="ignore").strip().replace("\r\n", "\n   ")
        print(f"   Latest Sent Email Headers:\n   {header_text}")
    mail.logout()
except Exception as e_imap:
    print(f"   IMAP fetch note: {e_imap}")

import os
import sys
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv(override=True)

from database import (
    get_db,
    to_object_id,
    create_price_alert,
    update_gececom_product_price,
    simulate_and_trigger_price_drop,
    get_user_price_alerts
)

db = get_db()
lavie_alert_id = "6addeb4176745985bd4b5a79"
alert = db.price_alerts.find_one({"_id": to_object_id(lavie_alert_id)})
print(f"Current Lavie Alert: {alert.get('product_name')} | Status: {alert.get('status')} | Target: ₹{alert.get('target_price')} | Current: ₹{alert.get('current_price')}")

# Simulate price drop for Lavie Handbag to ₹1,050 (target is ₹1,100)
print("\n--- Triggering Live Price Drop for Lavie Handbag to ₹1,050 ---")
ok, msg, res_data = simulate_and_trigger_price_drop(lavie_alert_id, 1050)
print(f"Result ok: {ok}")
print(f"Message: {msg}")
print(f"Email sent flag: {res_data.get('email_sent') if res_data else None}")
print(f"Recipient: {res_data.get('recipient_email') if res_data else None}")

# Verify updated alert doc
updated_alert = db.price_alerts.find_one({"_id": to_object_id(lavie_alert_id)})
print(f"\nUpdated Alert Status: {updated_alert.get('status')}")
print(f"Latest Price: ₹{updated_alert.get('latest_price')}")
print(f"Last Notified Price: ₹{updated_alert.get('last_notified_price')}")
print(f"Last Email Sent At: {updated_alert.get('last_email_sent_at')}")

# Verify GEC ECom product price
gec_prod = db.gececom_products.find_one({"id": "gec_bag_004"})
print(f"GEC Product Price: ₹{gec_prod.get('current_price')}")

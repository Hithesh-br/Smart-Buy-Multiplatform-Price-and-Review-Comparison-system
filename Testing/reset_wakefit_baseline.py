import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import get_db, get_user_price_alerts

db = get_db()
if db is not None:
    # Set store product price to baseline 699
    db.gececom_products.update_many(
        {"product_name": {"$regex": "Wakefit.*Pillows", "$options": "i"}},
        {"$set": {"current_price": 699}}
    )
    # Set price alerts to monitoring at baseline 699
    db.price_alerts.update_many(
        {"product_name": {"$regex": "Wakefit.*Pillows", "$options": "i"}},
        {"$set": {
            "latest_price": 699,
            "previous_price": 699,
            "status": "monitoring",
            "notification_status": "monitoring",
            "last_notified_price": None
        }}
    )
    print("Baseline reset completed.")
    alerts = get_user_price_alerts("hitheshharsha486@gmail.com")
    for a in alerts:
        if "Wakefit" in a.get("product_name", ""):
            print(a["product_name"][:30], "Latest:", a["latest_price"], "Target:", a["target_price"], "Status:", a["status"], "EmailStatus:", a["notification_status"])

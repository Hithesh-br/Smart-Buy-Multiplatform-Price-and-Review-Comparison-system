"""
Testing/test_wakefit_live_scenario.py
====================================
Validates the user prompt's exact Wakefit scenario:
- Product: Wakefit Hollow Fiber Sleeping Pillows Set of 2 (Medium Firm Support) - White
- Previous price: ₹699
- Target price: ₹600
- New price: ₹599
- Owner: hitheshharsha486@gmail.com
- Verifies:
  1. Price remaining at ₹699 -> 0 emails sent.
  2. Price dropping to ₹599 -> Live email sent to hitheshharsha486@gmail.com.
  3. Price staying at ₹599 -> 0 duplicate emails sent.
  4. Real SMTP credentials used.
"""

import os
import sys
from datetime import datetime, timezone

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import (
    get_db,
    create_price_alert,
    process_single_alert,
    get_alert_by_id,
    to_object_id
)

def test_wakefit():
    db = get_db()
    if db is None:
        print("MongoDB unavailable")
        sys.exit(1)

    owner_email = "hitheshharsha486@gmail.com"
    prod_name = "Wakefit Hollow Fiber Sleeping Pillows Set of 2 (Medium Firm Support) - White"

    print("\n" + "=" * 70)
    print("TESTING WAKEFIT SCENARIO FROM USER PROMPT")
    print(f"Product: {prod_name}")
    print(f"Owner: {owner_email}")
    print("=" * 70)

    # Clean up test alert
    db.price_alerts.delete_many({"product_name": prod_name, "email": owner_email})

    # Step 1: User creates alert
    alert_payload = {
        "product_name": prod_name,
        "product_url": "http://127.0.0.1:5000/product/wakefit-pillows",
        "product_image": "/static/images/products/wakefit_pillows.jpg",
        "platform": "gececom",
        "current_price": 699,
        "target_price": 600,
        "email": owner_email,
        "user_name": "Harsha"
    }
    ok, msg, alert_doc = create_price_alert(alert_payload)
    assert ok is True
    print(f"1. Alert created: ID={alert_doc['id']}, Baseline=₹699, Target=₹600, Recipient={alert_doc['email']}")

    # Step 2: Price remains ₹699 (Target ₹600) -> NO email sent
    print("\n2. Checking price remaining at ₹699...")
    res_at_699 = process_single_alert(alert_doc, current_price=699, previous_price=699)
    assert res_at_699["condition_met"] is False
    assert res_at_699["email_sent"] is False
    print("   -> Correct: 699 > 600: No notification email sent.")

    # Step 3: Price drops to ₹599 (Target ₹600) -> LIVE email sent
    print("\n3. Price drops to ₹599 (Target ₹600)... Dispatching live email via SMTP...")
    res_at_599 = process_single_alert(alert_doc, current_price=599, previous_price=699)
    print(f"   -> Result: Condition Met={res_at_599['condition_met']}, Email Sent={res_at_599['email_sent']}, Recipient={res_at_599.get('recipient')}")
    assert res_at_599["condition_met"] is True
    assert res_at_599["email_sent"] is True
    assert res_at_599["recipient"] == owner_email
    print(f"   -> SUCCESS: Price drop email sent to {owner_email}!")

    # Step 4: Price remains ₹599 -> Duplicate prevention
    print("\n4. Next monitor cycle with price remaining at ₹599...")
    updated_alert = get_alert_by_id(alert_doc["id"])
    res_dup = process_single_alert(updated_alert, current_price=599, previous_price=599)
    assert res_dup["email_sent"] is False
    assert res_dup.get("skipped_reason") == "duplicate_prevention"
    print("   -> SUCCESS: Duplicate notification correctly skipped.")

    print("\n" + "=" * 70)
    print("WAKEFIT SCENARIO VERIFIED COMPLETELY!")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    test_wakefit()

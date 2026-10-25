"""
Testing/test_price_change_sync_and_email.py
============================================
Validates end-to-end synchronization when a price changes or is dropped:
1. Product price updates in MongoDB gececom_products.
2. Search & platform caches are cleared.
3. Live Comparison Table displays the updated price for GEC ECom.
4. Price drop email notification is sent to the registered user (hitheshharsha486@gmail.com).
5. Price alerts dashboard displays the updated price and sent status.
"""

import sys
import re
import os
from unittest.mock import patch

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from database import (
    get_db,
    update_gececom_product_price,
    simulate_and_trigger_price_drop,
    get_all_gececom_products,
    get_user_price_alerts,
)
from app import app
from cache import clear_cache

def run_sync_verification():
    db = get_db()
    if db is None:
        print("[FAIL] Database unavailable.")
        return False

    prod_name = "Wakefit Hollow Fiber Sleeping Pillows Set of 2 (Medium Firm Support) - White"
    prod = db.gececom_products.find_one({"product_name": prod_name})
    if not prod:
        print(f"[FAIL] Product '{prod_name}' not found in gececom_products.")
        return False

    prod_id = str(prod["_id"])
    print(f"Product found: ID={prod_id}, Initial current_price=₹{prod.get('current_price')}")

    # Find the user's price alert for this product
    alert = db.price_alerts.find_one({
        "product_name": prod_name,
        "email": "hitheshharsha486@gmail.com"
    })
    if not alert:
        print("[FAIL] Alert for hitheshharsha486@gmail.com not found.")
        return False

    alert_id = str(alert["_id"])
    target_price = alert.get("target_price", 600)
    print(f"Alert found: ID={alert_id}, Target Price=₹{target_price}, Owner={alert.get('email')}")

    client = app.test_client()

    # Step 1: Search initially before drop and verify Comparison Table price
    clear_cache()
    resp_init = client.get(f"/search?q={prod_name[:25]}")
    html_init = resp_init.get_data(as_text=True)
    print(f"Initial search status: {resp_init.status_code}")
    assert resp_init.status_code == 200, "Search page failed to load"
    
    # Verify baseline price in catalog
    assert prod.get("current_price") == 699, f"Expected initial price 699, got {prod.get('current_price')}"

    # Step 2: Simulate price drop to ₹599 (below target of ₹600)
    print("\n--- Simulating Price Drop to ₹599 ---")
    captured_emails = []

    def mock_send_email_detailed(to_email, subject, body, html):
        captured_emails.append({
            "to_email": to_email,
            "subject": subject,
            "body": body,
            "html": html
        })
        return True, "250 2.0.0 OK (Mocked for verification)"

    with patch("otp_utils.send_email_detailed", side_effect=mock_send_email_detailed):
        ok, msg, res_data = simulate_and_trigger_price_drop(
            alert_id=alert_id,
            new_price=599,
            current_user_email="hitheshharsha486@gmail.com"
        )

    print(f"simulate_and_trigger_price_drop result: ok={ok}, msg={msg}")
    assert ok is True, f"Price drop failed: {msg}"
    assert len(captured_emails) == 1, f"Expected 1 email sent, got {len(captured_emails)}"
    email_entry = captured_emails[0]
    print(f"[VERIFIED] Email dispatched to: {email_entry['to_email']}")
    assert email_entry["to_email"] == "hitheshharsha486@gmail.com", f"Wrong recipient: {email_entry['to_email']}"
    assert "SmartBuy Price Drop Alert" in email_entry["subject"], "Subject mismatch"
    assert "599" in email_entry["body"], "New dropped price not found in email body"

    # Step 3: Check MongoDB gececom_products catalog
    updated_prod = db.gececom_products.find_one({"_id": prod["_id"]})
    print(f"[VERIFIED] GEC ECom Store Catalog price is now: ₹{updated_prod.get('current_price')}")
    assert updated_prod.get("current_price") == 599, f"Expected catalog price 599, got {updated_prod.get('current_price')}"

    # Step 4: Check Price Alert document in db.price_alerts
    updated_alert = db.price_alerts.find_one({"_id": alert["_id"]})
    print(f"[VERIFIED] Alert status: {updated_alert.get('notification_status')}, latest_price: ₹{updated_alert.get('latest_price')}")
    assert updated_alert.get("latest_price") == 599, f"Alert price not updated: {updated_alert.get('latest_price')}"
    assert updated_alert.get("notification_status") == "sent", "Alert status not sent"

    # Step 5: Query Comparison Table (/search) and verify that it immediately displays ₹599!
    print("\n--- Querying Comparison Table for updated price ---")
    resp_updated = client.get(f"/search?q={prod_name[:25]}")
    html_updated = resp_updated.get_data(as_text=True)
    assert resp_updated.status_code == 200, "Updated search page failed to load"

    # Check for ₹599 in comparison table
    has_599 = "599" in html_updated
    print(f"[VERIFIED] Comparison Table contains updated price ₹599: {has_599}")
    assert has_599, "Comparison Table did not display the updated price ₹599!"

    # Step 6: Reset baseline price back to ₹699
    print("\n--- Resetting baseline price back to ₹699 ---")
    update_gececom_product_price(prod_id, 699, product_name=prod_name)
    reset_prod = db.gececom_products.find_one({"_id": prod["_id"]})
    print(f"[VERIFIED] Reset complete. Catalog price is now: ₹{reset_prod.get('current_price')}")
    assert reset_prod.get("current_price") == 699, "Failed to reset price to 699"

    print("\n=======================================================")
    print("ALL TESTS PASSED: Price change synchronization verified!")
    print("=======================================================")
    return True

if __name__ == "__main__":
    success = run_sync_verification()
    sys.exit(0 if success else 1)

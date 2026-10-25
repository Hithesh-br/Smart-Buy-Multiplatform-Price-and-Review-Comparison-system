"""
test_user_recipient_workflow.py
================================
Validates Section 8:
- Two different user accounts (User A and User B) with two registered email addresses.
- Both users create alerts on Product X (User A target: Rs. 1,000; User B target: Rs. 800).
- Price drops to Rs. 900:
    - User A receives email (900 <= 1000).
    - User B does NOT receive email (900 > 800).
- Price drops to Rs. 800:
    - User B receives email (800 <= 800).
    - User A must NOT receive a duplicate email.
- Verifies test email trigger endpoint routes to alert owner's registered email.
"""

import sys
import os
from bson import ObjectId
from werkzeug.security import generate_password_hash

# Ensure workspace root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Ensure stdout/stderr handle UTF-8
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

from app import app
from database import (
    get_db,
    create_user,
    get_user_by_email,
    get_user_by_id,
    get_alert_by_id,
    add_gececom_product,
    update_gececom_product_price,
    trigger_test_price_alert
)

client = app.test_client()

def run_recipient_workflow_test():
    db = get_db()
    if db is None:
        print("[FAIL] Database unavailable.")
        sys.exit(1)

    print("=" * 80)
    print("RUNNING SMARTBUY USER RECIPIENT & MULTI-USER ISOLATION TEST (SECTION 8)")
    print("=" * 80)

    # 1. Setup User A & User B
    email_a = "alice_usera_smartbuy@example.com"
    email_b = "bob_userb_smartbuy@example.com"

    user_a = get_user_by_email(email_a)
    if not user_a:
        uid_a, _, _ = create_user("Alice UserA", email_a, generate_password_hash("Password@123"), phone="9876543210")
        user_a = get_user_by_id(uid_a)
    user_a_id = str(user_a.get("id") or user_a.get("_id"))

    user_b = get_user_by_email(email_b)
    if not user_b:
        uid_b, _, _ = create_user("Bob UserB", email_b, generate_password_hash("Password@123"), phone="9876543211")
        user_b = get_user_by_id(uid_b)
    user_b_id = str(user_b.get("id") or user_b.get("_id"))

    print(f"User A: ID={user_a_id} | Name={user_a.get('name')} | Registered Email={user_a.get('email')}")
    print(f"User B: ID={user_b_id} | Name={user_b.get('name')} | Registered Email={user_b.get('email')}")
    print("-" * 80)

    # 2. Setup Product X in GEC ECom Store
    prod_name = "Product X Special Edition Smartphone"
    prod = db.gececom_products.find_one({"product_name": prod_name})
    if not prod:
        prod = add_gececom_product({
            "name": prod_name,
            "product_name": prod_name,
            "current_price": 1200,
            "original_price": 1200,
            "category": "mobiles"
        })
    prod_id = str(prod.get("_id") or prod.get("id"))
    update_gececom_product_price(prod_id, 1200)
    print(f"Product X: ID={prod_id} | Name={prod_name} | Baseline Price=Rs. 1,200")
    print("-" * 80)

    # Clean existing alerts for Product X by these test users
    db.price_alerts.delete_many({
        "product_id": {"$in": [prod_id, str(prod_id)]},
        "email": {"$in": [email_a, email_b]}
    })

    # 3. User A logs in and creates alert (Target: Rs. 1,000)
    with client.session_transaction() as sess:
        sess['user_id'] = user_a_id
        sess['user_name'] = user_a.get('name')

    resp_a = client.post('/api/price-alerts', json={
        "product_id": prod_id,
        "product_name": prod_name,
        "current_price": 1200,
        "target_price": 1000,
        "alert_mode": "price",
        "platform": "gececom",
        "product_url": f"/gececom#product-{prod_id}"
    })
    data_a = resp_a.get_json()
    alert_a_id = data_a.get("alert", {}).get("id")
    print(f"User A Alert Created: ID={alert_a_id} | Target=Rs. 1,000 | Resp Status={resp_a.status_code}")

    # Verify User A alert in DB has user_id and registered email
    doc_a = get_alert_by_id(alert_a_id)
    assert doc_a is not None, "User A alert not found in DB"
    assert doc_a.get("user_id") == user_a_id, f"Alert user_id {doc_a.get('user_id')} != {user_a_id}"
    assert doc_a.get("email") == email_a, f"Alert email {doc_a.get('email')} != {email_a}"
    print(f"  [Verified] Alert {alert_a_id} correctly linked to User A ({user_a_id}) -> {email_a}")

    # 4. User B logs in and creates alert (Target: Rs. 800)
    with client.session_transaction() as sess:
        sess['user_id'] = user_b_id
        sess['user_name'] = user_b.get('name')

    resp_b = client.post('/api/price-alerts', json={
        "product_id": prod_id,
        "product_name": prod_name,
        "current_price": 1200,
        "target_price": 800,
        "alert_mode": "price",
        "platform": "gececom",
        "product_url": f"/gececom#product-{prod_id}"
    })
    data_b = resp_b.get_json()
    alert_b_id = data_b.get("alert", {}).get("id")
    print(f"User B Alert Created: ID={alert_b_id} | Target=Rs. 800 | Resp Status={resp_b.status_code}")

    # Verify User B alert in DB has user_id and registered email
    doc_b = get_alert_by_id(alert_b_id)
    assert doc_b is not None, "User B alert not found in DB"
    assert doc_b.get("user_id") == user_b_id, f"Alert user_id {doc_b.get('user_id')} != {user_b_id}"
    assert doc_b.get("email") == email_b, f"Alert email {doc_b.get('email')} != {email_b}"
    print(f"  [Verified] Alert {alert_b_id} correctly linked to User B ({user_b_id}) -> {email_b}")
    print("-" * 80)

    # --------------------------------------------------------------------------
    # 5. STEP 1: Price drops to Rs. 900
    # Expected:
    # - User A receives price-drop email (900 <= 1000 is True)
    # - User B does NOT receive email (900 <= 800 is False)
    # --------------------------------------------------------------------------
    print("\n--- STEP 1: Price drops to Rs. 900 in GEC ECom ---")
    update_res_1 = client.post(f"/api/gececom/products/{prod_id}/price", json={"price": 900}).get_json()
    print(f"Price update to Rs. 900 completed.")

    doc_a_step1 = get_alert_by_id(alert_a_id)
    doc_b_step1 = get_alert_by_id(alert_b_id)

    step1_a_ok = (
        doc_a_step1.get("status") == "email_sent" and
        doc_a_step1.get("notification_status") == "sent" and
        doc_a_step1.get("last_email_sent_at") is not None and
        doc_a_step1.get("latest_price") == 900
    )
    step1_b_ok = (
        doc_b_step1.get("status") == "monitoring" and
        doc_b_step1.get("notification_status") == "monitoring" and
        doc_b_step1.get("last_email_sent_at") is None and
        doc_b_step1.get("latest_price") == 900
    )

    print(f"Step 1 - User A: Status={doc_a_step1.get('status')} | Recipient={doc_a_step1.get('email')} -> {'PASS' if step1_a_ok else 'FAIL'}")
    print(f"Step 1 - User B: Status={doc_b_step1.get('status')} | Recipient={doc_b_step1.get('email')} -> {'PASS' if step1_b_ok else 'FAIL'}")
    assert step1_a_ok and step1_b_ok, "Step 1 verification failed!"

    # --------------------------------------------------------------------------
    # 6. STEP 2: Price drops to Rs. 800
    # Expected:
    # - User B receives price-drop email (800 <= 800 is True)
    # - User A does NOT receive duplicate email (already notified)
    # --------------------------------------------------------------------------
    print("\n--- STEP 2: Price drops to Rs. 800 in GEC ECom ---")
    update_res_2 = client.post(f"/api/gececom/products/{prod_id}/price", json={"price": 800}).get_json()
    print(f"Price update to Rs. 800 completed.")

    doc_a_step2 = get_alert_by_id(alert_a_id)
    doc_b_step2 = get_alert_by_id(alert_b_id)

    step2_b_ok = (
        doc_b_step2.get("status") == "email_sent" and
        doc_b_step2.get("notification_status") == "sent" and
        doc_b_step2.get("last_email_sent_at") is not None and
        doc_b_step2.get("latest_price") == 800
    )
    # User A: last_email_sent_at must NOT have been updated or duplicated
    a_events = doc_a_step2.get("notification_events") or []
    sent_events_a = [e for e in a_events if e.get("event") == "price_drop_email_sent"]
    step2_a_dup_prevention = (len(sent_events_a) == 1)

    print(f"Step 2 - User B: Status={doc_b_step2.get('status')} | Recipient={doc_b_step2.get('email')} -> {'PASS' if step2_b_ok else 'FAIL'}")
    print(f"Step 2 - User A: Total Price-Drop Emails Sent={len(sent_events_a)} -> {'PASS (0 Duplicates)' if step2_a_dup_prevention else 'FAIL'}")
    assert step2_b_ok and step2_a_dup_prevention, "Step 2 verification failed!"

    # --------------------------------------------------------------------------
    # 7. STEP 3: Verify "Send Test Email Now" Button
    # Expected:
    # - Sends test email to alert owner's registered email
    # - Never sends to sender or other user
    # --------------------------------------------------------------------------
    print("\n--- STEP 3: Verify 'Send Test Email Now' Button ---")
    test_ok_a, msg_a, res_a = trigger_test_price_alert(alert_a_id)
    print(f"User A Test Email Trigger: Status={test_ok_a} | Recipient={res_a.get('to_email') if res_a else None}")
    assert test_ok_a and res_a.get("to_email") == email_a, "User A test email recipient mismatch!"

    test_ok_b, msg_b, res_b = trigger_test_price_alert(alert_b_id)
    print(f"User B Test Email Trigger: Status={test_ok_b} | Recipient={res_b.get('to_email') if res_b else None}")
    assert test_ok_b and res_b.get("to_email") == email_b, "User B test email recipient mismatch!"

    # Cleanup test data
    db.price_alerts.delete_many({"_id": {"$in": [ObjectId(alert_a_id), ObjectId(alert_b_id)]}})
    print("\n" + "=" * 80)
    print("ALL RECIPIENT LOGIC & MULTI-USER TESTS (SECTION 8) PASSED PERFECTLY!")
    print("=" * 80)

if __name__ == "__main__":
    run_recipient_workflow_test()

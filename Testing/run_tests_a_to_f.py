"""
run_tests_a_to_f.py
===================
Automated verification script for SmartBuy price alert fixes:
Tests A through F:
- Test A: Target not reached (Target: 20898, New price: 21000 -> No email)
- Test B: Target reached (Target: 20898, New price: 20898 -> Exactly one email sent)
- Test C: Price falls below target (Target: 20898, New price: 20000 -> Exactly one email sent)
- Test D: Test email button (POST /api/price-alerts/<alert_id>/trigger -> Real test email sent, monitoring preserved)
- Test E: Duplicate prevention (Repeated check at same or higher price -> 0 duplicate emails)
- Test F: Multiple users (Two users with separate alerts -> Both receive individual notifications)
"""

import sys
import os
from datetime import datetime, timezone
from bson import ObjectId

# Ensure workspace root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Ensure stdout and stderr handle utf-8 on Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass


from database import (
    get_db,
    update_gececom_product_price,
    get_gececom_product_by_id,
    check_and_trigger_price_alerts,
    trigger_test_price_alert,
    create_price_alert
)

def run_all_tests():
    db = get_db()
    if db is None:
        print("[FAIL] MongoDB not available.")
        sys.exit(1)

    print("=" * 80)
    print("STARTING SMARTBUY PRICE-ALERT VERIFICATION (TESTS A - F)")
    print("=" * 80)

    # 1. Product Setup
    # Find or use the OnePlus Nord CE4 product
    prod_id = "6acfc21430bff10c50ccf750"
    prod = get_gececom_product_by_id(prod_id)
    if not prod:
        prod = db.gececom_products.find_one({"product_name": {"$regex": "OnePlus Nord CE4", "$options": "i"}})
        if prod:
            prod_id = str(prod["_id"])
        else:
            print("[FAIL] Test product not found.")
            sys.exit(1)

    p_name = prod["product_name"]
    print(f"Test Product: {p_name}")
    print(f"Product ID:   {prod_id}")
    print("-" * 80)

    # Clean existing test alerts for this product to ensure pristine test states
    test_email_1 = "hitheshharsha6@gmail.com"
    test_email_2 = "buysmart260@gmail.com"

    # Reset product baseline price to 21998
    update_gececom_product_price(prod_id, 21998)

    # Ensure a primary test alert exists with target 20898
    alert_query = {
        "product_id": prod_id,
        "email": test_email_1,
        "target_price": 20898
    }
    primary_alert = db.price_alerts.find_one(alert_query)
    if not primary_alert:
        ok, msg, primary_alert = create_price_alert({
            "email": test_email_1,
            "product_name": p_name,
            "product_id": prod_id,
            "product_url": f"/gececom#product-{prod_id}",
            "platform": "gececom",
            "current_price": 21998,
            "target_price": 20898,
            "alert_mode": "price",
            "status": "monitoring"
        })
    primary_alert_id = str(primary_alert["_id"])

    # Reset alert state to monitoring
    db.price_alerts.update_one(
        {"_id": ObjectId(primary_alert_id)},
        {"$set": {
            "status": "monitoring",
            "last_notified_price": None,
            "last_email_sent_at": None,
            "target_price": 20898,
            "current_price": 21998,
            "product_id": prod_id
        }}
    )

    results = {}

    # ----------------------------------------------------
    # TEST A — Target not reached
    # Target: Rs. 20,898, New price: Rs. 21,000 -> Expected: No email
    # ----------------------------------------------------
    print("\n--- RUNNING TEST A: Target not reached ---")
    print("Setting price to Rs. 21,000 (Target is Rs. 20,898)")
    update_gececom_product_price(prod_id, 21000)
    res_a = check_and_trigger_price_alerts(
        product_name=p_name,
        new_price=21000,
        platform="gececom",
        product_id=prod_id,
        previous_price=21998
    )
    alert_a = db.price_alerts.find_one({"_id": ObjectId(primary_alert_id)})
    detail_a = next((d for d in res_a.get("details", []) if d.get("alert_id") == primary_alert_id), {})
    test_a_passed = (
        detail_a.get("condition_met") is False and
        detail_a.get("email_sent") is False and
        alert_a.get("status") in ("monitoring", "active") and
        alert_a.get("last_email_sent_at") is None
    )
    results["Test A"] = {
        "passed": test_a_passed,
        "condition_met": detail_a.get("condition_met"),
        "email_sent": detail_a.get("email_sent"),
        "status": alert_a.get("status")
    }
    print(f"Test A Result: {'PASSED' if test_a_passed else 'FAILED'} | Alert Condition Met: {detail_a.get('condition_met')} | Alert Email Sent: {detail_a.get('email_sent')} | DB Status: {alert_a.get('status')}")

    # ----------------------------------------------------
    # TEST B — Target reached
    # Target: Rs. 20,898, New price: Rs. 20,898 -> Expected: One price-drop email
    # ----------------------------------------------------
    print("\n--- RUNNING TEST B: Target reached ---")
    print("Setting price to Rs. 20,898 (Target is Rs. 20,898)")
    update_gececom_product_price(prod_id, 20898)
    res_b = check_and_trigger_price_alerts(
        product_name=p_name,
        new_price=20898,
        platform="gececom",
        product_id=prod_id,
        previous_price=21000
    )
    alert_b = db.price_alerts.find_one({"_id": ObjectId(primary_alert_id)})
    detail_b = next((d for d in res_b.get("details", []) if d.get("alert_id") == primary_alert_id), {})
    test_b_passed = (
        detail_b.get("condition_met") is True and
        detail_b.get("email_sent") is True and
        alert_b.get("status") == "email_sent" and
        alert_b.get("last_notified_price") == 20898 and
        alert_b.get("last_email_sent_at") is not None
    )
    results["Test B"] = {
        "passed": test_b_passed,
        "condition_met": detail_b.get("condition_met"),
        "email_sent": detail_b.get("email_sent"),
        "status": alert_b.get("status"),
        "last_notified_price": alert_b.get("last_notified_price"),
        "service_response": detail_b.get("service_response")
    }
    print(f"Test B Result: {'PASSED' if test_b_passed else 'FAILED'} | Email Sent: {detail_b.get('email_sent')} | DB Status: {alert_b.get('status')} | Service Response: {detail_b.get('service_response')}")

    # ----------------------------------------------------
    # TEST E — Duplicate prevention
    # Run alert check repeatedly after price reaches target
    # Expected: No duplicate emails for the same event
    # ----------------------------------------------------
    print("\n--- RUNNING TEST E: Duplicate prevention ---")
    print("Running alert check again at Rs. 20,898 (Alert already sent at Rs. 20,898)")
    res_e1 = check_and_trigger_price_alerts(
        product_name=p_name,
        new_price=20898,
        platform="gececom",
        product_id=prod_id,
        previous_price=20898
    )
    print("Running alert check again at Rs. 20,898 (second time)")
    res_e2 = check_and_trigger_price_alerts(
        product_name=p_name,
        new_price=20898,
        platform="gececom",
        product_id=prod_id,
        previous_price=20898
    )
    alert_e = db.price_alerts.find_one({"_id": ObjectId(primary_alert_id)})
    detail_e1 = next((d for d in res_e1.get("details", []) if d.get("alert_id") == primary_alert_id), {})
    detail_e2 = next((d for d in res_e2.get("details", []) if d.get("alert_id") == primary_alert_id), {})
    test_e_passed = (
        detail_e1.get("email_sent") is False and
        detail_e1.get("skipped_reason") == "duplicate_prevention" and
        detail_e2.get("email_sent") is False and
        detail_e2.get("skipped_reason") == "duplicate_prevention" and
        alert_e.get("status") == "email_sent"
    )
    results["Test E"] = {
        "passed": test_e_passed,
        "first_attempt_sent": detail_e1.get("email_sent"),
        "second_attempt_sent": detail_e2.get("email_sent"),
        "skipped_reason": detail_e1.get("skipped_reason")
    }
    print(f"Test E Result: {'PASSED' if test_e_passed else 'FAILED'} | Duplicate Emails: 0 | Reason: {detail_e1.get('skipped_reason')}")

    # ----------------------------------------------------
    # TEST C — Price falls below target
    # Target: Rs. 20,898, New price: Rs. 20,000 -> Expected: One price-drop email
    # ----------------------------------------------------
    print("\n--- RUNNING TEST C: Price falls below target ---")
    print("Setting price to Rs. 20,000 (Target is Rs. 20,898, dropped further from Rs. 20,898)")
    update_gececom_product_price(prod_id, 20000)
    res_c = check_and_trigger_price_alerts(
        product_name=p_name,
        new_price=20000,
        platform="gececom",
        product_id=prod_id,
        previous_price=20898
    )
    alert_c = db.price_alerts.find_one({"_id": ObjectId(primary_alert_id)})
    detail_c = next((d for d in res_c.get("details", []) if d.get("alert_id") == primary_alert_id), {})
    test_c_passed = (
        detail_c.get("condition_met") is True and
        detail_c.get("email_sent") is True and
        alert_c.get("status") == "email_sent" and
        alert_c.get("last_notified_price") == 20000
    )
    results["Test C"] = {
        "passed": test_c_passed,
        "condition_met": detail_c.get("condition_met"),
        "email_sent": detail_c.get("email_sent"),
        "status": alert_c.get("status"),
        "last_notified_price": alert_c.get("last_notified_price"),
        "service_response": detail_c.get("service_response")
    }
    print(f"Test C Result: {'PASSED' if test_c_passed else 'FAILED'} | Email Sent: {detail_c.get('email_sent')} | DB Status: {alert_c.get('status')} | Notified Price: Rs. {alert_c.get('last_notified_price')}")

    # ----------------------------------------------------
    # TEST D — Test email button
    # Trigger Send Test Email Now
    # Expected: Real test email arrives, alert status remains unchanged
    # ----------------------------------------------------
    print("\n--- RUNNING TEST D: Test email button ---")
    print(f"Triggering test email for alert {primary_alert_id}")
    status_before = alert_c.get("status")
    ok_d, msg_d, info_d = trigger_test_price_alert(primary_alert_id)
    alert_d = db.price_alerts.find_one({"_id": ObjectId(primary_alert_id)})
    test_d_passed = (
        ok_d is True and
        info_d.get("email_sent") is True and
        alert_d.get("status") == status_before and
        alert_d.get("last_test_email_status") == "sent"
    )
    results["Test D"] = {
        "passed": test_d_passed,
        "success": ok_d,
        "message": msg_d,
        "status_preserved": alert_d.get("status") == status_before,
        "last_test_email_status": alert_d.get("last_test_email_status")
    }
    print(f"Test D Result: {'PASSED' if test_d_passed else 'FAILED'} | Success: {ok_d} | Msg: {msg_d} | Alert Status Preserved: {alert_d.get('status')}")

    # ----------------------------------------------------
    # TEST F — Multiple users
    # Create separate alerts for two users on the same product
    # Expected: Each notification goes only to its intended recipient
    # ----------------------------------------------------
    print("\n--- RUNNING TEST F: Multiple users ---")
    print("Setting up two separate alerts for two distinct recipient emails")
    # Reset product to 21000
    update_gececom_product_price(prod_id, 21000)

    # Clean previous multi-user test alerts
    db.price_alerts.delete_many({
        "product_id": prod_id,
        "email": {"$in": ["buysmart260@gmail.com", "hitheshharsha6@gmail.com"]},
        "_id": {"$ne": ObjectId(primary_alert_id)}
    })

    # Alert 1: Alice (buysmart260@gmail.com), target 20000
    ok1, m1, alert_alice = create_price_alert({
        "email": "buysmart260@gmail.com",
        "product_name": p_name,
        "product_id": prod_id,
        "product_url": f"/gececom#product-{prod_id}",
        "platform": "gececom",
        "current_price": 21000,
        "target_price": 20000,
        "alert_mode": "price",
        "status": "monitoring"
    })
    alice_id = str(alert_alice["_id"])

    # Alert 2: Bob (hitheshharsha6@gmail.com), target 19500
    ok2, m2, alert_bob = create_price_alert({
        "email": "hitheshharsha6@gmail.com",
        "product_name": p_name,
        "product_id": prod_id,
        "product_url": f"/gececom#product-{prod_id}",
        "platform": "gececom",
        "current_price": 21000,
        "target_price": 19500,
        "alert_mode": "price",
        "status": "monitoring"
    })
    bob_id = str(alert_bob["_id"])

    print(f"Alice Alert ID: {alice_id} | Target: Rs. 20,000 | Email: buysmart260@gmail.com")
    print(f"Bob Alert ID:   {bob_id} | Target: Rs. 19,500 | Email: hitheshharsha6@gmail.com")

    # Drop price to Rs. 19,800: Only Alice's condition is met (19800 <= 20000, but 19800 > 19500)
    print("\nStep 1: Dropping price to Rs. 19,800 (Meets Alice target <= 20000, Bob target <= 19500 not yet met)")
    update_gececom_product_price(prod_id, 19800)
    res_f1 = check_and_trigger_price_alerts(
        product_name=p_name,
        new_price=19800,
        platform="gececom",
        product_id=prod_id,
        previous_price=21000
    )
    alice_doc_1 = db.price_alerts.find_one({"_id": ObjectId(alice_id)})
    bob_doc_1 = db.price_alerts.find_one({"_id": ObjectId(bob_id)})

    step1_ok = (
        alice_doc_1.get("status") == "email_sent" and
        alice_doc_1.get("notification_status") == "sent" and
        bob_doc_1.get("status") == "monitoring"
    )
    print(f"Step 1 Check: Alice status: {alice_doc_1.get('status')}, Bob status: {bob_doc_1.get('status')} -> {'PASSED' if step1_ok else 'FAILED'}")

    # Step 2: Drop price to Rs. 19,000: Now Bob's condition is also met (19000 <= 19500)
    print("\nStep 2: Dropping price to Rs. 19,000 (Bob target <= 19500 now met, Alice drops further)")
    update_gececom_product_price(prod_id, 19000)
    res_f2 = check_and_trigger_price_alerts(
        product_name=p_name,
        new_price=19000,
        platform="gececom",
        product_id=prod_id,
        previous_price=19800
    )
    alice_doc_2 = db.price_alerts.find_one({"_id": ObjectId(alice_id)})
    bob_doc_2 = db.price_alerts.find_one({"_id": ObjectId(bob_id)})

    step2_ok = (
        bob_doc_2.get("status") == "email_sent" and
        bob_doc_2.get("notification_status") == "sent" and
        alice_doc_2.get("status") == "email_sent"
    )
    print(f"Step 2 Check: Bob status: {bob_doc_2.get('status')} -> {'PASSED' if step2_ok else 'FAILED'}")

    # Clean up test accounts
    db.price_alerts.delete_many({
        "_id": {"$in": [ObjectId(alice_id), ObjectId(bob_id)]}
    })

    test_f_passed = step1_ok and step2_ok
    results["Test F"] = {
        "passed": test_f_passed,
        "step1_isolation": step1_ok,
        "step2_isolation": step2_ok
    }
    print(f"Test F Result: {'PASSED' if test_f_passed else 'FAILED'} | Multi-user Alert Isolation Verified")

    print("\n" + "=" * 80)
    print("FINAL SUMMARY OF TESTS A - F:")
    print("=" * 80)
    all_passed = True
    for t_name, data in results.items():
        p = data["passed"]
        if not p:
            all_passed = False
        print(f"[{'PASS' if p else 'FAIL'}] {t_name}: {data}")

    print("=" * 80)
    if all_passed:
        print("ALL TESTS PASSED SUCCESSFULLY!")
    else:
        print("SOME TESTS FAILED.")
    print("=" * 80)


if __name__ == "__main__":
    run_all_tests()

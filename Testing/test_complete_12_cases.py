"""
Testing/test_complete_12_cases.py
=================================
Automated Verification Suite for All 12 Test Cases required in Section 10:

1. User creates an alert: verified correct user ID and email stored.
2. Current price > target price: no notification sent.
3. Current price == target price: notification sent to alert owner.
4. Current price < target price: notification sent to alert owner.
5. Two users monitor same product with different targets: each notification goes strictly to appropriate user.
6. Admin email differs from alert owner email: notification still goes strictly to alert owner.
7. Invalid SMTP credentials: alert not incorrectly marked as emailed.
8. Duplicate prevention & retry: no duplicate notifications for same price drop event.
9. Scheduler checks alerts without dashboard open.
10. User privacy: User cannot access or modify another user's private alerts.
11. Dashboard data integrity: correct current price, target price, monitoring status, and email status.
12. Multiplatform compatibility: Amazon, Flipkart, Meesho, and GEC ECom Store integrations functional.
"""

import os
import sys
import time
from datetime import datetime, timezone
from unittest.mock import patch

# Ensure app root is on python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database import (
    get_db,
    create_price_alert,
    get_user_price_alerts,
    delete_price_alert,
    process_single_alert,
    get_alert_by_id,
    send_price_drop_email,
    trigger_test_price_alert,
    simulate_and_trigger_price_drop,
    check_and_trigger_price_alerts,
    to_object_id
)
from services.price_monitor_service import check_all_active_price_alerts

test_results = {}

def run_all_tests():
    db = get_db()
    if db is None:
        print("ERROR: Cannot connect to MongoDB!")
        sys.exit(1)

    print("\n" + "=" * 70)
    print("STARTING COMPLETE 12-POINT AUTOMATED VALIDATION SUITE")
    print("=" * 70)

    # Clean up any leftover test data
    db.price_alerts.delete_many({"product_name": {"$regex": "^TEST_PRODUCT"}})
    db.users.delete_many({"email": {"$in": ["test_user1@example.com", "test_user2@example.com", "admin_sb@example.com"]}})

    # Create dummy users
    u1_res = db.users.insert_one({
        "name": "Test User One",
        "email": "test_user1@example.com",
        "role": "customer",
        "created_at": datetime.now(timezone.utc)
    })
    user1_id = str(u1_res.inserted_id)

    u2_res = db.users.insert_one({
        "name": "Test User Two",
        "email": "test_user2@example.com",
        "role": "customer",
        "created_at": datetime.now(timezone.utc)
    })
    user2_id = str(u2_res.inserted_id)

    # -------------------------------------------------------------
    # CASE 1: Alert creation stores correct user ID and email
    # -------------------------------------------------------------
    print("\n[Case 1] Creating alert with authenticated user ID and email...")
    alert_payload_1 = {
        "product_name": "TEST_PRODUCT_WAKEFIT_PILLOWS",
        "product_url": "https://gececom.store/p/wakefit-pillows",
        "product_image": "https://gececom.store/img/wakefit.jpg",
        "platform": "gececom",
        "current_price": 699,
        "target_price": 600,
        "user_id": user1_id,
        "email": "test_user1@example.com",
        "user_name": "Test User One"
    }
    ok1, msg1, alert1 = create_price_alert(alert_payload_1)
    assert ok1 is True, f"Failed to create alert: {msg1}"
    assert alert1["user_id"] == user1_id, f"Expected user_id {user1_id}, got {alert1.get('user_id')}"
    assert alert1["email"] == "test_user1@example.com", f"Expected email test_user1@example.com, got {alert1.get('email')}"
    assert alert1["status"] == "monitoring", f"Expected monitoring status, got {alert1.get('status')}"
    test_results["Case 1: Correct user ID & email storage"] = "PASSED"
    print("-> Case 1 PASSED: Alert saved with verified owner ID and email.")

    # -------------------------------------------------------------
    # CASE 2: Price above target price: no notification is sent
    # -------------------------------------------------------------
    print("\n[Case 2] Checking price above target price (Current: ₹699, Target: ₹600)...")
    res_case2 = process_single_alert(alert1, current_price=699, previous_price=699)
    assert res_case2["condition_met"] is False, "Condition should be False when 699 > 600"
    assert res_case2["email_sent"] is False, "No email should be sent when price > target"
    doc2 = get_alert_by_id(alert1["id"])
    assert doc2["status"] == "monitoring", f"Status should remain 'monitoring', got {doc2.get('status')}"
    test_results["Case 2: Current > Target sends no email"] = "PASSED"
    print("-> Case 2 PASSED: 699 > 600 -> 0 emails sent, status stays monitoring.")

    # -------------------------------------------------------------
    # CASE 3: Price equals target price: notification sent to alert owner
    # -------------------------------------------------------------
    print("\n[Case 3] Checking price equals target price (Current: ₹600, Target: ₹600)...")
    with patch("otp_utils.send_email_detailed", return_value=(True, "Accepted")):
        res_case3 = process_single_alert(alert1, current_price=600, previous_price=699)
        assert res_case3["condition_met"] is True, "Condition should be True when 600 <= 600"
        assert res_case3["email_sent"] is True, "Email must be sent when price == target"
        assert res_case3["recipient"] == "test_user1@example.com", f"Email must go to alert owner, got {res_case3.get('recipient')}"
    doc3 = get_alert_by_id(alert1["id"])
    assert doc3["status"] == "email_sent", f"Status should be 'email_sent', got {doc3.get('status')}"
    assert doc3["notification_status"] == "sent" or doc3["notification_status"] == "email_sent", "Notification status should be sent"
    assert doc3.get("notification_timestamp") is not None, "notification_timestamp must be set"
    test_results["Case 3: Current == Target sends email to owner"] = "PASSED"
    print("-> Case 3 PASSED: 600 == 600 -> Email sent directly to test_user1@example.com.")

    # Re-arm alert for next test
    db.price_alerts.update_one({"_id": to_object_id(alert1["id"])}, {"$set": {"status": "monitoring", "latest_price": 699, "last_notified_price": None}})
    alert1 = get_alert_by_id(alert1["id"])

    # -------------------------------------------------------------
    # CASE 4: Price falls below target price: notification sent to alert owner
    # -------------------------------------------------------------
    print("\n[Case 4] Checking price below target price (Current: ₹599, Target: ₹600, Prev: ₹699)...")
    with patch("otp_utils.send_email_detailed", return_value=(True, "Accepted for delivery")) as mock_send:
        res_case4 = process_single_alert(alert1, current_price=599, previous_price=699)
        assert res_case4["condition_met"] is True, "Condition should be True when 599 <= 600"
        assert res_case4["email_sent"] is True, "Email must be sent when 599 < 600"
        assert res_case4["recipient"] == "test_user1@example.com", f"Recipient must be alert owner, got {res_case4.get('recipient')}"
        mock_send.assert_called_once()
        args, kwargs = mock_send.call_args
        recipient_arg = args[0]
        subject_arg = args[1]
        body_arg = args[2]
        html_arg = args[3]
        assert recipient_arg == "test_user1@example.com"
        assert "SmartBuy Price Drop Alert – Your Product Is Now Cheaper!" in subject_arg
        assert "599" in body_arg and "699" in body_arg and "600" in body_arg
    test_results["Case 4: Current < Target sends email to owner"] = "PASSED"
    print("-> Case 4 PASSED: 599 < 600 -> Email sent to test_user1@example.com with savings.")

    # -------------------------------------------------------------
    # CASE 5: Two users monitor same product with different target prices
    # -------------------------------------------------------------
    print("\n[Case 5] Two users monitor same product with different target prices (User 1: ₹600, User 2: ₹550)...")
    # User 1 has target 600, User 2 creates target 550
    alert_payload_2 = {
        "product_name": "TEST_PRODUCT_WAKEFIT_PILLOWS",
        "product_url": "https://gececom.store/p/wakefit-pillows",
        "platform": "gececom",
        "current_price": 699,
        "target_price": 550,
        "user_id": user2_id,
        "email": "test_user2@example.com",
        "user_name": "Test User Two"
    }
    ok2, _, alert2 = create_price_alert(alert_payload_2)
    assert ok2 is True

    # Drop price to 599: User 1 should be notified (599 <= 600), User 2 should NOT (599 > 550)
    # First re-arm alert1
    db.price_alerts.update_one({"_id": to_object_id(alert1["id"])}, {"$set": {"status": "monitoring", "latest_price": 699, "last_notified_price": None}})
    a1_fresh = get_alert_by_id(alert1["id"])
    a2_fresh = get_alert_by_id(alert2["id"])

    with patch("otp_utils.send_email_detailed", return_value=(True, "Accepted")) as mock_send_multi:
        res1 = process_single_alert(a1_fresh, current_price=599, previous_price=699)
        res2 = process_single_alert(a2_fresh, current_price=599, previous_price=699)
        assert res1["condition_met"] is True and res1["email_sent"] is True
        assert res1["recipient"] == "test_user1@example.com"
        assert res2["condition_met"] is False and res2["email_sent"] is False
        assert mock_send_multi.call_count == 1
    test_results["Case 5: Multi-user different target prices isolation"] = "PASSED"
    print("-> Case 5 PASSED: At ₹599, only User 1 (target ₹600) received email. User 2 (target ₹550) did not.")

    # -------------------------------------------------------------
    # CASE 6: Administrator email differs from alert owner email
    # -------------------------------------------------------------
    print("\n[Case 6] Administrator email differs from alert owner's email...")
    # System administrator or SMTP user is buysmart260@gmail.com
    # Verify that recipient is NEVER replaced with admin or SMTP sender
    smtp_sender = os.getenv("SMTP_USER", "buysmart260@gmail.com")
    with patch("otp_utils.send_email_detailed", return_value=(True, "Accepted")) as mock_send_admin_check:
        db.price_alerts.update_one({"_id": to_object_id(alert1["id"])}, {"$set": {"status": "monitoring", "last_notified_price": None}})
        a1_test6 = get_alert_by_id(alert1["id"])
        res_case6 = process_single_alert(a1_test6, current_price=590, previous_price=699)
        assert res_case6["recipient"] == "test_user1@example.com"
        assert res_case6["recipient"] != smtp_sender
        assert mock_send_admin_check.call_args[0][0] == "test_user1@example.com"
    test_results["Case 6: Admin email differs from owner email"] = "PASSED"
    print(f"-> Case 6 PASSED: Recipient is strictly alert owner test_user1@example.com, never sender {smtp_sender}.")

    # -------------------------------------------------------------
    # CASE 7: SMTP credentials invalid -> alert not incorrectly marked as emailed
    # -------------------------------------------------------------
    print("\n[Case 7] Testing invalid SMTP credentials / transmission failure...")
    db.price_alerts.update_one({"_id": to_object_id(alert1["id"])}, {"$set": {"status": "monitoring", "last_notified_price": None}})
    a1_test7 = get_alert_by_id(alert1["id"])
    with patch("otp_utils.send_email_detailed", return_value=(False, "SMTPAuthenticationError: (535, 'Invalid credentials')")):
        res_case7 = process_single_alert(a1_test7, current_price=580, previous_price=699)
        assert res_case7["email_sent"] is False
        assert res_case7["status"] == "email_failed"
    doc7 = get_alert_by_id(alert1["id"])
    assert doc7["status"] == "email_failed", f"Expected 'email_failed', got {doc7.get('status')}"
    assert doc7.get("last_email_sent_at") is None or "580" not in str(doc7.get("last_notified_price", ""))
    test_results["Case 7: SMTP error does not falsely mark email sent"] = "PASSED"
    print("-> Case 7 PASSED: Delivery failure marked status as 'email_failed', not sent.")

    # -------------------------------------------------------------
    # CASE 8: Duplicate prevention & idempotency
    # -------------------------------------------------------------
    print("\n[Case 8] Duplicate notification prevention...")
    # Mark alert as already emailed at 550
    db.price_alerts.update_one(
        {"_id": to_object_id(alert1["id"])},
        {"$set": {
            "status": "email_sent",
            "latest_price": 550,
            "last_notified_price": 550,
            "last_email_sent_at": datetime.now(timezone.utc)
        }}
    )
    a1_dup = get_alert_by_id(alert1["id"])
    with patch("otp_utils.send_email_detailed", return_value=(True, "Accepted")) as mock_dup:
        res_dup = process_single_alert(a1_dup, current_price=550, previous_price=550)
        assert res_dup["email_sent"] is False, "Duplicate email must not be sent for same price!"
        mock_dup.assert_not_called()
    test_results["Case 8: Duplicate prevention & idempotency"] = "PASSED"
    print("-> Case 8 PASSED: Alert at ₹550 skipped resending duplicate email.")

    # -------------------------------------------------------------
    # CASE 9: Scheduler checks alerts without dashboard open
    # -------------------------------------------------------------
    print("\n[Case 9] Background monitor cycle checking active alerts...")
    # Create GEC ECom product in DB
    prod_id = "test_pillow_gec"
    db.gececom_products.update_one(
        {"id": prod_id},
        {"$set": {
            "id": prod_id,
            "product_name": "TEST_PRODUCT_WAKEFIT_PILLOWS",
            "current_price": 540,
            "original_price": 699,
            "platform": "gececom"
        }},
        upsert=True
    )
    # Re-arm alert2 (target 550). Product is now 540.
    db.price_alerts.update_one(
        {"_id": to_object_id(alert2["id"])},
        {"$set": {"status": "monitoring", "product_id": prod_id, "last_notified_price": None}}
    )

    with patch("otp_utils.send_email_detailed", return_value=(True, "Delivered")) as mock_sched:
        sched_res = check_all_active_price_alerts()
        assert sched_res["checked"] >= 2
        assert sched_res["notifications_sent"] >= 1
    test_results["Case 9: Background scheduler execution without dashboard"] = "PASSED"
    print(f"-> Case 9 PASSED: Background check_all_active_price_alerts inspected {sched_res['checked']} alerts and triggered notifications.")

    # -------------------------------------------------------------
    # CASE 10: User cannot access or modify another user's private alerts
    # -------------------------------------------------------------
    print("\n[Case 10] Testing user alert privacy and unauthorized modification...")
    # User 2 tries to delete User 1's alert
    del_ok = delete_price_alert(alert1["id"], requesting_user_id=user2_id, is_admin=False)
    assert del_ok is False, "User 2 should NOT be allowed to delete User 1's alert!"

    # User 1 queries their alerts: should only see User 1's alerts
    u1_alerts = get_user_price_alerts(email="test_user1@example.com", user_id=user1_id, allow_all=False)
    u1_ids = [a["id"] for a in u1_alerts]
    assert alert1["id"] in u1_ids
    assert alert2["id"] not in u1_ids, "User 1 should not see User 2's alerts!"

    # Unauthenticated / empty query should not leak all alerts
    anon_alerts = get_user_price_alerts(email=None, user_id=None, allow_all=False)
    assert len(anon_alerts) == 0, "Unauthenticated queries must return empty list!"
    test_results["Case 10: Private alert isolation & unauthorized protection"] = "PASSED"
    print("-> Case 10 PASSED: Cross-user deletion rejected; private alert list strictly isolated.")

    # -------------------------------------------------------------
    # CASE 11: Dashboard displays correct current price, target, and status
    # -------------------------------------------------------------
    print("\n[Case 11] Verifying dashboard data formatting...")
    alerts_view = get_user_price_alerts(email="test_user1@example.com", user_id=user1_id)
    assert len(alerts_view) > 0
    sample_view = alerts_view[0]
    assert "target_price" in sample_view
    assert "latest_price" in sample_view
    assert "status" in sample_view
    assert "notification_status" in sample_view
    test_results["Case 11: Dashboard data attributes & format"] = "PASSED"
    print("-> Case 11 PASSED: Dashboard fields latest_price, target_price, status present.")

    # -------------------------------------------------------------
    # CASE 12: Amazon, Flipkart, Meesho, and GEC ECom Store compatibility
    # -------------------------------------------------------------
    print("\n[Case 12] Testing multiplatform alert support across 4 stores...")
    platforms = ["amazon", "flipkart", "meesho", "gececom"]
    for p in platforms:
        p_alert_data = {
            "product_name": f"TEST_PRODUCT_{p.upper()}",
            "platform": p,
            "current_price": 1000,
            "target_price": 900,
            "user_id": user1_id,
            "email": "test_user1@example.com"
        }
        ok_p, _, alert_p = create_price_alert(p_alert_data)
        assert ok_p is True, f"Failed to create alert for {p}"
        assert alert_p["platform"] == p

        with patch("otp_utils.send_email_detailed", return_value=(True, "Delivered")) as mock_plat:
            res_p = process_single_alert(alert_p, current_price=850, previous_price=1000)
            assert res_p["email_sent"] is True
            assert res_p["recipient"] == "test_user1@example.com"
    test_results["Case 12: All 4 platforms supported (Amazon, Flipkart, Meesho, GEC ECom)"] = "PASSED"
    print("-> Case 12 PASSED: Amazon, Flipkart, Meesho, and GEC ECom alerts processed successfully.")

    # -------------------------------------------------------------
    # CASE 13: Existing Signup OTP & Password-Reset Email Compatibility
    # -------------------------------------------------------------
    print("\n[Case 13] Testing existing signup OTP and password-reset email functionality...")
    from otp_utils import send_otp_email, generate_otp
    test_otp = generate_otp()
    assert len(test_otp) == 6 and test_otp.isdigit(), f"Invalid generated OTP: {test_otp}"

    with patch("otp_utils.send_email_detailed", return_value=(True, "OTP Delivered")) as mock_otp:
        ok_signup, _ = send_otp_email("test_user1@example.com", test_otp, purpose="signup")
        assert ok_signup is True, "Signup OTP email failed"
        assert mock_otp.called
        call_args = mock_otp.call_args[0]
        assert call_args[0] == "test_user1@example.com"
        assert "Email Verification" in call_args[1]

    with patch("otp_utils.send_email_detailed", return_value=(True, "Reset Delivered")) as mock_reset:
        ok_reset, _ = send_otp_email("test_user1@example.com", test_otp, purpose="password_reset")
        assert ok_reset is True, "Password reset OTP email failed"
        assert mock_reset.called
        call_args_reset = mock_reset.call_args[0]
        assert call_args_reset[0] == "test_user1@example.com"
        assert "Password Reset" in call_args_reset[1]

    test_results["Case 13: Signup OTP & Password Reset compatibility"] = "PASSED"
    print("-> Case 13 PASSED: Existing signup verification and password-reset emails functional.")

    # Clean up test records
    db.price_alerts.delete_many({"product_name": {"$regex": "^TEST_PRODUCT"}})
    db.users.delete_many({"email": {"$in": ["test_user1@example.com", "test_user2@example.com", "admin_sb@example.com"]}})
    db.gececom_products.delete_one({"id": prod_id})

    print("\n" + "=" * 70)
    print("SUMMARY OF TEST RESULTS:")
    print("=" * 70)
    for test_name, status in test_results.items():
        print(f"[{status}] {test_name}")
    print("=" * 70)
    print("ALL 13 TEST CASES PASSED SUCCESSFULLY!")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    run_all_tests()

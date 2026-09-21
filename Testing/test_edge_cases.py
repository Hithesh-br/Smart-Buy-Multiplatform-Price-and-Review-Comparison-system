import requests
import time
import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import database
database.init_db()
db = database.db

BASE_URL = "http://127.0.0.1:5000"

def run_edge_case_tests():

    session = requests.Session()

    test_email = f"edge_case_{int(time.time())}@smartbuy.com"
    test_password = "Password123!"
    test_name = "Edge Case Tester"

    print("--- 1. Testing Signup & Initial Unverified State ---")
    reg_resp = session.post(f"{BASE_URL}/signup", data={
        "name": test_name,
        "email": test_email,
        "password": test_password,
        "confirm_password": test_password
    }, allow_redirects=True)

    assert "/verify-otp" in reg_resp.url
    print("   [OK] Signup created user and redirected to /verify-otp")

    print("\n--- 2. Testing Unverified Sign-In Access Gating ---")
    gating_session = requests.Session()
    signin_resp = gating_session.post(f"{BASE_URL}/signin", data={
        "email": test_email,
        "password": test_password
    }, allow_redirects=True)

    assert "/verify-otp" in signin_resp.url
    print("   [OK] Unverified sign-in intercepted and redirected to /verify-otp!")

    print("\n--- 3. Testing Wrong OTP & Attempt Increment Counter ---")
    otp_doc = db.otp_codes.find_one({"identifier": test_email})
    assert otp_doc is not None
    real_code = otp_doc["code"]
    wrong_code = "000000" if real_code != "000000" else "111111"

    # Attempt 1 wrong code
    bad1_resp = session.post(f"{BASE_URL}/verify-otp", data={"otp": wrong_code, "channel": "email"})
    assert "Incorrect OTP" in bad1_resp.text or "Attempt 1" in bad1_resp.text
    doc_after_bad1 = db.otp_codes.find_one({"identifier": test_email})
    assert doc_after_bad1.get("attempts") == 1
    print("   [OK] Wrong OTP incremented attempts counter to 1")

    # Send 4 more wrong attempts to hit limit (5 max attempts)
    for i in range(2, 6):
        resp = session.post(f"{BASE_URL}/verify-otp", data={"otp": wrong_code, "channel": "email"})

    doc_after_max = db.otp_codes.find_one({"identifier": test_email})
    assert doc_after_max is None, "OTP code should be deleted after exceeding 5 max attempts"
    print("   [OK] Exceeding 5 max attempts invalidated and deleted the OTP code from DB!")

    print("\n--- 4. Testing Resend OTP Functionality ---")
    resend_resp = session.post(f"{BASE_URL}/resend-otp", data={"channel": "email"}, allow_redirects=True)
    assert "/verify-otp" in resend_resp.url

    new_otp_doc = db.otp_codes.find_one({"identifier": test_email})
    assert new_otp_doc is not None
    new_code = new_otp_doc["code"]
    assert new_otp_doc.get("attempts") == 0, "Resent OTP should reset attempts counter to 0"
    print(f"   [OK] Resend generated new code ({new_code}) and reset attempts counter to 0!")

    print("\n--- 5. Testing Expired OTP Handling ---")
    # Simulate past expiration time in database
    past_time = datetime.now(timezone.utc) - timedelta(minutes=11)
    db.otp_codes.update_one({"identifier": test_email}, {"$set": {"expires_at": past_time}})

    expired_resp = session.post(f"{BASE_URL}/verify-otp", data={"otp": new_code, "channel": "email"})
    assert "expired" in expired_resp.text.lower()
    doc_expired = db.otp_codes.find_one({"identifier": test_email})
    assert doc_expired is None, "Expired OTP record should be purged"
    print("   [OK] Expired OTP blocked verification and purged code from DB!")

    print("\n--- 6. Verifying Final OTP Success ---")
    session.post(f"{BASE_URL}/resend-otp", data={"channel": "email"}, allow_redirects=True)
    valid_doc = db.otp_codes.find_one({"identifier": test_email})
    valid_code = valid_doc["code"]

    final_resp = session.post(f"{BASE_URL}/verify-otp", data={"otp": valid_code, "channel": "email"}, allow_redirects=True)
    assert "/signin" in final_resp.url or "/profile" in final_resp.url

    user = database.get_user_by_email(test_email)
    assert user.get("is_email_verified") == True
    print("   [OK] Final valid OTP confirmed and user marked as verified!")


    print("\n=== ALL EDGE CASE TESTS PASSED PERFECTLY ===")

if __name__ == "__main__":
    run_edge_case_tests()

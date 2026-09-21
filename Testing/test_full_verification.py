import os
import sys
import time
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = "http://127.0.0.1:5000"

def run_all_20_tests():
    print("\n" + "=" * 70)
    print("      SMARTBUY AUTHENTICATION & EMAIL OTP VERIFICATION TEST SUITE")
    print("=" * 70 + "\n")

    session = requests.Session()
    ts = int(time.time())
    test_email = f"smartbuy_test_{ts}@example.com"
    valid_pwd = "SmartBuy@123"

    # --- Test 14: Search product without login -> works ---
    print("Test 14: Product search without login...")
    search_resp = session.get(f"{BASE_URL}/api/search?q=laptop")
    assert search_resp.status_code == 200, f"Expected 200, got {search_resp.status_code}"
    print("  [PASS] Product search accessible without authentication.")

    # --- Test 15: Click Buy/Deal -> redirects to auth flow if unauthenticated ---
    print("Test 15: Click Buy/Deal action...")
    deal_resp = session.get(f"{BASE_URL}/deal/continue", allow_redirects=True)
    assert "/signup" in deal_resp.url or "/signin" in deal_resp.url or "/profile" in deal_resp.url
    print("  [PASS] Deal/Buy button triggers authentication flow for guest users.")

    # --- Test 1: Valid email -> Send OTP -> email sent ---
    print("Test 1: POST /api/auth/send-otp with valid email...")
    send_resp = session.post(f"{BASE_URL}/api/auth/send-otp", json={"email": test_email})
    assert send_resp.status_code == 200, f"Expected 200, got {send_resp.status_code}: {send_resp.text}"
    send_json = send_resp.json()
    assert send_json.get("success") == True
    assert send_json.get("message") == "OTP sent successfully"
    print("  [PASS] Send OTP API returned success = true.")

    # Fetch stored OTP from MongoDB for testing
    from database import db, init_db
    init_db()
    from database import db
    rec = db.otp_verifications.find_one({"email": test_email})
    assert rec is not None, "OTP verification record not found in MongoDB otp_verifications"
    real_otp = rec.get("code")
    print(f"  (MongoDB otp_verifications verified — real OTP code generated securely: {real_otp})")

    # --- Test 6: Resend OTP Cooldown (immediately after sending) ---
    print("Test 6: Testing 60-second resend OTP cooldown limit...")
    cooldown_resp = session.post(f"{BASE_URL}/api/auth/resend-otp", json={"email": test_email})
    assert cooldown_resp.status_code == 429, f"Expected 429 Cooldown, got {cooldown_resp.status_code}: {cooldown_resp.text}"
    print("  [PASS] 60-second resend cooldown enforced successfully.")

    # --- Test 3: Wrong OTP -> rejected ("Invalid OTP") ---
    print("Test 3: Submitting wrong OTP...")
    wrong_resp = session.post(f"{BASE_URL}/api/auth/verify-otp", json={"email": test_email, "otp": "000000"})
    assert wrong_resp.status_code == 400
    assert wrong_resp.json().get("message") == "Invalid OTP"
    print("  [PASS] Wrong OTP rejected with 'Invalid OTP'.")

    # --- Test 5: 7 wrong attempts -> OTP invalidated ---
    print("Test 5: Exceeding maximum (7) incorrect OTP attempts...")
    for i in range(6): # total 1 + 6 = 7 wrong attempts
        r = session.post(f"{BASE_URL}/api/auth/verify-otp", json={"email": test_email, "otp": "999999"})
    
    assert r.status_code == 400
    assert "Maximum OTP attempts exceeded" in r.json().get("message")
    rec_after_max = db.otp_verifications.find_one({"email": test_email})
    assert rec_after_max is None, "OTP record should be invalidated/deleted after 7 attempts"
    print("  [PASS] 7 wrong attempts invalidated OTP and deleted record.")

    # --- Test 6 Part 2: Resend OTP generates fresh valid OTP ---
    print("Test 6 (Part 2): Requesting fresh OTP after invalidation...")
    resend_resp = session.post(f"{BASE_URL}/api/auth/resend-otp", json={"email": test_email})
    assert resend_resp.status_code == 200
    rec_new = db.otp_verifications.find_one({"email": test_email})
    new_otp = rec_new.get("code")
    print(f"  [PASS] Resend OTP succeeded. New OTP generated: {new_otp}")

    # --- Test 4: OTP Expired -> rejected ---
    print("Test 4: Testing expired OTP rejection...")
    test_expired_email = f"expired_{ts}@example.com"
    session.post(f"{BASE_URL}/api/auth/send-otp", json={"email": test_expired_email})
    from datetime import datetime, timezone, timedelta
    db.otp_verifications.update_one({"email": test_expired_email}, {"$set": {"expires_at": datetime.now(timezone.utc) - timedelta(hours=1)}})
    exp_resp = session.post(f"{BASE_URL}/api/auth/verify-otp", json={"email": test_expired_email, "otp": "123456"})
    assert exp_resp.status_code == 400
    assert "OTP expired" in exp_resp.json().get("message")
    print("  [PASS] Expired OTP rejected with 'OTP expired. Please request a new OTP.'.")

    # --- Test 2: Correct OTP -> verification successful ---
    print("Test 2: Submitting correct OTP for new_otp...")
    verify_resp = session.post(f"{BASE_URL}/api/auth/verify-otp", json={"email": test_email, "otp": new_otp})
    assert verify_resp.status_code == 200, f"Verification failed: {verify_resp.text}"
    assert verify_resp.json().get("message") == "Email verified successfully"
    rec_verified = db.otp_verifications.find_one({"email": test_email})
    assert rec_verified.get("verified") == True
    print("  [PASS] Correct OTP verified successfully and marked verified = true in MongoDB.")

    # --- Test 10: Unverified email -> account creation rejected ---
    print("Test 10: Attempting signup with unverified email...")
    unverified_email = f"unverified_{ts}@example.com"
    unver_signup = session.post(f"{BASE_URL}/api/auth/signup", json={
        "name": "Unverified Tester",
        "email": unverified_email,
        "password": valid_pwd,
        "confirm_password": valid_pwd
    })
    print(f"DEBUG Test 10: status={unver_signup.status_code}, body={unver_signup.text}")
    assert unver_signup.status_code == 400, f"Expected 400, got {unver_signup.status_code}: {unver_signup.text}"
    assert "Please verify your email" in unver_signup.json().get("message")
    print("  [PASS] Unverified email signup rejected.")

    # --- Test 7: Invalid password -> signup rejected ---
    print("Test 7: Attempting signup with weak password ('weak')...")
    weak_signup = session.post(f"{BASE_URL}/api/auth/signup", json={
        "name": "Weak Tester",
        "email": test_email,
        "password": "weak",
        "confirm_password": "weak"
    })
    assert weak_signup.status_code == 400
    print("  [PASS] Weak password rejected by backend validation.")

    # --- Test 9: Passwords don't match -> rejected ---
    print("Test 9: Attempting signup with mismatched passwords...")
    mismatch_signup = session.post(f"{BASE_URL}/api/auth/signup", json={
        "name": "Mismatch Tester",
        "email": test_email,
        "password": valid_pwd,
        "confirm_password": "DifferentPassword@123"
    })
    assert mismatch_signup.status_code == 400
    assert "Passwords do not match." in mismatch_signup.json().get("message")
    print("  [PASS] Mismatched passwords rejected.")

    # --- Test 8 & 11: Valid password (SmartBuy@123) & Verified Email -> Account stored in MongoDB ---
    print("Tests 8 & 11: Signup with verified email and valid password ('SmartBuy@123')...")
    signup_resp = session.post(f"{BASE_URL}/api/auth/signup", json={
        "name": "SmartBuy User",
        "email": test_email,
        "password": valid_pwd,
        "confirm_password": valid_pwd
    })
    assert signup_resp.status_code == 201, f"Expected 201, got {signup_resp.status_code}: {signup_resp.text}"
    user_doc = db.users.find_one({"email": test_email})
    assert user_doc is not None
    assert user_doc.get("email_verified") == True or user_doc.get("emailVerified") == True
    print("  [PASS] Account created and verified user document saved in MongoDB.")

    # --- Test 12: Duplicate email -> signup rejected ---
    print("Test 12: Attempting duplicate signup with already registered email...")
    dup_resp = session.post(f"{BASE_URL}/api/auth/signup", json={
        "name": "Duplicate User",
        "email": test_email,
        "password": valid_pwd,
        "confirm_password": valid_pwd
    })
    assert dup_resp.status_code == 409
    assert "Email already registered. Please sign in." in dup_resp.json().get("message")
    print("  [PASS] Duplicate signup rejected with HTTP 409.")

    # --- Test 13: Successful signup -> existing Sign In works ---
    print("Test 13: Sign in with newly created account...")
    signin_resp = session.post(f"{BASE_URL}/signin", data={
        "email": test_email,
        "password": valid_pwd
    }, allow_redirects=True)
    assert "/profile" in signin_resp.url, f"Expected redirect to /profile, got {signin_resp.url}"
    print("  [PASS] Sign in successful, redirected to /profile.")

    print("\n" + "=" * 70)
    print("         ALL 15 AUTHENTICATION & OTP TEST SCENARIOS PASSED 100%")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    run_all_20_tests()

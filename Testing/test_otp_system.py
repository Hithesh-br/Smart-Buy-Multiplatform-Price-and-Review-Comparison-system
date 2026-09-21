import requests
import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_URL = "http://127.0.0.1:5000"


def test_full_otp_flow():
    session = requests.Session()

    test_email = f"otp_test_{int(time.time())}@smartbuy.com"
    test_password = "Password123!"
    test_name = "OTP Tester"


    print("1. Submitting Signup Form for new user...")
    signup_resp = session.post(f"{BASE_URL}/signup", data={
        "name": test_name,
        "email": test_email,
        "password": test_password,
        "confirm_password": test_password
    }, allow_redirects=True)

    print(f"   Signup Response URL: {signup_resp.url}")
    assert "/verify-otp" in signup_resp.url, "Signup should redirect to /verify-otp"
    print("   [OK] Signup redirected to /verify-otp successfully!")

    print("2. Attempting Signin prior to verification (Access Gating Check)...")
    signin_resp = session.post(f"{BASE_URL}/signin", data={
        "email": test_email,
        "password": test_password
    }, allow_redirects=True)

    print(f"   Signin Attempt URL: {signin_resp.url}")
    assert "/verify-otp" in signin_resp.url, "Unverified signin should be gated & redirected to /verify-otp"
    print("   [OK] Unverified account access gated successfully!")

    print("3. Querying stored OTP code from MongoDB database...")
    import database
    database.init_db()
    db = database.db
    assert db is not None, "MongoDB database connection failed or database is None"
    otp_doc = db.otp_codes.find_one({"identifier": test_email})

    assert otp_doc is not None, "OTP document should exist in db.otp_codes"
    otp_code = otp_doc["code"]
    print(f"   Fetched OTP Code from DB: {otp_code}")

    print("4. Submitting OTP code to /verify-otp...")
    verify_resp = session.post(f"{BASE_URL}/verify-otp", data={
        "otp": otp_code,
        "channel": "email"
    }, allow_redirects=True)

    print(f"   Verification Response URL: {verify_resp.url}")
    assert "/signin" in verify_resp.url or "/profile" in verify_resp.url, "Successful verification should redirect to /signin"
    
    user = database.get_user_by_email(test_email)
    assert user is not None, f"User with email '{test_email}' was not found in the database"
    assert user.get("is_email_verified") == True, "User is_email_verified should be True"
    print("   [OK] OTP verified & user account marked as verified in MongoDB!")

    print("5. Signing in with verified account...")
    login_resp = session.post(f"{BASE_URL}/signin", data={
        "email": test_email,
        "password": test_password
    }, allow_redirects=True)

    print(f"   Verified Signin URL: {login_resp.url}")
    assert "/profile" in login_resp.url, "Verified signin should succeed and redirect to /profile"
    print("   [OK] Verified user signed in successfully!")

    print("\n=== ALL OTP VERIFICATION & ACCESS GATING TESTS PASSED PERFECTLY ===")


if __name__ == "__main__":
    test_full_otp_flow()

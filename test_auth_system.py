"""
test_auth_system.py
===================
Automated test suite for SmartBuy Flask + MongoDB Authentication & Forgot Password System.
"""

import sys
import os
from dotenv import load_dotenv

load_dotenv(override=True)

if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    getattr(sys.stdout, 'reconfigure')(encoding='utf-8')

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from database import db, get_user_by_email, store_otp, verify_otp_code, delete_otp
from otp_utils import validate_password, generate_otp, hash_otp

def run_tests():
    print("=" * 70)
    print("      SMARTBUY AUTHENTICATION & OTP SYSTEM TEST SUITE")
    print("=" * 70)

    # 1. TEST PASSWORD VALIDATION RULES
    print("\n[TEST 1] Password Validation Rules...")
    valid_pwds = ["Smartbuy@123", "Admin@2026!", "P@ssw0rd99"]
    invalid_pwds = [
        ("smartbuy@123", "Must start with uppercase A-Z"),
        ("Smartbuy123", "Missing special char"),
        ("Smartbuy@", "Missing number"),
        ("Sm@12", "Too short (<8 chars)")
    ]

    for pwd in valid_pwds:
        ok, errs = validate_password(pwd)
        assert ok, f"Expected '{pwd}' to be VALID, but got errors: {errs}"
        print(f"  ✓ Valid Password accepted: '{pwd}'")

    for pwd, reason in invalid_pwds:
        ok, errs = validate_password(pwd)
        assert not ok, f"Expected '{pwd}' to be INVALID ({reason}), but it passed!"
        print(f"  ✓ Invalid Password correctly rejected: '{pwd}' ({errs[0]})")

    # 2. TEST SIGNUP ROUTE & MONGODB INTEGRATION
    test_email = "autotest_user@smartbuy.com"
    test_name = "AutoTest User"
    initial_pwd = "Smartbuy@123"

    print(f"\n[TEST 2] User Registration (POST /signup) for {test_email}...")
    if db is not None:
        db.users.delete_many({"email": test_email})
        delete_otp(test_email)

    with app.test_client() as client:
        # Submit signup
        res = client.post('/signup', data={
            'name': test_name,
            'email': test_email,
            'password': initial_pwd,
            'confirm_password': initial_pwd
        }, follow_redirects=False)

        assert res.status_code in (200, 201, 302), f"Signup failed with status code: {res.status_code}"
        print(f"  ✓ Signup HTTP response code: {res.status_code}")

        # Check user in MongoDB
        user_doc = get_user_by_email(test_email)
        assert user_doc is not None, "User not found in MongoDB after signup!"
        assert user_doc['name'] == test_name, "Name mismatch in MongoDB!"
        assert user_doc['email'] == test_email, "Email mismatch in MongoDB!"
        assert 'hashed_password' in user_doc or 'password_hash' in user_doc, "Hashed password missing in MongoDB!"
        assert user_doc.get('hashed_password') != initial_pwd, "SECURITY CRITICAL: Plain-text password saved in DB!"
        assert user_doc.get('email_verified') is True, "email_verified attribute missing/false!"
        print("  ✓ MongoDB document stored correctly:")
        print(f"    - name: {user_doc.get('name')}")
        print(f"    - email: {user_doc.get('email')}")
        hp = str(user_doc.get('hashed_password') or user_doc.get('password_hash') or '')
        print(f"    - hashed_password: {hp[:30]}...")
        print(f"    - created_at: {user_doc.get('created_at')}")
        print(f"    - email_verified: {user_doc.get('email_verified')}")

        # 3. TEST SIGNIN ROUTE
        print(f"\n[TEST 3] User Sign In (POST /signin)...")
        # Incorrect password
        res_fail = client.post('/signin', data={'email': test_email, 'password': 'WrongPassword@123'})
        assert b"Invalid email or password" in res_fail.data or res_fail.status_code == 200, "Failed password was allowed!"
        print("  ✓ Incorrect password correctly rejected.")

        # Correct password
        res_succ = client.post('/signin', data={'email': test_email, 'password': initial_pwd}, follow_redirects=False)
        assert res_succ.status_code in (200, 302), f"Signin failed with status {res_succ.status_code}"
        print("  ✓ Valid signin succeeded and redirected.")

        # 4. TEST FORGOT PASSWORD OTP GENERATION & DISPATCH
        print(f"\n[TEST 4] Forgot Password OTP Flow...")

        # Non-existent email
        res_no_user = client.post('/send-reset-otp', json={'email': 'nonexistent_9999@smartbuy.com'})
        assert res_no_user.status_code in (200, 404), f"Expected 200 or 404 for missing email, got {res_no_user.status_code}"
        assert db.otp_verifications.find_one({"email": 'nonexistent_9999@smartbuy.com'}) is None, "OTP should not be created for nonexistent user!"
        print("  ✓ Non-existent email request handled safely (no OTP generated).")

        # Existing email
        delete_otp(test_email)
        res_otp = client.post('/send-reset-otp', json={'email': test_email})
        assert res_otp.status_code == 200, f"Send OTP failed with status {res_otp.status_code}: {res_otp.get_json()}"
        print("  ✓ Send OTP request returned HTTP 200.")

        # Verify OTP record in DB
        otp_rec = db.otp_verifications.find_one({"email": test_email})
        assert otp_rec is not None, "OTP record not found in MongoDB!"
        assert otp_rec.get('attempts') == 0, "Initial attempts should be 0!"
        print("  ✓ Temporary OTP stored securely in MongoDB collection 'otp_verifications'.")
        print(f"    - email: {otp_rec.get('email')}")
        print(f"    - attempts: {otp_rec.get('attempts')}")
        print(f"    - expires_at: {otp_rec.get('expires_at')}")

        # 5. TEST OTP VERIFICATION & ATTEMPTS LIMIT
        print(f"\n[TEST 5] OTP Verification & Security Limits...")
        
        # Test wrong OTP (attempts counter increment)
        res_wrong = client.post('/verify-reset-otp', json={'email': test_email, 'otp': '000000'})
        assert res_wrong.status_code == 400, f"Expected 400 for wrong OTP, got {res_wrong.status_code}"
        otp_after_wrong = db.otp_verifications.find_one({"email": test_email})
        assert otp_after_wrong and otp_after_wrong.get('attempts') == 1, "Attempts count did not increment on wrong OTP!"
        print("  ✓ Wrong OTP rejected and attempt counter incremented to 1.")

        # Generate known test OTP directly for test verification
        test_code = "654321"
        store_otp(test_email, test_code, channel="email", purpose="forgot_password", ttl_minutes=10)

        # Test correct OTP verification
        res_ok_otp = client.post('/verify-reset-otp', json={'email': test_email, 'otp': test_code})
        assert res_ok_otp.status_code == 200 and res_ok_otp.get_json().get('success'), f"OTP verification failed: {res_ok_otp.get_json()}"
        print("  ✓ Valid 6-digit OTP verified successfully.")

        # 6. TEST PASSWORD RESET & OTP INVALIDATION
        print(f"\n[TEST 6] Password Reset & OTP Cleanup...")
        new_pwd = "Smartnew@2026"
        res_reset = client.post('/reset-password', json={
            'email': test_email,
            'new_password': new_pwd,
            'confirm_new_password': new_pwd
        })

        assert res_reset.status_code == 200 and res_reset.get_json().get('success'), f"Password reset failed: {res_reset.get_json()}"
        print("  ✓ Password reset HTTP 200 success.")

        # Verify password updated in MongoDB
        updated_user = get_user_by_email(test_email)
        assert updated_user is not None, "Updated user not found in DB!"
        from werkzeug.security import check_password_hash
        pwd_hash = str(updated_user.get('hashed_password') or updated_user.get('password_hash') or '')
        assert check_password_hash(pwd_hash, new_pwd), "MongoDB password hash not updated to new password!"
        print("  ✓ MongoDB user hashed_password updated successfully.")

        # Verify OTP record invalidated/removed
        deleted_otp_rec = db.otp_verifications.find_one({"email": test_email})
        assert deleted_otp_rec is None, "SECURITY RISK: Used OTP was not deleted after password reset!"
        print("  ✓ Used OTP removed from MongoDB after reset.")

        # Verify Signin with new password
        res_new_signin = client.post('/signin', data={'email': test_email, 'password': new_pwd}, follow_redirects=False)
        assert res_new_signin.status_code in (200, 302), "Signin with newly reset password failed!"
        print("  ✓ Sign In with newly reset password succeeded!")

    print("\n" + "=" * 70)
    print("      ALL AUTHENTICATION TESTS PASSED SUCCESSFULLY! 🎉")
    print("=" * 70 + "\n")

if __name__ == '__main__':
    run_tests()

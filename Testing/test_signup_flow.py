import os
import sys
import unittest
from dotenv import load_dotenv

load_dotenv(override=True)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import app
from database import store_otp, verify_otp_code, get_user_by_email, db, delete_signup_otp
from otp_utils import generate_otp, validate_password

class TestSignupWorkflow(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        self.test_email = "flowtest_user@example.com"
        self.test_name = "Flow Test User"
        self.test_password = "SecurePass123!"
        
        # Cleanup any existing test user or OTP record
        if db is not None:
            db.users.delete_many({"email": self.test_email})
            db.otp_codes.delete_many({"identifier": self.test_email})
            db.signup_otp.delete_many({"email": self.test_email})

    def test_full_signup_flow(self):
        print("\n--- 1. Enter Email & Send OTP via Gmail SMTP ---")
        res1 = self.client.post('/api/send-otp', json={'email': self.test_email})
        self.assertEqual(res1.status_code, 200)
        self.assertTrue(res1.get_json().get('success'))
        print("  -> OTP Sent successfully")

        print("\n--- 2. Enter OTP & Verify OTP ---")
        # Retrieve the generated code from database for verification
        otp_rec = db.otp_codes.find_one({"identifier": self.test_email})
        self.assertIsNotNone(otp_rec)
        otp_code = otp_rec.get("code")
        print(f"  -> Retrieved OTP Code: {otp_code}")

        res2 = self.client.post('/api/verify-otp', json={'email': self.test_email, 'otp': otp_code})
        self.assertEqual(res2.status_code, 200)
        self.assertTrue(res2.get_json().get('success'))
        print("  -> Email Verified [OK]")

        print("\n--- 3. Password Validation ---")
        is_valid, errs = validate_password(self.test_password)
        self.assertTrue(is_valid)
        self.assertEqual(len(errs), 0)
        print("  -> Password Validation Passed [OK]")

        print("\n--- 4. Create Account in MongoDB ---")
        res3 = self.client.post('/signup', json={
            'name': self.test_name,
            'email': self.test_email,
            'password': self.test_password,
            'confirm_password': self.test_password
        })
        self.assertEqual(res3.status_code, 201)
        self.assertTrue(res3.get_json().get('success'))
        print("  -> Account Created Successfully!")

        print("\n--- 5. Verify User Document in MongoDB ---")
        user = get_user_by_email(self.test_email)
        self.assertIsNotNone(user)
        self.assertEqual(user.get("name"), self.test_name)
        self.assertTrue(user.get("is_email_verified"))
        print(f"  -> MongoDB User Verified: ID={user.get('_id')}, is_email_verified={user.get('is_email_verified')}")

    def tearDown(self):
        if db is not None:
            db.users.delete_many({"email": self.test_email})
            db.otp_codes.delete_many({"identifier": self.test_email})
            db.signup_otp.delete_many({"email": self.test_email})

if __name__ == "__main__":
    unittest.main()

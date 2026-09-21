import os
import sys
from dotenv import load_dotenv

load_dotenv(override=True)

from app import app
from database import store_otp, verify_otp_code, get_user_by_email
from otp_utils import generate_otp, send_otp_email

print("--- Step 1: Testing OTP Generation & Storage ---")
test_email = "buysmart260@gmail.com"
otp = generate_otp()
print(f"Generated OTP: {otp} for {test_email}")

stored = store_otp(test_email, otp, channel="email")
print(f"Store OTP Result: {stored}")

print("\n--- Step 2: Testing Live SMTP Email Dispatch ---")
sent, msg = send_otp_email(test_email, otp)
print(f"Send Email Result: {sent} | Message: {msg}")

print("\n--- Step 3: Testing OTP Verification (Valid Code) ---")
valid, v_msg = verify_otp_code(test_email, otp, channel="email")
print(f"Verify OTP (Valid Code): {valid} | Message: {v_msg}")

print("\n--- Step 4: Testing Flask API Endpoints ---")
with app.test_client() as client:
    # 4a. API Send OTP
    res1 = client.post('/api/send-otp', json={'email': test_email})
    print(f"POST /api/send-otp -> Status: {res1.status_code}, Body: {res1.get_json()}")
    
    # Extract code from db/store to test verify
    otp2 = generate_otp()
    store_otp(test_email, otp2, channel="email")
    
    # 4b. API Verify OTP
    res2 = client.post('/api/verify-otp', json={'email': test_email, 'otp': otp2})
    print(f"POST /api/verify-otp -> Status: {res2.status_code}, Body: {res2.get_json()}")

print("\n--- ALL TESTS COMPLETED ---")

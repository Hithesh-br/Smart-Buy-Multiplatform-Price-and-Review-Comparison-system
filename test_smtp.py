"""
test_smtp.py
============
Run this standalone BEFORE testing the signup page, to confirm your Gmail
App Password + SMTP settings actually work.

Usage:
    python test_smtp.py

Reads SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD / SMTP_FROM from .env,
sends a real test email to yourself, and prints exactly what fails if it does.
"""

import os
import smtplib
from email.mime.text import MIMEText
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)

TEST_TO = SMTP_USER  # sends to yourself

print(f"Host: {SMTP_HOST}")
print(f"Port: {SMTP_PORT}")
print(f"User: {SMTP_USER}")
print(f"Password length: {len(SMTP_PASSWORD) if SMTP_PASSWORD else 0} chars")
print("-" * 40)

if not SMTP_USER or not SMTP_PASSWORD:
    print("ERROR: SMTP_USER or SMTP_PASSWORD is missing from your .env")
    raise SystemExit(1)

msg = MIMEText("This is a test email from SmartBuy's SMTP setup.")
msg["Subject"] = "SmartBuy SMTP test"
msg["From"] = SMTP_FROM
msg["To"] = TEST_TO

try:
    print("Connecting...")
    server = smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10)
    server.set_debuglevel(1)  # prints the full SMTP conversation
    print("Starting TLS...")
    server.starttls()
    print("Logging in...")
    server.login(SMTP_USER, SMTP_PASSWORD)
    print("Sending...")
    server.sendmail(SMTP_FROM, [TEST_TO], msg.as_string())
    server.quit()
    print("-" * 40)
    print(f"SUCCESS: Test email sent to {TEST_TO}. Check your inbox.")
except smtplib.SMTPAuthenticationError as e:
    print("-" * 40)
    print("AUTH FAILED — your SMTP_USER/SMTP_PASSWORD are wrong.")
    print("Most likely cause: you're using your normal Gmail password instead")
    print("of a 16-character App Password. See Google Account > Security > App passwords.")
    print(f"Raw error: {e}")
except (smtplib.SMTPServerDisconnected, ConnectionResetError, OSError) as e:
    print("-" * 40)
    print("CONNECTION FAILED — 'Connection unexpectedly closed' type error.")
    print("Common causes:")
    print("  1. Wrong port/security combo (use 587 with starttls(), not 465)")
    print("  2. Your network/firewall/hosting provider blocks outbound port 587")
    print("     (common on some cloud hosts, corporate networks, or India-based ISPs")
    print("     that throttle SMTP — try from a different network to isolate this)")
    print("  3. Antivirus or proxy intercepting the connection")
    print(f"Raw error: {e}")
except Exception as e:
    print("-" * 40)
    print(f"UNEXPECTED ERROR: {type(e).__name__}: {e}")

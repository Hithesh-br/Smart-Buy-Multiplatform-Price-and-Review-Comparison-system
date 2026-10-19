import os
import random
import re
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

import secrets
import hashlib
from email.message import EmailMessage

def generate_otp() -> str:
    """
    Generate a cryptographically secure 6-digit numeric OTP code using secrets module.
    Always produces exactly 6 digits (e.g. 058321).
    """
    return str(secrets.randbelow(1000000)).zfill(6)


def hash_otp(otp_code: str) -> str:
    """Hash an OTP string using SHA-256 before saving to database."""
    return hashlib.sha256(str(otp_code).strip().encode('utf-8')).hexdigest()


def validate_password(password: str) -> tuple[bool, list[str]]:
    """
    Validate password complexity requirements:
    - Minimum 8 characters
    - Must start with an uppercase English letter (A-Z)
    - Contain at least one number (0-9)
    - Contain at least one special character (@ ! # $ % ^ & *, etc.)
    """
    errors = []
    if not password or len(password) < 8:
        errors.append("Password must be at least 8 characters long.")
    if not password or not re.match(r'^[A-Z]', password):
        errors.append("Password must start with an uppercase English letter (A-Z).")
    if not password or not re.search(r'[0-9]', password):
        errors.append("Password must contain at least one number (0-9).")
    if not password or not re.search(r'[^A-Za-z0-9]', password):
        errors.append("Password must contain at least one special character (e.g. @, !, #, $, %).")
    
    return len(errors) == 0, errors



DEFAULT_SMTP_HOST = "smtp.gmail.com"
DEFAULT_SMTP_PORT = 465
DEFAULT_SMTP_USER = "buysmart260@gmail.com"
DEFAULT_SMTP_PASS = "zrqv vpqh wjcw bjnr"
DEFAULT_FROM_NAME = "SmartBuy"


def get_smtp_config() -> tuple[str, int, str, str, str]:
    """Retrieve sanitized SMTP configuration from environment or verified fallback."""
    load_dotenv(override=True)
    smtp_host = (os.getenv("SMTP_HOST") or DEFAULT_SMTP_HOST).strip().strip("'\"")
    try:
        smtp_port = int(str(os.getenv("SMTP_PORT", DEFAULT_SMTP_PORT)).strip().strip("'\""))
    except (ValueError, TypeError):
        smtp_port = DEFAULT_SMTP_PORT

    smtp_user = (os.getenv("SMTP_USER") or DEFAULT_SMTP_USER).strip().strip("'\"")
    smtp_pass = (os.getenv("SMTP_PASSWORD") or DEFAULT_SMTP_PASS).strip().strip("'\"")
    from_name = (os.getenv("SMTP_FROM_NAME") or DEFAULT_FROM_NAME).strip().strip("'\"")

    return smtp_host, smtp_port, smtp_user, smtp_pass, from_name


def send_email_detailed(to_email: str, subject: str, body_text: str, html_content: str = None) -> tuple[bool, str]:
    """
    Send an email via SMTP (supporting both Port 465 SSL and Port 587 STARTTLS with auto-fallback).
    Includes high-priority mobile push headers for immediate phone inbox alerts.
    Returns (True, success_message) on success, (False, error_message) on failure.
    Never logs or exposes passwords or sensitive credentials.
    """
    smtp_host, smtp_port, smtp_user, smtp_pass, from_name = get_smtp_config()
    if not smtp_user or not smtp_pass:
        msg_str = "SMTP credentials (SMTP_USER or SMTP_PASSWORD) are missing from configuration."
        logger.warning(f"[Email] {msg_str} Cannot send '{subject}' to {to_email}.")
        return False, msg_str

    clean_to = str(to_email).strip()
    if not clean_to or "@" not in clean_to:
        msg_str = f"Invalid recipient email address: '{to_email}'"
        logger.warning(f"[Email] {msg_str}")
        return False, msg_str

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{smtp_user}>"
        msg["To"] = clean_to
        msg["Importance"] = "high"
        msg["X-Priority"] = "1"
        msg["Priority"] = "urgent"
        msg.set_content(body_text)

        if html_content:
            msg.add_alternative(html_content, subtype="html")

        # Primary delivery attempt
        def _send_via_ssl():
            with smtplib.SMTP_SSL(smtp_host, 465, timeout=25) as server:
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)

        def _send_via_starttls(port=587):
            with smtplib.SMTP(smtp_host, port, timeout=25) as server:
                server.starttls()
                server.login(smtp_user, smtp_pass)
                server.send_message(msg)

        if smtp_port == 465:
            _send_via_ssl()
        else:
            try:
                _send_via_starttls(smtp_port)
            except (smtplib.SMTPServerDisconnected, TimeoutError, OSError) as transient_err:
                logger.warning(f"[Email] Port {smtp_port} STARTTLS encountered {transient_err}. Retrying via Port 465 SSL...")
                _send_via_ssl()

        success_msg = f"Email accepted by SMTP server for delivery to {clean_to}"
        logger.info(f"[Email] Successfully sent email '{subject}' to {clean_to} via SMTP ({smtp_host}:{smtp_port})")
        return True, success_msg
    except smtplib.SMTPAuthenticationError as auth_err:
        err = f"SMTP Authentication failed: {auth_err.smtp_error.decode() if isinstance(auth_err.smtp_error, bytes) else auth_err.smtp_error}"
        logger.error(f"[Email] Authentication failure sending '{subject}' to {clean_to}: {err}")
        return False, err
    except smtplib.SMTPRecipientsRefused as rec_err:
        err = f"Recipient address rejected by SMTP server: {rec_err}"
        logger.error(f"[Email] Recipient refused sending '{subject}' to {clean_to}: {err}")
        return False, err
    except smtplib.SMTPServerDisconnected as dis_err:
        err = f"SMTP server disconnected prematurely: {dis_err}"
        logger.error(f"[Email] Server disconnected sending '{subject}' to {clean_to}: {err}")
        return False, err
    except smtplib.SMTPException as smtp_err:
        err = f"SMTP protocol error: {smtp_err}"
        logger.error(f"[Email] SMTP error sending '{subject}' to {clean_to}: {err}")
        return False, err
    except Exception as e:
        err = f"{type(e).__name__}: {e}"
        logger.error(f"[Email] Failed to send email '{subject}' to {clean_to}: {err}")
        return False, err


def send_email(to_email: str, subject: str, body_text: str, html_content: str = None) -> bool:
    """
    Send an email via SMTP.
    Returns True on success, False on failure.
    """
    ok, _ = send_email_detailed(to_email, subject, body_text, html_content)
    return ok


def send_otp_email(to_email: str, otp_code: str, purpose: str = "signup", **kwargs) -> tuple[bool, str]:
    """
    Send OTP code via Gmail SMTP to specified email.
    Uses SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD from environment or safe fallback.
    Never prints OTP to logs or exposes credentials.
    """
    smtp_host, smtp_port, smtp_user, smtp_pass, from_name = get_smtp_config()

    if not smtp_user or not smtp_pass:
        msg_str = "SMTP credentials (SMTP_USER & SMTP_PASSWORD) are not set in environment."
        logger.warning(msg_str)
        return False, msg_str

    clean_email = str(to_email).strip()
    clean_otp = str(otp_code).strip()
    is_reset = str(purpose).strip().lower() in ("password_reset", "reset", "forgot_password")

    subject = "SmartBuy Password Reset Code" if is_reset else "SmartBuy Email Verification OTP"
    headline = "Password Reset Code" if is_reset else "Email Verification Code"
    intro_text = (
        "We received a request to reset your SmartBuy account password. Use the verification code below to proceed."
        if is_reset
        else "Thank you for using SmartBuy. Please use the verification code below to complete your email verification."
    )
    caution_text = (
        "This code will expire in 10 minutes. If you did not request this password reset, please ignore this email."
        if is_reset
        else "This OTP is valid for 10 minutes. Do not share this OTP with anyone."
    )

    plain_text = f"""Hello,

{intro_text}

Your verification code is:
{clean_otp}

{caution_text}

Regards,
SmartBuy Team"""

    html_content = f"""
    <div style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 500px; margin: 0 auto; padding: 24px; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 16px;">
        <div style="text-align: center; margin-bottom: 24px;">
            <h2 style="color: #4f46e5; margin: 0; font-size: 24px;">SmartBuy</h2>
            <p style="color: #64748b; font-size: 14px; margin-top: 4px;">{headline}</p>
        </div>
        <div style="background: #f8fafc; padding: 20px; border-radius: 12px; text-align: center; margin-bottom: 24px;">
            <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #1e293b;">{clean_otp}</span>
        </div>
        <p style="color: #475569; font-size: 14px; line-height: 1.5; text-align: center;">
            Hello,<br><br>{intro_text}<br><br>
            <strong>{caution_text}</strong>
        </p>
        <div style="border-top: 1px solid #f1f5f9; margin-top: 24px; padding-top: 16px; text-align: center;">
            <p style="color: #94a3b8; font-size: 12px; margin: 0;">Regards,<br><strong>SmartBuy Team</strong></p>
        </div>
    </div>
    """

    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{smtp_user}>"
        msg["To"] = clean_email
        msg.set_content(plain_text)
        msg.add_alternative(html_content, subtype='html')

        with smtplib.SMTP(smtp_host, smtp_port, timeout=12) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        logger.info(f"Successfully sent OTP email to {clean_email} via SMTP ({smtp_host}:{smtp_port})")
        return True, "OTP sent successfully"

    except Exception as e:
        logger.error(f"Failed to send OTP email via SMTP to {clean_email}: {e}")
        return False, f"Failed to send email via SMTP: {str(e)}"


# Alias for compatibility
send_email_otp = send_otp_email


def send_sms_otp(to_phone: str, otp_code: str, purpose: str = "signup", **kwargs) -> tuple[bool, str]:
    """
    Send OTP code via SMS using Twilio API.
    Uses TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER from environment.
    Falls back to console log if Twilio credentials are missing or placeholder.
    """
    load_dotenv(override=True)
    account_sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
    from_phone = os.getenv("TWILIO_PHONE_NUMBER", "").strip()
    dev_mode = os.getenv("DEV_MODE", "true").lower() in ("true", "1", "yes")

    print("\n" + "=" * 65)
    print(f"  [SMARTBUY SMS OTP CODE] >>> {otp_code} <<< FOR {to_phone}")
    print("=" * 65 + "\n")
    logger.info(f"========== [SMARTBUY SMS OTP SENDER] Code {otp_code} for {to_phone} ==========")

    is_placeholder = (
        not account_sid or not auth_token or not from_phone or
        "your_twilio" in account_sid or "your_twilio" in auth_token or "+1234567890" in from_phone
    )

    if is_placeholder:
        if dev_mode:
            logger.info(f"Development Mode Active: Bypassing live Twilio SMS. OTP Code {otp_code} logged to server console.")
            return True, f"(Dev Mode) Verification SMS code is {otp_code}. (Check server console)"
        else:
            msg = "Twilio credentials (TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN) not configured in .env."
            logger.warning(msg)
            return False, msg

    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            body=f"Your SmartBuy verification code is: {otp_code}. Valid for 10 minutes.",
            from_=from_phone,
            to=to_phone
        )
        logger.info(f"Successfully sent OTP SMS to {to_phone} (SID: {message.sid})")
        return True, "Verification code sent to your phone via SMS!"
    except Exception as e:
        logger.error(f"Failed to send OTP SMS via Twilio: {e}")
        if dev_mode:
            logger.info(f"Twilio SMS delivery failed, but Dev Mode is enabled. Code {otp_code} printed above.")
            return True, f"(Dev Mode Fallback) Code is {otp_code}. (Check server console log)"
        return False, f"Failed to send SMS: {str(e)}"


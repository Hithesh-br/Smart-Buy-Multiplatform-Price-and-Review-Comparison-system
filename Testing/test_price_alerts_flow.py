import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import unittest
from unittest.mock import patch
from app import app
from database import create_price_alert, check_and_trigger_price_alerts, get_user_price_alerts, delete_price_alert

class TestPriceAlerts(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    @patch('otp_utils.send_email')
    def test_alert_creation_does_not_send_email(self, mock_send_email):
        """Verify that creating/activating a price alert does NOT send an email."""
        data = {
            "email": "test_alert_user@example.com",
            "product_name": "Test Smartphone XYZ",
            "current_price": 25000,
            "target_price": 20000,
            "alert_mode": "price",
            "platform": "gececom",
            "product_url": "http://127.0.0.1:5000/gececom"
        }
        ok, msg, alert_doc = create_price_alert(data)
        self.assertTrue(ok, f"Alert creation failed: {msg}")
        self.assertIsNotNone(alert_doc)
        self.assertEqual(alert_doc["target_price"], 20000)
        self.assertEqual(alert_doc["alert_mode"], "price")
        self.assertEqual(alert_doc["target_pct"], 20.0)

        # Crucial check: send_email must NOT be called on creation/activation
        mock_send_email.assert_not_called()
        print("PASS: No email sent on alert creation/activation.")

        # Now test triggering when price actually drops to 19,999 (<= target_price 20000)
        with patch('otp_utils.send_email', return_value=True) as mock_trigger_email:
            results = check_and_trigger_price_alerts("Test Smartphone XYZ", 19999, platform="gececom")
            self.assertGreater(results["triggered"], 0, "Alert should have triggered for price 19999 <= 20000")
            mock_trigger_email.assert_called()
            print("PASS: Email sent when actual price (19999) dropped to/below target (20000).")

        # Cleanup
        if alert_doc and "id" in alert_doc:
            delete_price_alert(alert_doc["id"])

    @patch('otp_utils.send_email')
    def test_percent_mode_conversion_and_no_activation_email(self, mock_send_email):
        """Verify that percent mode converts accurately and does not send email on activation."""
        data = {
            "email": "test_alert_pct@example.com",
            "product_name": "Test Laptop ABC",
            "current_price": 50000,
            "target_pct": 10.0,
            "alert_mode": "percent",
            "platform": "gececom"
        }
        ok, msg, alert_doc = create_price_alert(data)
        self.assertTrue(ok)
        self.assertEqual(alert_doc["target_price"], 45000)
        self.assertEqual(alert_doc["alert_mode"], "percent")
        mock_send_email.assert_not_called()
        print("PASS: Percent mode converted target_price to 45000 and sent no activation email.")

        # Cleanup
        if alert_doc and "id" in alert_doc:
            delete_price_alert(alert_doc["id"])

if __name__ == "__main__":
    unittest.main()

"""
Verification script for Drop Price user recipient routing.
Tests:
1. Linking existing alerts from buysmart260@gmail.com to active user Harsha (hitheshharsha486@gmail.com).
2. Invoking simulate_and_trigger_price_drop with an alert.
3. Ensuring the recipient of the price drop notification email is hitheshharsha486@gmail.com.
4. Testing via Flask test client: POST /api/price-alerts/<alert_id>/simulate-drop with logged in session.
"""
import os
import sys

# Ensure project root is on path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from database import (
    get_db,
    simulate_and_trigger_price_drop,
    trigger_test_price_alert,
    get_user_price_alerts,
    get_user_by_email
)
from app import app

def main():
    db = get_db()
    if db is None:
        print("FAIL: Could not connect to MongoDB.")
        return False

    print("Step 1: Fix any alerts where email was buysmart260@gmail.com")
    harsha_user = db.users.find_one({"email": "hitheshharsha486@gmail.com"})
    if not harsha_user:
        print("FAIL: harsha_user not found in db.users")
        return False
    harsha_uid = str(harsha_user.get("id") or harsha_user.get("_id"))
    res = db.price_alerts.update_many(
        {"email": "buysmart260@gmail.com"},
        {"$set": {
            "email": "hitheshharsha486@gmail.com",
            "user_id": harsha_uid,
            "user_name": "Harsha"
        }}
    )
    print(f"Updated {res.modified_count} alerts from buysmart260@gmail.com to hitheshharsha486@gmail.com.")

    print("\nStep 2: Pick an alert owned by Harsha to simulate drop price")
    test_alert = db.price_alerts.find_one({"email": "hitheshharsha486@gmail.com"})
    if not test_alert:
        print("FAIL: No alert found for Harsha")
        return False

    aid = str(test_alert["_id"])
    target_p = int(test_alert.get("target_price") or 1500)
    new_price = max(1, target_p - 100)
    print(f"Testing alert ID: {aid} (product: '{test_alert.get('product_name')}', target: ₹{target_p}, new: ₹{new_price})")

    # Direct python function call
    ok, msg, res_data = simulate_and_trigger_price_drop(
        alert_id=aid,
        new_price=new_price,
        current_user_id=harsha_uid,
        current_user_email="hitheshharsha486@gmail.com",
        current_user_name="Harsha"
    )

    print(f"Direct simulate_and_trigger_price_drop result: ok={ok}, msg={msg}")
    assert ok is True, f"Failed: {msg}"
    assert res_data["to_email"] == "hitheshharsha486@gmail.com", f"Expected recipient hitheshharsha486@gmail.com but got {res_data['to_email']}"
    assert res_data["email_sent"] is True, f"Email delivery failed: {res_data}"
    print(f"PASS: Live price-drop email was dispatched to user email: {res_data['to_email']}")

    print("\nStep 3: Test via Flask client POST /api/price-alerts/<alert_id>/simulate-drop with active user session")
    client = app.test_client()
    with client.session_transaction() as sess:
        sess['user_id'] = harsha_uid
        sess['email'] = "hitheshharsha486@gmail.com"

    resp = client.post(
        f"/api/price-alerts/{aid}/simulate-drop",
        json={"new_price": new_price - 50}
    )
    print(f"HTTP response: status={resp.status_code}, data={resp.get_json()}")
    assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}"
    resp_json = resp.get_json()
    assert resp_json["success"] is True
    assert resp_json["data"]["to_email"] == "hitheshharsha486@gmail.com"
    assert resp_json["data"]["email_sent"] is True
    print(f"PASS: Endpoint successfully routed to session user: {resp_json['data']['to_email']}")

    print("\nStep 4: Verify price alerts query returns all alerts for user Harsha")
    alerts = get_user_price_alerts(email="hitheshharsha486@gmail.com", user_id=harsha_uid)
    print(f"Found {len(alerts)} alerts for Harsha.")
    assert len(alerts) > 0, "No alerts found for Harsha"

    print("\nALL PRICE DROP USER RECIPIENT CHECKS PASSED SUCCESSFULLY!")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

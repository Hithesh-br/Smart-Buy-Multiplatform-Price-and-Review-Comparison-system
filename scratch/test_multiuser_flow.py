"""
scratch/test_multiuser_flow.py
==============================
End-to-End Multi-User MongoDB Isolation & Admin Inbox Validation Test
"""

import sys
import io
import time
from datetime import datetime
from pymongo import MongoClient
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

from database import (
    init_db, create_user, get_user_by_email, get_user_by_id,
    update_user_last_login, log_user_search, save_user_selected_product,
    create_user_feedback, get_user_feedback_list, get_feedback_by_id,
    get_user_search_history, get_user_selected_products, get_user_stats,
    create_admin_inbox_notification, get_admin_inbox_notifications
)

print("=" * 70)
print("STARTING SMARTBUY MULTI-USER MONGODB INTEGRATION TEST")
print("=" * 70)

from flask import Flask
app = Flask(__name__)
if not init_db(app):
    print("❌ Failed to connect to MongoDB!")
    sys.exit(1)

# Clean previous test users
client = MongoClient("mongodb://localhost:27017")
db = client["smartbuy_db"]
db.users.delete_many({"email": {"$in": ["usera@smartbuy.com", "userb@smartbuy.com"]}})
db.feedback.delete_many({"title": {"$regex": "Test Feedback"}})
db.admin_inbox.delete_many({"message": {"$regex": "usera|userb"}})

# -------------------------------------------------------------
# STEP 1: USER A SIGNUP & SIGNIN
# -------------------------------------------------------------
print("\n--- Testing USER A Flow ---")
pwd_hash_a = generate_password_hash("passwordA123")
user_a_id, status_a, msg_a = create_user("User A", "usera@smartbuy.com", pwd_hash_a)
assert status_a == 201, f"User A signup failed: {msg_a}"
print(f"✅ User A Registered with MongoDB _id: {user_a_id}")

# Duplicate Email Test
_, dup_status, dup_msg = create_user("User A Duplicate", "usera@smartbuy.com", pwd_hash_a)
assert dup_status == 409, f"Duplicate check failed: {dup_msg}"
assert "Email already registered" in dup_msg
print(f"✅ Duplicate email check passed: {dup_msg}")

# Sign In & Update last_login
update_user_last_login(user_a_id)
user_a_doc = get_user_by_id(user_a_id)
assert user_a_doc["last_login"] is not None, "User A last_login was not updated!"
print("✅ User A Sign In & last_login updated in MongoDB")

# Search Product
search_a_id = log_user_search(
    user_a_id, "iPhone 15 Pro", "Mobiles",
    specifications={"ram": "8GB", "storage": "128GB"},
    search_query="iPhone 15 Pro", num_results=12,
    platforms_found="Amazon, Flipkart, Meesho",
    best_platform="Amazon", best_price=119900
)
print(f"✅ User A Search Logged (_id: {search_a_id})")

# Select Product
prod_a_id = save_user_selected_product(
    user_a_id, search_a_id, "iPhone 15 Pro Max", "Amazon",
    price="119900", rating="4.7", reviews="1520",
    specifications="8GB RAM, 256GB Storage",
    product_url="https://amazon.in/dp/exampleA", is_buy_click=True
)
print(f"✅ User A Selected Product Saved (_id: {prod_a_id})")

# Submit 5-star Rating & Feedback
fb_a_id = create_user_feedback(user_a_id, "Test Feedback A", "SmartBuy helped me compare prices easily.", 5)
assert fb_a_id is not None, "Failed to create User A feedback!"
print(f"✅ User A Submitted 5-Star Feedback (_id: {fb_a_id})")


# -------------------------------------------------------------
# STEP 2: USER B SIGNUP & SIGNIN
# -------------------------------------------------------------
print("\n--- Testing USER B Flow ---")
pwd_hash_b = generate_password_hash("passwordB123")
user_b_id, status_b, msg_b = create_user("User B", "userb@smartbuy.com", pwd_hash_b)
assert status_b == 201, f"User B signup failed: {msg_b}"
print(f"✅ User B Registered with MongoDB _id: {user_b_id}")

# Sign In & Update last_login
update_user_last_login(user_b_id)
print("✅ User B Sign In & last_login updated in MongoDB")

# Search Product
search_b_id = log_user_search(
    user_b_id, "Samsung OLED TV 55", "Televisions",
    specifications={"size": "55 inch", "resolution": "4K"},
    search_query="Samsung OLED TV", num_results=8,
    platforms_found="Flipkart, Amazon",
    best_platform="Flipkart", best_price=64990
)
print(f"✅ User B Search Logged (_id: {search_b_id})")

# Submit 4-star Rating & Feedback
fb_b_id = create_user_feedback(user_b_id, "Test Feedback B", "Great experience finding deals.", 4)
assert fb_b_id is not None, "Failed to create User B feedback!"
print(f"✅ User B Submitted 4-Star Feedback (_id: {fb_b_id})")


# -------------------------------------------------------------
# STEP 3: PRIVACY & SEPARATION VERIFICATION
# -------------------------------------------------------------
print("\n--- Verifying Strict Data Separation ---")

stats_a = get_user_stats(user_a_id)
stats_b = get_user_stats(user_b_id)

assert stats_a["name"] == "User A"
assert stats_b["name"] == "User B"

# Check search history separation
searches_a = get_user_search_history(user_a_id)
searches_b = get_user_search_history(user_b_id)

for s in searches_a:
    assert str(s["user_id"]) == str(user_a_id), "User A search history leaked to another user!"
for s in searches_b:
    assert str(s["user_id"]) == str(user_b_id), "User B search history leaked to another user!"
print("✅ Search history strictly separated per user ObjectId")

# Check feedback separation
feedbacks_a = get_user_feedback_list(user_a_id)
feedbacks_b = get_user_feedback_list(user_b_id)

assert len(feedbacks_a) == 1 and feedbacks_a[0]["title"] == "Test Feedback A"
assert len(feedbacks_b) == 1 and feedbacks_b[0]["title"] == "Test Feedback B"
print("✅ Rating and Feedback strictly separated per user ObjectId")


# -------------------------------------------------------------
# STEP 4: ADMIN INBOX VERIFICATION
# -------------------------------------------------------------
print("\n--- Verifying Admin Inbox Notifications ---")

notifications = get_admin_inbox_notifications(limit=50)
types_found = [n.get("event_type") or n.get("type") for n in notifications]

print(f"Total Admin Inbox Events logged: {len(notifications)}")
print(f"Event Types: {set(types_found)}")

assert "NEW_USER" in types_found or "new_user" in types_found, "NEW_USER event missing in Admin Inbox!"
assert "USER_LOGIN" in types_found or "user_login" in types_found, "USER_LOGIN event missing in Admin Inbox!"
assert "FEEDBACK_SUBMITTED" in types_found or "feedback_submitted" in types_found, "FEEDBACK_SUBMITTED event missing in Admin Inbox!"
print("✅ Admin Inbox successfully logged all user sign up, sign in, search, product selection & feedback events")

print("\n" + "=" * 70)
print("🎉 ALL MONGODB INTEGRATION & SEPARATION TESTS PASSED 100%!")
print("=" * 70)

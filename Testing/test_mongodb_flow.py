"""
test_mongodb_flow.py
====================
End-to-end test script verifying MongoDB integration for SmartBuy.
Tests:
1. MongoDB Connection Ping & Collection Setup
2. Sign Up Data storage in smartbuy_db.users & NEW_USER in admin_inbox
3. Sign In verification, last_login update, session user_id handling & USER_LOGIN in admin_inbox
4. Product Search History storage in smartbuy_db.search_history & PRODUCT_SEARCH in admin_inbox
5. Product Selection & Buy Button Data storage in smartbuy_db.selected_products & BUY_CLICK in admin_inbox
6. Feedback & Rating storage in smartbuy_db.feedback & FEEDBACK_SUBMITTED in admin_inbox
7. User Data Privacy (filtering by user_id = current_user_id)
8. Admin Access Control (403 Forbidden for non-admin)
"""

import sys
import io
import time
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from bson import ObjectId

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

print("=" * 60)
print("1. TESTING MONGODB CONNECTION & INITIALIZATION")
print("=" * 60)

import database
from database import (
    init_db, client, create_user, get_user_by_email, get_user_by_id,
    update_user_last_login, log_user_search, get_user_search_history,
    save_user_selected_product, get_user_selected_products,
    create_user_feedback, get_user_feedback_list, create_admin_inbox_notification,
    get_admin_inbox_notifications, get_user_stats, to_object_id
)

# Test init_db output
success = init_db()
if not success or database.db is None:
    print("FAILED: MongoDB initialization failed!")
    sys.exit(1)

# Verify collections exist
collections = database.db.list_collection_names()
print(f"Collections in smartbuy_db: {collections}")
required_collections = ["users", "search_history", "selected_products", "feedback", "admin_inbox"]
for col in required_collections:
    assert col in collections, f"Missing required collection: {col}"
print("✔ All required collections present in smartbuy_db")

print()
print("=" * 60)
print("2. TESTING SIGN UP DATA (smartbuy_database.db.users)")
print("=" * 60)

test_email_1 = f"testuser_{int(time.time())}@example.com"
test_email_2 = f"testuser2_{int(time.time())}@example.com"
password_raw = "SecretPass123"
password_hash = generate_password_hash(password_raw)

# Create user 1
uid1_str, status_code, msg = create_user("Hithesh Test", test_email_1, password_hash)
print(f"create_user response: uid={uid1_str}, status={status_code}, msg={msg}")
assert status_code == 201, f"Expected 201, got {status_code}"
assert uid1_str is not None, "User ID string should not be None"

# Verify in MongoDB smartbuy_database.db.users directly
u1_doc = database.db.users.find_one({"_id": ObjectId(uid1_str)})
print("User 1 document in MongoDB:")
print(f"  name: {u1_doc.get('name')}")
print(f"  email: {u1_doc.get('email')}")
print(f"  is_admin: {u1_doc.get('is_admin')}")
print(f"  created_at: {u1_doc.get('created_at')}")
print(f"  last_login: {u1_doc.get('last_login')}")
assert u1_doc["name"] == "Hithesh Test"
assert u1_doc["email"] == test_email_1
assert u1_doc["is_admin"] is False
assert u1_doc["last_login"] is None
assert u1_doc["password_hash"] != password_raw, "Password MUST NOT be stored in plain text!"
assert check_password_hash(u1_doc["password_hash"], password_raw), "Password hash check failed"
print("✔ Sign Up user document verified in smartbuy_database.db.users")

# Test duplicate email check
_, dup_status, dup_msg = create_user("Duplicate User", test_email_1, password_hash)
print(f"Duplicate signup test status code: {dup_status} (Expected 409)")
assert dup_status == 409, f"Expected 409 conflict, got {dup_status}"
print("✔ Duplicate email check verified (HTTP 409)")

# Create user 2 for privacy testing
uid2_str, _, _ = create_user("Second User", test_email_2, password_hash)

print()
print("=" * 60)
print("3. TESTING SIGN IN DATA & LAST LOGIN UPDATE")
print("=" * 60)

# Retrieve user for signin
fetched_user = get_user_by_email(test_email_1)
assert fetched_user is not None
assert check_password_hash(fetched_user["password_hash"], password_raw)
session_user_id = fetched_user["id"]
print(f"Flask session['user_id'] = {session_user_id} (Type: {type(session_user_id)})")

# Update last_login
update_user_last_login(session_user_id)
updated_u1 = database.db.users.find_one({"_id": ObjectId(session_user_id)})
print(f"Updated last_login in MongoDB: {updated_u1.get('last_login')}")
assert updated_u1.get("last_login") is not None, "last_login should be updated after sign in"
print("✔ Sign In verification & last_login update verified")

print()
print("=" * 60)
print("4. TESTING PRODUCT SEARCH HISTORY (smartbuy_database.db.search_history)")
print("=" * 60)

specs = {"brand": "Samsung", "ram": "8GB", "storage": "256GB"}
search_id = log_user_search(
    user_id=session_user_id,
    product_name="Samsung Galaxy S24",
    category="Mobiles",
    specifications=specs,
    search_query="Samsung Galaxy S24 8GB 256GB",
    num_results=15,
    platforms_found="Amazon, Flipkart, Meesho"
)
print(f"log_user_search search_id: {search_id}")
assert search_id is not None

# Verify document in smartbuy_database.db.search_history
sh_doc = database.db.search_history.find_one({"_id": ObjectId(search_id)})
print("Search History document in MongoDB:")
print(f"  user_id: {sh_doc.get('user_id')} (Type: {type(sh_doc.get('user_id'))})")
print(f"  product_name: {sh_doc.get('product_name')}")
print(f"  category: {sh_doc.get('category')}")
print(f"  selected_specifications: {sh_doc.get('selected_specifications')}")
print(f"  search_query: {sh_doc.get('search_query')}")
print(f"  searched_at: {sh_doc.get('searched_at')}")

assert isinstance(sh_doc["user_id"], ObjectId), "user_id in search_history MUST be ObjectId"
assert sh_doc["user_id"] == ObjectId(session_user_id)
assert sh_doc["product_name"] == "Samsung Galaxy S24"
assert sh_doc["category"] == "Mobiles"
assert sh_doc["selected_specifications"] == specs
assert sh_doc["search_query"] == "Samsung Galaxy S24 8GB 256GB"
print("✔ Product Search History verified in smartbuy_database.db.search_history")

print()
print("=" * 60)
print("5. TESTING PRODUCT SELECTION & BUY BUTTON (smartbuy_database.db.selected_products)")
print("=" * 60)

selected_id = save_user_selected_product(
    user_id=session_user_id,
    search_id=search_id,
    product_name="Samsung Galaxy S24 5G",
    platform="Amazon",
    price="₹79,999",
    rating="4.5",
    reviews="1250 reviews",
    specifications=specs,
    image_url="https://m.media-amazon.com/images/I/s24.jpg",
    product_url="https://www.amazon.in/dp/B0CS5X857Q",
    is_buy_click=True
)
print(f"save_user_selected_product selected_id: {selected_id}")
assert selected_id is not None

sp_doc = database.db.selected_products.find_one({"_id": ObjectId(selected_id)})
print("Selected Products document in MongoDB:")
print(f"  user_id: {sp_doc.get('user_id')} (Type: {type(sp_doc.get('user_id'))})")
print(f"  product_name: {sp_doc.get('product_name')}")
print(f"  platform: {sp_doc.get('platform')}")
print(f"  price: {sp_doc.get('price')}")
print(f"  rating: {sp_doc.get('rating')}")
print(f"  review_count: {sp_doc.get('review_count')}")
print(f"  product_url: {sp_doc.get('product_url')}")
print(f"  selected_at: {sp_doc.get('selected_at')}")

assert isinstance(sp_doc["user_id"], ObjectId), "user_id in selected_products MUST be ObjectId"
assert sp_doc["user_id"] == ObjectId(session_user_id)
assert sp_doc["platform"] == "Amazon"
assert sp_doc["price"] == "₹79,999"
print("✔ Product Selection & Buy Button verified in smartbuy_database.db.selected_products")

print()
print("=" * 60)
print("6. TESTING FEEDBACK AND RATING (smartbuy_database.db.feedback)")
print("=" * 60)

fb_id = create_user_feedback(
    user_id=session_user_id,
    rating=5,
    title="Excellent comparison",
    message="SmartBuy helped me compare prices easily."
)
print(f"create_user_feedback fb_id: {fb_id}")
assert fb_id is not None

fb_doc = database.db.feedback.find_one({"_id": ObjectId(fb_id)})
print("Feedback document in MongoDB:")
print(f"  user_id: {fb_doc.get('user_id')} (Type: {type(fb_doc.get('user_id'))})")
print(f"  rating: {fb_doc.get('rating')}")
print(f"  title: {fb_doc.get('title')}")
print(f"  message: {fb_doc.get('message')}")
print(f"  created_at: {fb_doc.get('created_at')}")

assert isinstance(fb_doc["user_id"], ObjectId), "user_id in feedback MUST be ObjectId"
assert fb_doc["user_id"] == ObjectId(session_user_id)
assert fb_doc["rating"] == 5
assert fb_doc["title"] == "Excellent comparison"
print("✔ Feedback & Rating verified in smartbuy_database.db.feedback")

print()
print("=" * 60)
print("7. TESTING ADMIN SMARTBUY INBOX (smartbuy_database.db.admin_inbox)")
print("=" * 60)

admin_inbox_logs = get_admin_inbox_notifications(limit=50)
print(f"Total Admin Inbox notifications logged: {len(admin_inbox_logs)}")
event_types = [log.get("event_type") for log in admin_inbox_logs]
print(f"Log Event Types recorded: {event_types}")

for required_event in ["NEW_USER", "USER_LOGIN", "PRODUCT_SEARCH", "BUY_CLICK", "FEEDBACK_SUBMITTED"]:
    assert required_event in event_types, f"Missing required admin inbox event: {required_event}"

print("✔ Admin SmartBuy Inbox activity recording verified")

print()
print("=" * 60)
print("8. TESTING USER DATA PRIVACY")
print("=" * 60)

u1_searches = get_user_search_history(session_user_id)
u2_searches = get_user_search_history(uid2_str)

print(f"User 1 search count: {len(u1_searches)}")
print(f"User 2 search count: {len(u2_searches)}")

assert len(u1_searches) == 1, "User 1 should see only their own search"
assert len(u2_searches) == 0, "User 2 MUST NOT see User 1's search!"

u1_feedback = get_user_feedback_list(session_user_id)
u2_feedback = get_user_feedback_list(uid2_str)
assert len(u1_feedback) == 1, "User 1 should see only their own feedback"
assert len(u2_feedback) == 0, "User 2 MUST NOT see User 1's feedback!"

print("✔ User Data Privacy strictly enforced (User A cannot see User B's data)")

print()
print("=" * 60)
print("9. TESTING FLASK APP ROUTE ACCESS & ADMIN SECURITY")
print("=" * 60)

from app import app

with app.test_client() as c:
    # Test home page
    r_home = c.get('/')
    assert r_home.status_code == 200, f"Home page HTTP {r_home.status_code}"
    print("✔ Home page route HTTP 200 OK")

    # Test unauthenticated access to admin dashboard -> redirects to admin login
    r_admin_unauth = c.get('/admin/dashboard')
    assert r_admin_unauth.status_code in [302, 403], f"Unauthenticated admin access HTTP {r_admin_unauth.status_code}"
    print("✔ Unauthenticated admin access blocked correctly")

    # Sign in as non-admin user Hithesh
    c.post('/signin', data={'email': test_email_1, 'password': password_raw})
    
    # Try accessing admin dashboard as normal user -> 403 Forbidden
    r_admin_norm = c.get('/admin/dashboard')
    assert r_admin_norm.status_code == 403, f"Normal user accessing admin page expected 403, got {r_admin_norm.status_code}"
    print("✔ Non-admin user receiving 403 Forbidden on admin dashboard verified")

print()
print("=" * 60)
print("ALL MONGODB INTEGRATION TESTS PASSED SUCCESSFULLY! 🎉")
print("=" * 60)

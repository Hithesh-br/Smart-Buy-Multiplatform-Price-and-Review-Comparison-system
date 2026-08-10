"""
database.py
===========
MongoDB database layer for SmartBuy:
- Users Collection (smartbuy_db.users)
- Search History Collection (smartbuy_db.search_history)
- Selected Products Collection (smartbuy_db.selected_products)
- User Feedback Collection (smartbuy_db.feedback)
- Admin SmartBuy Inbox Collection (smartbuy_db.admin_inbox)
"""

import os
import logging
from datetime import datetime
# pyrefly: ignore [missing-import]
from pymongo import MongoClient, ASCENDING, DESCENDING
# pyrefly: ignore [missing-import]
from pymongo.errors import PyMongoError
# pyrefly: ignore [missing-import]
from bson import ObjectId

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "smartbuy_db"

logger = logging.getLogger("smartbuy.database")

# Initialize PyMongo Client
client = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=5000
)

db = None


def to_object_id(val):
    """Convert value to BSON ObjectId safely."""
    if not val:
        return None
    if isinstance(val, ObjectId):
        return val
    if isinstance(val, str) and ObjectId.is_valid(val):
        try:
            return ObjectId(val)
        except Exception:
            return None
    return None


def format_doc(doc):
    """Format MongoDB document dict into Jinja2/Flask compatible dict format."""
    if not doc:
        return None
    res = dict(doc)
    if "_id" in res:
        res["id"] = str(res["_id"])
        res["_id"] = str(res["_id"])

    for k, v in list(res.items()):
        if isinstance(v, ObjectId):
            res[k] = str(v)
        elif isinstance(v, datetime):
            res[k] = v.strftime("%Y-%m-%d %H:%M:%S")

    if "is_admin" in res:
        res["is_admin"] = bool(res["is_admin"])
    return res


def init_db(app=None):
    """
    Initialize MongoDB connection & verify server status via ping command.
    Ensures required collections and indexes exist.
    """
    global db
    try:
        # Ping MongoDB server
        client.admin.command("ping")
        db = client[DB_NAME]
        print("MongoDB Connected Successfully")
        print(f"Database: {DB_NAME}")

        collections = [
            "users", "search_history", "selected_products",
            "feedback", "admin_inbox", "search_queries", "inbox_messages"
        ]
        existing = db.list_collection_names()
        for col in collections:
            if col not in existing:
                db.create_collection(col)

        # Create indexes
        db.users.create_index([("email", ASCENDING)], unique=True)
        db.search_history.create_index([("user_id", ASCENDING), ("searched_at", DESCENDING)])
        db.selected_products.create_index([("user_id", ASCENDING), ("selected_at", DESCENDING)])
        db.feedback.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
        db.admin_inbox.create_index([("created_at", DESCENDING)])
        db.search_queries.create_index([("query", ASCENDING)], unique=True)
        db.inbox_messages.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])

        # Ensure default administrator account exists
        admin_email = "admin@smartbuy.com"
        if not db.users.find_one({"email": admin_email}):
            from werkzeug.security import generate_password_hash
            db.users.insert_one({
                "name": "System Administrator",
                "email": admin_email,
                "password_hash": generate_password_hash("admin123"),
                "is_admin": True,
                "created_at": datetime.utcnow(),
                "last_login": None
            })

        return True

    except Exception as e:
        db = None
        print("MongoDB Connection Failed")
        print(f"Please make sure MongoDB Server is running on:")
        print(f"{MONGO_URI}")
        print(f"Error details: {e}")
        logger.error(f"MongoDB connection exception: {e}")
        return False


# ════════════════════ USER AUTHENTICATION ════════════════════

def create_user(name: str, email: str, password_hash: str):
    """
    Create a new user account in MongoDB (smartbuy_db.users).
    Returns tuple: (user_id_str, status_code, message)
    """
    if not name or not email or not password_hash:
        return None, 400, "Please enter valid account details"

    email_clean = email.strip().lower()
    name_clean = name.strip()

    if db is None:
        return None, 500, "MongoDB service is currently unavailable"

    try:
        # Check if email already exists
        existing = db.users.find_one({"email": email_clean})
        if existing:
            return None, 409, "Email already registered. Please sign in."

        user_doc = {
            "name": name_clean,
            "email": email_clean,
            "password_hash": password_hash,
            "is_admin": False,
            "created_at": datetime.utcnow(),
            "last_login": None
        }

        res = db.users.insert_one(user_doc)
        user_id_obj = res.inserted_id
        user_id_str = str(user_id_obj)

        # Create Admin Inbox Notification (NEW_USER)
        try:
            create_admin_inbox_notification(
                user_id=user_id_obj,
                user_name=name_clean,
                email=email_clean,
                event_type="NEW_USER",
                title="New SmartBuy User",
                message=f"A new user registered on SmartBuy: {name_clean} ({email_clean})"
            )
        except Exception as e_admin:
            logger.warning(f"Admin notification failure: {e_admin}")

        return user_id_str, 201, "Account created successfully"

    except PyMongoError as pe:
        logger.error(f"PyMongoError creating user ({email_clean}): {pe}")
        return None, 500, "Database error creating account"
    except Exception as e:
        logger.error(f"Exception creating user ({email_clean}): {e}")
        return None, 500, "Unable to create account"


def get_user_by_email(email: str) -> dict | None:
    """Find a user by email address in smartbuy_db.users."""
    if not email or db is None:
        return None
    email_clean = email.strip().lower()

    try:
        doc = db.users.find_one({"email": email_clean})
        return format_doc(doc) if doc else None
    except Exception as e:
        logger.error(f"Error fetching user by email: {e}")
        return None


def get_user_by_id(user_id) -> dict | None:
    """Find a user by MongoDB ObjectId in smartbuy_db.users."""
    if not user_id or db is None:
        return None

    oid = to_object_id(user_id)
    if not oid:
        return None

    try:
        doc = db.users.find_one({"_id": oid})
        return format_doc(doc) if doc else None
    except Exception as e:
        logger.error(f"Error fetching user by ID: {e}")
        return None


def update_user_last_login(user_id) -> None:
    """Update last_login timestamp when user signs in and create USER_LOGIN admin notification."""
    if not user_id or db is None:
        return
    oid = to_object_id(user_id)
    if not oid:
        return

    try:
        user = db.users.find_one({"_id": oid})
        db.users.update_one(
            {"_id": oid},
            {"$set": {"last_login": datetime.utcnow()}}
        )

        if user:
            user_name = user.get("name", "User")
            email = user.get("email", "")
            create_admin_inbox_notification(
                user_id=oid,
                user_name=user_name,
                email=email,
                event_type="USER_LOGIN",
                title="User Sign In",
                message=f"User logged in: {user_name} ({email})"
            )
    except Exception as e:
        logger.error(f"Error updating last_login: {e}")


def update_user_name(user_id, name: str) -> bool:
    """Update user's full name in smartbuy_db.users."""
    if not user_id or not name or db is None:
        return False
    oid = to_object_id(user_id)
    if not oid:
        return False

    name_clean = name.strip()
    try:
        res = db.users.update_one({"_id": oid}, {"$set": {"name": name_clean}})
        return res.matched_count > 0
    except Exception as e:
        logger.error(f"Error updating user name: {e}")
        return False


def update_user_password(user_id, password_hash: str) -> bool:
    """Update user's password hash in smartbuy_db.users."""
    if not user_id or not password_hash or db is None:
        return False
    oid = to_object_id(user_id)
    if not oid:
        return False

    try:
        res = db.users.update_one({"_id": oid}, {"$set": {"password_hash": password_hash}})
        return res.matched_count > 0
    except Exception as e:
        logger.error(f"Error updating user password: {e}")
        return False


# ════════════════════ PRODUCT SEARCH HISTORY ════════════════════

def log_search_query(query: str) -> None:
    """Log global search query for autocomplete & analytics."""
    if not query or len(query.strip()) < 2 or db is None:
        return
    q = query.strip().lower()
    try:
        db.search_queries.update_one(
            {"query": q},
            {
                "$inc": {"search_count": 1},
                "$set": {"last_searched_at": datetime.utcnow()},
                "$setOnInsert": {"created_at": datetime.utcnow()}
            },
            upsert=True
        )
    except Exception as e:
        logger.error(f"Error logging search query: {e}")


def log_user_search(user_id, product_name: str, category: str = "", specifications=None, search_query: str = "", num_results: int = 0, platforms_found: str = "", best_platform: str = "", best_price=None, platforms=None) -> str | None:
    """
    Log a specific authenticated user search to smartbuy_db.search_history.
    Every search is connected to currently logged-in user.
    """
    if not user_id or not product_name or db is None:
        return None

    oid = to_object_id(user_id)
    if not oid:
        return None

    p_name = product_name.strip()
    cat = (category or "General").strip()

    if isinstance(specifications, dict):
        selected_specs = specifications
    elif isinstance(specifications, str) and specifications.strip():
        selected_specs = {"details": specifications.strip()}
    else:
        selected_specs = {}

    s_query = (search_query or p_name).strip()
    plat_list = platforms if isinstance(platforms, list) else ["Amazon", "Flipkart", "Meesho"]
    plat_str = platforms_found or ", ".join(plat_list)

    try:
        search_doc = {
            "user_id": oid,
            "product_name": p_name,
            "category": cat,
            "selected_specifications": selected_specs,
            "search_query": s_query,
            "num_results": num_results,
            "platforms_found": plat_str,
            "platforms": plat_list,
            "best_platform": best_platform or "SmartBuy",
            "best_price": best_price or 0,
            "searched_at": datetime.utcnow()
        }

        res = db.search_history.insert_one(search_doc)
        search_id_obj = res.inserted_id
        search_id_str = str(search_id_obj)

        # Admin Inbox notification (PRODUCT_SEARCH)
        try:
            user = get_user_by_id(oid)
            user_name = user["name"] if user else "User"
            email = user["email"] if user else ""
            create_admin_inbox_notification(
                user_id=oid,
                user_name=user_name,
                email=email,
                event_type="PRODUCT_SEARCH",
                title="Product Search Performed",
                message=f"{user_name} searched for '{s_query}' in category '{cat}'."
            )
        except Exception as e_admin:
            logger.warning(f"Admin notification failure: {e_admin}")

        return search_id_str

    except Exception as e:
        logger.error(f"Error logging user search: {e}")
        return None


def get_user_search_history(user_id, limit: int = 50) -> list:
    """Retrieve search history for logged-in user filtered by user_id = current_user_id."""
    if not user_id or db is None:
        return []
    current_user_id = to_object_id(user_id)
    if not current_user_id:
        return []

    try:
        cursor = db.search_history.find({"user_id": current_user_id}).sort("searched_at", DESCENDING).limit(limit)
        return [format_doc(d) for d in cursor]
    except Exception as e:
        logger.error(f"Error fetching user search history: {e}")
        return []


# ════════════════════ SMARTBUY INBOX (USER NOTIFICATIONS) ════════════════════

def create_inbox_message(user_id, message_type: str, title: str, message: str, related_search_id=None) -> str | None:
    """Create an activity notification message in user's private SmartBuy Inbox."""
    if not user_id or not title or not message or db is None:
        return None

    oid = to_object_id(user_id)
    if not oid:
        return None

    try:
        doc = {
            "user_id": oid,
            "message_type": message_type.strip(),
            "title": title.strip(),
            "message": message.strip(),
            "related_search_id": to_object_id(related_search_id),
            "is_read": False,
            "created_at": datetime.utcnow()
        }
        res = db.inbox_messages.insert_one(doc)
        return str(res.inserted_id)
    except Exception as e:
        logger.error(f"Error creating inbox message: {e}")
        return None


def get_user_inbox_messages(user_id, limit: int = 50) -> list:
    """Retrieve inbox messages for a logged-in user filtered by user_id = current_user_id."""
    if not user_id or db is None:
        return []
    current_user_id = to_object_id(user_id)
    if not current_user_id:
        return []

    try:
        cursor = db.inbox_messages.find({"user_id": current_user_id}).sort("created_at", DESCENDING).limit(limit)
        return [format_doc(d) for d in cursor]
    except Exception as e:
        logger.error(f"Error fetching user inbox messages: {e}")
        return []


def get_user_unread_inbox_count(user_id) -> int:
    """Return count of unread inbox messages for logged-in user filtered by user_id = current_user_id."""
    if not user_id or db is None:
        return 0
    current_user_id = to_object_id(user_id)
    if not current_user_id:
        return 0

    try:
        return db.inbox_messages.count_documents({"user_id": current_user_id, "is_read": False})
    except Exception as e:
        logger.error(f"Error getting unread inbox count: {e}")
        return 0


def mark_inbox_message_read(message_id, user_id) -> bool:
    """Mark specific inbox message as read owned by user_id."""
    if not message_id or not user_id or db is None:
        return False
    mid = to_object_id(message_id)
    uid = to_object_id(user_id)
    if not mid or not uid:
        return False

    try:
        res = db.inbox_messages.update_one({"_id": mid, "user_id": uid}, {"$set": {"is_read": True}})
        return res.matched_count > 0
    except Exception as e:
        logger.error(f"Error marking inbox message read: {e}")
        return False


def delete_inbox_message(message_id, user_id) -> bool:
    """Delete inbox message owned by user_id."""
    if not message_id or not user_id or db is None:
        return False
    mid = to_object_id(message_id)
    uid = to_object_id(user_id)
    if not mid or not uid:
        return False

    try:
        res = db.inbox_messages.delete_one({"_id": mid, "user_id": uid})
        return res.deleted_count > 0
    except Exception as e:
        logger.error(f"Error deleting inbox message: {e}")
        return False


def get_inbox_message_by_id(message_id, user_id) -> dict | None:
    """Retrieve inbox message by ID checking ownership."""
    if not message_id or not user_id or db is None:
        return None
    mid = to_object_id(message_id)
    uid = to_object_id(user_id)
    if not mid or not uid:
        return None

    try:
        doc = db.inbox_messages.find_one({"_id": mid, "user_id": uid})
        return format_doc(doc) if doc else None
    except Exception as e:
        logger.error(f"Error getting inbox message by ID: {e}")
        return None


# ════════════════════ USER FEEDBACK & RATING ════════════════════

def create_user_feedback(user_id, title: str, message: str, rating: int) -> str | None:
    """
    Store user feedback in smartbuy_db.feedback.
    - rating: 1 to 5
    - title & message cannot be empty
    """
    if not user_id or not title or not message or db is None:
        return None

    current_user_id = to_object_id(user_id)
    if not current_user_id:
        return None

    try:
        rating_val = int(rating)
        if rating_val < 1 or rating_val > 5:
            return None
    except (ValueError, TypeError):
        return None

    t_clean = title.strip()
    m_clean = message.strip()
    if not t_clean or not m_clean:
        return None

    try:
        fb_doc = {
            "user_id": current_user_id,
            "rating": rating_val,
            "title": t_clean,
            "message": m_clean,
            "created_at": datetime.utcnow()
        }

        res = db.feedback.insert_one(fb_doc)
        fb_id_str = str(res.inserted_id)

        # Admin Inbox notification (FEEDBACK_SUBMITTED)
        try:
            u = get_user_by_id(current_user_id)
            user_name = u["name"] if u else "User"
            email = u["email"] if u else ""
            create_admin_inbox_notification(
                user_id=current_user_id,
                user_name=user_name,
                email=email,
                event_type="FEEDBACK_SUBMITTED",
                title="New User Feedback Submitted",
                message=f"{user_name} submitted rating {rating_val}/5: '{t_clean}'"
            )
        except Exception as e_admin:
            logger.warning(f"Admin notification failure: {e_admin}")

        return fb_id_str

    except Exception as e:
        logger.error(f"Error creating user feedback: {e}")
        return None


def get_user_feedback_list(user_id) -> list:
    """Retrieve feedback items created by logged-in user filtered by user_id = current_user_id."""
    if not user_id or db is None:
        return []
    current_user_id = to_object_id(user_id)
    if not current_user_id:
        return []

    try:
        cursor = db.feedback.find({"user_id": current_user_id}).sort("created_at", DESCENDING)
        return [format_doc(d) for d in cursor]
    except Exception as e:
        logger.error(f"Error fetching user feedback list: {e}")
        return []


def get_feedback_by_id(feedback_id, user_id) -> dict | None:
    """Retrieve a specific feedback item ensuring it belongs to user_id."""
    if not feedback_id or not user_id or db is None:
        return None
    fid = to_object_id(feedback_id)
    uid = to_object_id(user_id)
    if not fid or not uid:
        return None

    try:
        doc = db.feedback.find_one({"_id": fid, "user_id": uid})
        return format_doc(doc) if doc else None
    except Exception as e:
        logger.error(f"Error getting feedback by ID: {e}")
        return None


def update_user_feedback(feedback_id, user_id, title: str, message: str, rating: int) -> bool:
    """Update feedback item owned by user_id."""
    if not feedback_id or not user_id or not title or not message or db is None:
        return False
    fid = to_object_id(feedback_id)
    uid = to_object_id(user_id)
    if not fid or not uid:
        return False

    try:
        rating_val = int(rating)
        if rating_val < 1 or rating_val > 5:
            return False
    except (ValueError, TypeError):
        return False

    try:
        res = db.feedback.update_one(
            {"_id": fid, "user_id": uid},
            {"$set": {"title": title.strip(), "message": message.strip(), "rating": rating_val, "updated_at": datetime.utcnow()}}
        )
        return res.matched_count > 0
    except Exception as e:
        logger.error(f"Error updating user feedback: {e}")
        return False


def delete_user_feedback(feedback_id, user_id) -> bool:
    """Delete feedback item owned by user_id."""
    if not feedback_id or not user_id or db is None:
        return False
    fid = to_object_id(feedback_id)
    uid = to_object_id(user_id)
    if not fid or not uid:
        return False

    try:
        res = db.feedback.delete_one({"_id": fid, "user_id": uid})
        return res.deleted_count > 0
    except Exception as e:
        logger.error(f"Error deleting user feedback: {e}")
        return False


# ════════════════════ SELECTED PRODUCTS & COMPARISONS ════════════════════

def save_user_selected_product(user_id, search_id, product_name: str, platform: str, price="", rating="", reviews="", specifications="", image_url="", product_url="", is_buy_click=False) -> str | None:
    """
    Save a user selected product / compared product / buy click to smartbuy_db.selected_products.
    Uses REAL scraped values (product_name, platform, price, rating, review_count, specs, product_url, image_url).
    """
    if not user_id or not product_name or not platform or db is None:
        return None

    current_user_id = to_object_id(user_id)
    if not current_user_id:
        return None

    p_name = product_name.strip()
    plat = platform.strip()

    if isinstance(specifications, dict):
        specs = specifications
    elif isinstance(specifications, str) and specifications.strip():
        specs = {"details": specifications.strip()}
    else:
        specs = {}

    rev_val = str(reviews or "")

    try:
        prod_doc = {
            "user_id": current_user_id,
            "search_id": to_object_id(search_id) if search_id else None,
            "product_name": p_name,
            "platform": plat,
            "price": str(price or ""),
            "rating": str(rating or ""),
            "review_count": rev_val,
            "reviews": rev_val,
            "specifications": specs,
            "image_url": image_url or "",
            "product_url": product_url or "",
            "selected_at": datetime.utcnow()
        }

        res = db.selected_products.insert_one(prod_doc)
        prod_id_str = str(res.inserted_id)

        # Admin Inbox Notification (BUY_CLICK / PRODUCT_SELECTED)
        event_type = "BUY_CLICK" if is_buy_click else "PRODUCT_SELECTED"
        title = "Buy Button Clicked" if is_buy_click else "Product Selected"
        try:
            u = get_user_by_id(current_user_id)
            user_name = u["name"] if u else "User"
            email = u["email"] if u else ""
            create_admin_inbox_notification(
                user_id=current_user_id,
                user_name=user_name,
                email=email,
                event_type=event_type,
                title=title,
                message=f"{user_name} selected '{p_name}' on {plat} at price {price or 'N/A'}."
            )
        except Exception as e_admin:
            logger.warning(f"Admin notification failure: {e_admin}")

        return prod_id_str

    except Exception as e:
        logger.error(f"Error saving selected product: {e}")
        return None


def get_user_selected_products(user_id, limit: int = 50) -> list:
    """Retrieve selected products for logged-in user filtered by user_id = current_user_id."""
    if not user_id or db is None:
        return []
    current_user_id = to_object_id(user_id)
    if not current_user_id:
        return []

    try:
        cursor = db.selected_products.find({"user_id": current_user_id}).sort("selected_at", DESCENDING).limit(limit)
        return [format_doc(d) for d in cursor]
    except Exception as e:
        logger.error(f"Error fetching user selected products: {e}")
        return []


def get_latest_user_selected_product(user_id) -> dict | None:
    """Retrieve the most recent selected product for logged-in user."""
    prods = get_user_selected_products(user_id, limit=1)
    return prods[0] if prods else None


def save_user_comparison(user_id, search_id, platform: str, product_name: str, price: str, rating: str, reviews: str, product_url: str, image_url: str = "", is_best_deal: int = 0) -> str | None:
    """Save product comparison selection for authenticated user in smartbuy_db.selected_products."""
    return save_user_selected_product(user_id, search_id, product_name, platform, price, rating, reviews, "", image_url, product_url)


def get_user_saved_comparisons(user_id, limit: int = 50) -> list:
    """Retrieve saved comparisons for logged-in user."""
    return get_user_selected_products(user_id, limit)


def get_user_stats(user_id) -> dict:
    """Retrieve user stats for profile page filtered by user_id = current_user_id."""
    stats = {
        "total_searches": 0,
        "total_feedback": 0,
        "total_saved_comparisons": 0,
        "total_selected_deals": 0,
        "total_inbox_messages": 0,
        "created_at": None,
        "last_login": None,
        "name": "",
        "email": "",
        "recent_searches": [],
        "selected_products": [],
        "feedbacks": [],
        "user_rating": None
    }
    user = get_user_by_id(user_id)
    if not user:
        return stats

    stats["name"] = user.get("name", "")
    stats["email"] = user.get("email", "")
    stats["created_at"] = user.get("created_at", None)
    stats["last_login"] = user.get("last_login", None)

    searches = get_user_search_history(user_id, limit=50)
    feedbacks = get_user_feedback_list(user_id)
    deals = get_user_selected_products(user_id, limit=50)
    inbox = get_user_inbox_messages(user_id, limit=50)

    stats["total_searches"] = len(searches)
    stats["recent_searches"] = searches
    stats["selected_products"] = deals
    stats["feedbacks"] = feedbacks
    stats["total_feedback"] = len(feedbacks)
    stats["total_selected_deals"] = len(deals)
    stats["total_saved_comparisons"] = len(deals)
    stats["total_inbox_messages"] = len(inbox)
    if feedbacks:
        stats["user_rating"] = feedbacks[0].get("rating", 5)

    return stats


# ════════════════════ GLOBAL QUERIES ════════════════════

def get_recent_queries(limit: int = 100) -> list:
    """Retrieve recently searched queries ordered by most recent."""
    if db is None:
        return []
    try:
        cursor = db.search_queries.find({}, {"query": 1}).sort("last_searched_at", DESCENDING).limit(limit)
        return [doc["query"] for doc in cursor if "query" in doc]
    except Exception as e:
        logger.error(f"Error getting recent queries: {e}")
        return []


def get_trending_queries(limit: int = 10) -> list:
    """Return most-searched queries ordered by search_count descending."""
    if db is None:
        return []
    try:
        cursor = db.search_queries.find({}, {"query": 1}).sort([("search_count", DESCENDING), ("last_searched_at", DESCENDING)]).limit(limit)
        return [doc["query"] for doc in cursor if "query" in doc]
    except Exception as e:
        logger.error(f"Error getting trending queries: {e}")
        return []


def get_query_count() -> int:
    """Return total number of unique queries logged."""
    if db is None:
        return 0
    try:
        return db.search_queries.count_documents({})
    except Exception as e:
        logger.error(f"Error getting query count: {e}")
        return 0


# ════════════════════ ADMIN SMARTBUY INBOX & MANAGEMENT ════════════════════

def create_admin_inbox_notification(user_id=None, user_name="", email="", event_type="GENERAL", title="", message="") -> str | None:
    """
    Create an admin inbox event in smartbuy_db.admin_inbox.
    Events: NEW_USER, USER_LOGIN, PRODUCT_SEARCH, PRODUCT_SELECTED, BUY_CLICK, FEEDBACK_SUBMITTED.
    """
    if db is None:
        return None

    uid = to_object_id(user_id) if user_id else None
    u_name = (user_name or "").strip()
    u_email = (email or "").strip().lower()

    if uid and (not u_name or not u_email):
        user_doc = db.users.find_one({"_id": uid})
        if user_doc:
            u_name = u_name or user_doc.get("name", "User")
            u_email = u_email or user_doc.get("email", "")

    try:
        admin_doc = {
            "user_id": uid,
            "user_name": u_name or "System",
            "email": u_email,
            "type": (event_type or "new_user").lower(),
            "event_type": event_type.strip(),
            "title": title.strip() or event_type.strip(),
            "message": message.strip(),
            "created_at": datetime.utcnow(),
            "is_read": False
        }

        res = db.admin_inbox.insert_one(admin_doc)
        return str(res.inserted_id)
    except Exception as e:
        logger.error(f"Error creating admin inbox notification: {e}")
        return None


def get_admin_inbox_notifications(limit: int = 100) -> list:
    """Retrieve all notifications in Admin SmartBuy Inbox."""
    if db is None:
        return []
    try:
        cursor = db.admin_inbox.find().sort("created_at", DESCENDING).limit(limit)
        notifications = []
        for doc in cursor:
            n = format_doc(doc)
            if not n.get("user_name") or n.get("user_name") == "System":
                uid = n.get("user_id")
                if uid:
                    u = get_user_by_id(uid)
                    if u:
                        n["user_name"] = u.get("name", "User")
                        n["email"] = u.get("email", "")
            notifications.append(n)
        return notifications
    except Exception as e:
        logger.error(f"Error fetching admin inbox notifications: {e}")
        return []


def get_admin_unread_count() -> int:
    """Get count of unread admin inbox notifications."""
    if db is None:
        return 0
    try:
        return db.admin_inbox.count_documents({"is_read": False})
    except Exception as e:
        logger.error(f"Error getting admin unread count: {e}")
        return 0


def mark_admin_notification_read(notification_id) -> bool:
    """Mark an admin notification as read."""
    if not notification_id or db is None:
        return False
    nid = to_object_id(notification_id)
    if not nid:
        return False

    try:
        res = db.admin_inbox.update_one({"_id": nid}, {"$set": {"is_read": True}})
        return res.matched_count > 0
    except Exception as e:
        logger.error(f"Error marking admin notification read: {e}")
        return False


def delete_admin_notification(notification_id) -> bool:
    """Delete an admin notification."""
    if not notification_id or db is None:
        return False
    nid = to_object_id(notification_id)
    if not nid:
        return False

    try:
        res = db.admin_inbox.delete_one({"_id": nid})
        return res.deleted_count > 0
    except Exception as e:
        logger.error(f"Error deleting admin notification: {e}")
        return False


def get_all_users_for_admin() -> list:
    """Retrieve list of all registered users with summary metrics for Admin Dashboard & Users view."""
    if db is None:
        return []
    try:
        cursor = db.users.find().sort("created_at", DESCENDING)
        users = []
        for doc in cursor:
            u = format_doc(doc)
            uid = u["id"]
            u["total_searches"] = len(get_user_search_history(uid, limit=500))
            u["total_selected_products"] = len(get_user_selected_products(uid, limit=500))
            u["total_feedback"] = len(get_user_feedback_list(uid))
            users.append(u)
        return users
    except Exception as e:
        logger.error(f"Error fetching all users for admin: {e}")
        return []


def get_user_full_details_for_admin(user_id) -> dict | None:
    """Retrieve comprehensive details of a specific user for Admin User Details view."""
    user = get_user_by_id(user_id)
    if not user:
        return None

    try:
        searches = get_user_search_history(user_id, limit=100)
        selected_products = get_user_selected_products(user_id, limit=100)
        feedbacks = get_user_feedback_list(user_id)

        return {
            **user,
            "searches": searches,
            "selected_products": selected_products,
            "feedbacks": feedbacks,
            "total_searches": len(searches),
            "total_selected_products": len(selected_products),
            "total_feedback": len(feedbacks),
        }
    except Exception as e:
        logger.error(f"Error fetching user full details: {e}")
        return user

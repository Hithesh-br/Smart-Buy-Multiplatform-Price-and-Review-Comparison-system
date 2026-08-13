"""
api.py
======
Smart-Buy: Multiplatform Price Review Comparison System
======================================================
Flask API Blueprint & Route Handlers:
- / (Home UI)
- /search (Product search and side-by-side comparison page)
- /api/search (JSON API endpoint)
- /autocomplete (Live search query suggestions)
- /api/health (System status health check)
"""

import json
import time
import re
import logging
from functools import wraps
from flask import Blueprint, render_template, request, redirect, jsonify, session, flash, url_for, Response, stream_with_context
from werkzeug.security import generate_password_hash, check_password_hash
from search_engine import fetch_all_products_parallel, process_results, stream_platform_results
from cache import get_cached_search, set_cached_search
from database import (
    log_search_query, get_trending_queries, get_query_count,
    create_user, get_user_by_email, get_user_by_id, update_user_name,
    update_user_password, log_user_search, get_user_search_history,
    create_user_feedback, get_user_feedback_list, get_feedback_by_id,
    update_user_feedback, delete_user_feedback, get_user_stats,
    create_inbox_message, get_user_inbox_messages, get_user_unread_inbox_count,
    mark_inbox_message_read, delete_inbox_message, get_inbox_message_by_id,
    save_user_comparison, get_user_saved_comparisons, save_user_selected_product,
    get_user_selected_products, get_latest_user_selected_product,
    update_user_last_login, create_admin_inbox_notification,
    get_admin_inbox_notifications, get_admin_unread_count,
    mark_admin_notification_read, delete_admin_notification,
    get_all_users_for_admin, get_user_full_details_for_admin
)
from autocomplete_engine import build_trie_from_history, get_autocomplete_suggestions
from search.normalizer import normalize_query, build_search_query
from search.filters import parse_filter_params
from utils import clean_text

logger = logging.getLogger("smartbuy.api")
api_bp = Blueprint("api", __name__)


def login_required(f):
    """Decorator to require login for user routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please Sign Up or Sign In to access your profile.", "warning")
            return redirect(url_for('api.signin', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """Decorator to require Admin role for admin routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            flash("Please sign in with Administrator credentials.", "warning")
            return redirect(url_for('api.admin_login', next=request.url))
        user = get_user_by_id(user_id)
        if not user or not user.get('is_admin'):
            return render_template('403.html'), 403
        return f(*args, **kwargs)
    return decorated_function


@api_bp.app_errorhandler(404)
def not_found_error(error):
    if request.path.startswith('/api/'):
        return jsonify({"status": "error", "message": "Resource not found"}), 404
    return render_template('index.html', category_hints=CATEGORY_HINTS, trending_searches=get_trending_queries(limit=8)), 404


@api_bp.app_errorhandler(500)
def internal_server_error(error):
    logger.error(f"Internal Server Error: {error}", exc_info=True)
    if request.path.startswith('/api/'):
        return jsonify({"status": "error", "message": "Internal Server Error"}), 500
    return render_template('index.html', category_hints=CATEGORY_HINTS, trending_searches=get_trending_queries(limit=8)), 500


# Category hint chips for home page
CATEGORY_HINTS = [
    {"label": "Mobiles",         "icon": "fas fa-mobile-alt",   "query": "Mobile Phone"},
    {"label": "Laptops",         "icon": "fas fa-laptop",        "query": "Laptop"},
    {"label": "Headphones",      "icon": "fas fa-headphones",    "query": "Headphones"},
    {"label": "Smartwatches",    "icon": "fas fa-clock",         "query": "Smartwatch"},
    {"label": "Televisions",     "icon": "fas fa-tv",            "query": "Television"},
    {"label": "Grocery",         "icon": "fas fa-shopping-basket","query": "Grocery"},
    {"label": "Fashion",         "icon": "fas fa-tshirt",        "query": "Fashion"},
    {"label": "Beauty",          "icon": "fas fa-spa",           "query": "Beauty Products"},
    {"label": "Sports",          "icon": "fas fa-futbol",        "query": "Sports Equipment"},
    {"label": "Books",           "icon": "fas fa-book",          "query": "Books"},
    {"label": "Home Appliances", "icon": "fas fa-blender",       "query": "Home Appliances"},
    {"label": "Gaming",          "icon": "fas fa-gamepad",       "query": "Gaming"},
    {"label": "Baby Care",       "icon": "fas fa-baby",          "query": "Baby Products"},
    {"label": "Pet Supplies",    "icon": "fas fa-paw",           "query": "Pet Supplies"},
    {"label": "Furniture",       "icon": "fas fa-couch",         "query": "Furniture"},
    {"label": "Kitchen",         "icon": "fas fa-utensils",      "query": "Kitchen Appliances"},
]

# Trie cache
_trie_cache = {'trie': None, 'built_at': 0}
TRIE_TTL = 120


def get_current_trie():
    now = time.time()
    if _trie_cache['trie'] is None or (now - _trie_cache['built_at'] > TRIE_TTL):
        _trie_cache['trie'] = build_trie_from_history()
        _trie_cache['built_at'] = now
    return _trie_cache['trie']


@api_bp.route('/', methods=['GET'])
def index():
    """Home page — dynamic search-first UI."""
    trending = get_trending_queries(limit=8)
    return render_template('index.html',
                           category_hints=CATEGORY_HINTS,
                           trending_searches=trending)


@api_bp.route('/about', methods=['GET'])
def about():
    """About SmartBuy system page."""
    return render_template('about.html')


def normalize_external_url(url: str, platform: str = "") -> str:
    """Ensure external product link starts with valid http/https protocol."""
    if not url or url.strip() in ["#", "None", "null", "undefined", "javascript:void(0)"]:
        plat_lower = (platform or "").lower()
        if "amazon" in plat_lower:
            return "https://www.amazon.in"
        elif "flipkart" in plat_lower:
            return "https://www.flipkart.com"
        elif "meesho" in plat_lower:
            return "https://www.meesho.com"
        return "https://www.google.com"

    u = url.strip()
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("http://") or u.startswith("https://"):
        return u

    plat_lower = (platform or "").lower()
    if "amazon" in plat_lower:
        base = "https://www.amazon.in"
    elif "flipkart" in plat_lower:
        base = "https://www.flipkart.com"
    elif "meesho" in plat_lower:
        base = "https://www.meesho.com"
    else:
        base = "https://"

    if not u.startswith("/") and not base.endswith("/"):
        return base + "/" + u
    elif u.startswith("/") and base.endswith("/"):
        return base + u[1:]
    else:
        return base + u


# ── Buy Button Routes (/buy/amazon, /buy/flipkart, /buy/meesho, /deal/redirect) ──
@api_bp.route('/buy/amazon', methods=['GET'])
@api_bp.route('/buy/flipkart', methods=['GET'])
@api_bp.route('/buy/meesho', methods=['GET'])
@api_bp.route('/deal/redirect', methods=['GET'])
def handle_buy_click():
    """Handler for user clicking Buy on Amazon/Flipkart/Meesho. Checks auth; saves product in session; redirects to signup if unauthenticated."""
    deal_url_raw = request.args.get('url', '').strip()
    platform = request.args.get('platform', '').strip()
    if not platform:
        path = request.path.lower()
        if 'amazon' in path:
            platform = 'Amazon'
        elif 'flipkart' in path:
            platform = 'Flipkart'
        elif 'meesho' in path:
            platform = 'Meesho'
        else:
            platform = 'Online Store'

    product_name = request.args.get('product_name', '').strip() or request.args.get('title', '').strip() or 'Searched Product'
    price = request.args.get('price', '').strip()
    rating = request.args.get('rating', '').strip()
    reviews = request.args.get('reviews', '').strip()
    image = request.args.get('image', '').strip()
    specifications = request.args.get('specifications', '').strip()
    search_query = request.args.get('search_query', '').strip()

    deal_url = normalize_external_url(deal_url_raw, platform)

    pending_product = {
        'product_name': product_name,
        'platform': platform,
        'price': price,
        'rating': rating,
        'reviews': reviews,
        'image_url': image,
        'specifications': specifications,
        'product_url': deal_url,
        'search_query': search_query
    }

    # Save selected product in session (session["pending_product"])
    session['pending_product'] = pending_product
    session['pending_purchase'] = pending_product
    session['pending_selected_product'] = pending_product
    session['pending_deal_url'] = deal_url

    # Check if user is logged in
    if 'user_id' in session:
        user_id = session['user_id']
        user = get_user_by_id(user_id)
        user_name = user.get('name', 'User') if isinstance(user, dict) else 'User'

        save_user_selected_product(
            user_id, None, pending_product.get('product_name', 'Searched Product'),
            pending_product.get('platform', 'Online Store'), pending_product.get('price', ''),
            pending_product.get('rating', ''), pending_product.get('reviews', ''),
            pending_product.get('specifications', ''), pending_product.get('image_url', ''),
            pending_product.get('product_url', '')
        )
        return redirect(url_for('api.profile'))

    # Unauthenticated -> redirect to Sign Up
    flash("Please create an account or sign in to continue your purchase.", "info")
    return redirect(url_for('api.signup'))


@api_bp.route('/api/signup', methods=['POST'])
@api_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """
    User Registration Endpoint:
    - Supports JSON API requests (POST /api/signup) and standard HTML form POSTs (POST /signup).
    - Validates name, email, password (>=6 chars), confirm_password match.
    - Checks duplicate email (HTTP 409).
    - Hashes password using Werkzeug.
    - Saves user in database and creates Admin Inbox notification.
    - Returns HTTP 201, 400, 409, 500 with exact JSON response specification.
    """
    if request.method == 'GET':
        if 'user_id' in session:
            return redirect(url_for('api.profile'))
        return render_template('signup.html')

    # Detect if request is JSON / AJAX
    is_json_req = request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.headers.get('Accept', '') or request.path == '/api/signup'

    if request.is_json:
        data = request.get_json() or {}
        name = str(data.get('name', '')).strip()
        email = str(data.get('email', '')).strip().lower()
        password = str(data.get('password', ''))
        confirm_password = str(data.get('confirm_password', ''))
    else:
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

    # Requirement 1 & 2 Backend Validation
    if not name:
        msg = "Please enter valid account details"
        if is_json_req:
            return jsonify({"success": False, "message": msg}), 400
        return render_template('signup.html', errors=["Full Name is required."], name=name, email=email), 400

    if not email or '@' not in email or '.' not in email:
        msg = "Please enter valid account details"
        if is_json_req:
            return jsonify({"success": False, "message": msg}), 400
        return render_template('signup.html', errors=["Please enter a valid email address."], name=name, email=email), 400

    if len(password) < 6:
        msg = "Password must be at least 6 characters long."
        if is_json_req:
            return jsonify({"success": False, "message": msg}), 400
        return render_template('signup.html', errors=[msg], name=name, email=email), 400

    if password != confirm_password:
        msg = "Passwords do not match."
        if is_json_req:
            return jsonify({"success": False, "message": msg}), 400
        return render_template('signup.html', errors=[msg], name=name, email=email), 400

    # Password Hash & Database Insert
    pwd_hash = generate_password_hash(password)
    user_id, status_code, db_msg = create_user(name, email, pwd_hash)

    if status_code == 201 and user_id:
        if is_json_req:
            return jsonify({"success": True, "message": "Account created successfully"}), 201

        flash("User registered successfully and saved to MongoDB.", "success")
        return redirect(url_for('api.signin'))
    elif status_code == 409:
        msg = "Email already registered. Please sign in."
        if is_json_req:
            return jsonify({"success": False, "message": msg}), 409
        return render_template('signup.html', errors=[msg], name=name, email=email), 409
    else:
        logger.error(f"Signup database error for email {email}: {db_msg}")
        msg = "Unable to create account"
        if is_json_req:
            return jsonify({"success": False, "message": msg}), status_code or 500
        return render_template('signup.html', errors=[msg], name=name, email=email), status_code or 500



@api_bp.route('/signin', methods=['GET', 'POST'])
def signin():
    """Sign in existing user and redirect to Profile page."""
    if 'user_id' in session:
        user = get_user_by_id(session['user_id'])
        if user and user.get('is_admin'):
            return redirect(url_for('api.admin_dashboard'))
        return redirect('/profile')

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        user = get_user_by_email(email)
        if user and check_password_hash(user.get('password_hash', ''), password):
            u_id = str(user.get('id') or user.get('_id', ''))
            u_name = user.get('name', 'User')
            session['user_id'] = u_id
            session['user_name'] = u_name
            session['is_admin'] = user.get('is_admin', 0)
            update_user_last_login(u_id)

            # Transfer pending session purchase data to authenticated user account
            pending_prod = session.get('pending_product') or session.get('pending_purchase') or session.get('pending_selected_product')
            if pending_prod:
                save_user_selected_product(
                    u_id, None, pending_prod.get('product_name', ''),
                    pending_prod.get('platform', ''), pending_prod.get('price', ''),
                    pending_prod.get('rating', ''), pending_prod.get('reviews', ''),
                    pending_prod.get('specifications', ''), pending_prod.get('image_url', ''),
                    pending_prod.get('product_url', '')
                )

            flash(f"Welcome back, {u_name}! 👋", "success")
            if user.get('is_admin'):
                return redirect(url_for('api.admin_dashboard'))
            return redirect(url_for('api.profile'))
        else:
            error = "Invalid email or password."
            return render_template('signin.html', error=error, email=email)

    return render_template('signin.html')


@api_bp.route('/logout', methods=['GET'])
def logout():
    """Log out current user."""
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect('/')


@api_bp.route('/my-searches', methods=['GET'])
@login_required
def my_searches():
    """Display logged-in user's search history."""
    history = get_user_search_history(session['user_id'])
    return render_template('my_searches.html', history=history)


# ── SmartBuy Inbox Routes ──
@api_bp.route('/inbox', methods=['GET'])
@login_required
def inbox():
    """Display private SmartBuy Inbox for logged-in user."""
    messages = get_user_inbox_messages(session['user_id'])
    return render_template('inbox.html', inbox_messages=messages)


@api_bp.route('/inbox/read/<message_id>', methods=['POST'])
@login_required
def read_inbox_message(message_id):
    """Mark an inbox message as read with strict 403 ownership verification."""
    msg = get_inbox_message_by_id(message_id, session['user_id'])
    if not msg:
        return "403 Unauthorized Access", 403

    mark_inbox_message_read(message_id, session['user_id'])
    return redirect(url_for('api.inbox'))


@api_bp.route('/inbox/delete/<message_id>', methods=['POST'])
@login_required
def remove_inbox_message(message_id):
    """Delete an inbox message with strict 403 ownership verification."""
    msg = get_inbox_message_by_id(message_id, session['user_id'])
    if not msg:
        return "403 Unauthorized Access", 403

    delete_inbox_message(message_id, session['user_id'])
    flash("Notification deleted.", "info")
    return redirect(url_for('api.inbox'))


# ── Feedback & Rating Routes ──
@api_bp.route('/my-feedback', methods=['GET'])
@api_bp.route('/profile/feedback', methods=['GET'])
@login_required
def my_feedback():
    """Display or retrieve logged-in user's submitted feedback list."""
    feedbacks = get_user_feedback_list(session['user_id'])
    if request.is_json or request.headers.get('Accept') == 'application/json':
        return jsonify({"status": "success", "feedbacks": feedbacks})
    return render_template('my_feedback.html', feedbacks=feedbacks)


@api_bp.route('/feedback/new', methods=['POST'])
@api_bp.route('/profile/feedback', methods=['POST'])
@login_required
def create_feedback():
    """Submit new feedback with mandatory rating (1-5), title, and message validation."""
    title = request.form.get('title', '').strip() or (request.json.get('title', '').strip() if request.is_json else '')
    message = request.form.get('message', '').strip() or (request.json.get('message', '').strip() if request.is_json else '')
    rating_raw = request.form.get('rating', '') or (request.json.get('rating', '') if request.is_json else '')
    redirect_target = request.form.get('redirect_to', '')

    try:
        rating = int(rating_raw)
        if rating < 1 or rating > 5:
            raise ValueError()
    except (ValueError, TypeError):
        msg = "Rating is required and must be between 1 and 5 stars."
        if request.is_json:
            return jsonify({"status": "error", "message": msg}), 400
        flash(msg, "danger")
        return redirect(redirect_target if (redirect_target and redirect_target.startswith('/')) else url_for('api.profile'))

    if not title or not message:
        msg = "Feedback Title and Message are required."
        if request.is_json:
            return jsonify({"status": "error", "message": msg}), 400
        flash(msg, "danger")
        return redirect(redirect_target if (redirect_target and redirect_target.startswith('/')) else url_for('api.profile'))

    fb_id = create_user_feedback(session['user_id'], title, message, rating)
    if fb_id:
        user = get_user_by_id(session['user_id'])
        user_name = user.get('name', 'User') if isinstance(user, dict) else 'User'
        user_email = user.get('email', '') if isinstance(user, dict) else ''
        create_admin_inbox_notification(
            user_id=session['user_id'],
            user_name=user_name,
            email=user_email,
            event_type='FEEDBACK_SUBMITTED',
            title='New User Feedback',
            message=f"{user_name} submitted rating {rating}/5 stars: '{title}'"
        )
        msg = "Rating and feedback saved successfully."
        if request.is_json:
            return jsonify({"status": "success", "message": msg, "feedback_id": fb_id}), 201
        flash(msg, "success")
    else:
        msg = "Failed to save feedback. Please try again."
        if request.is_json:
            return jsonify({"status": "error", "message": msg}), 500
        flash(msg, "danger")

    return redirect(redirect_target if (redirect_target and redirect_target.startswith('/')) else url_for('api.profile'))


@api_bp.route('/feedback/edit/<feedback_id>', methods=['POST'])
@api_bp.route('/profile/feedback/<feedback_id>', methods=['PUT', 'POST'])
@login_required
def edit_feedback(feedback_id):
    """Edit an existing feedback entry owned by current user with ownership check."""
    # Check ownership first (Section 12 requirement)
    existing_fb = get_feedback_by_id(feedback_id, session['user_id'])
    if not existing_fb:
        msg = "Feedback not found or access denied."
        if request.is_json:
            return jsonify({"status": "error", "message": msg}), 403
        flash(msg, "danger")
        return redirect(url_for('api.profile'))

    title = request.form.get('title', '').strip() or (request.json.get('title', '').strip() if request.is_json else '')
    message = request.form.get('message', '').strip() or (request.json.get('message', '').strip() if request.is_json else '')
    rating_raw = request.form.get('rating', '5') or (request.json.get('rating', '5') if request.is_json else '')

    try:
        rating = int(rating_raw)
        if rating < 1 or rating > 5:
            raise ValueError()
    except (ValueError, TypeError):
        msg = "Rating must be between 1 and 5 stars."
        if request.is_json:
            return jsonify({"status": "error", "message": msg}), 400
        flash(msg, "danger")
        return redirect(url_for('api.profile'))

    if not title or not message:
        msg = "Feedback title and message are required."
        if request.is_json:
            return jsonify({"status": "error", "message": msg}), 400
        flash(msg, "danger")
        return redirect(url_for('api.profile'))

    updated = update_user_feedback(feedback_id, session['user_id'], title, message, rating)
    if updated:
        msg = "Rating and feedback updated successfully."
        if request.is_json:
            return jsonify({"status": "success", "message": msg}), 200
        flash(msg, "success")
    else:
        msg = "Unable to update feedback."
        if request.is_json:
            return jsonify({"status": "error", "message": msg}), 500
        flash(msg, "danger")
    return redirect(url_for('api.profile'))


@api_bp.route('/feedback/delete/<feedback_id>', methods=['POST'])
@api_bp.route('/profile/feedback/delete/<feedback_id>', methods=['POST'])
@api_bp.route('/profile/feedback/<feedback_id>', methods=['DELETE'])
@login_required
def delete_feedback(feedback_id):
    """Delete a feedback entry owned by current user with ownership check."""
    existing_fb = get_feedback_by_id(feedback_id, session['user_id'])
    if not existing_fb:
        msg = "Feedback not found or access denied."
        if request.is_json:
            return jsonify({"status": "error", "message": msg}), 403
        flash(msg, "danger")
        return redirect(url_for('api.profile'))

    deleted = delete_user_feedback(feedback_id, session['user_id'])
    if deleted:
        msg = "Feedback deleted successfully."
        if request.is_json:
            return jsonify({"status": "success", "message": msg}), 200
        flash(msg, "success")
    else:
        msg = "Unable to delete feedback."
        if request.is_json:
            return jsonify({"status": "error", "message": msg}), 500
        flash(msg, "danger")
    return redirect(url_for('api.profile'))


@api_bp.route('/profile', methods=['GET'])
@login_required
def profile():
    """Display user profile page with restored selected product."""
    stats = get_user_stats(session['user_id'])
    
    # Restore pending or latest selected product
    selected_product = session.get('pending_product') or session.get('pending_purchase') or session.get('pending_selected_product')
    if not selected_product:
        db_prod = get_latest_user_selected_product(session['user_id'])
        if db_prod:
            selected_product = {
                'product_name': db_prod.get('product_name', 'Searched Product'),
                'platform': db_prod.get('platform', 'Online Store'),
                'price': db_prod.get('price', ''),
                'rating': db_prod.get('rating', ''),
                'reviews': db_prod.get('reviews', ''),
                'specifications': db_prod.get('specifications', ''),
                'image_url': db_prod.get('image_url', ''),
                'product_url': db_prod.get('product_url', '')
            }

    return render_template('profile.html', stats=stats, selected_product=selected_product, restored_comparison=selected_product)


@api_bp.route('/deal/continue', methods=['GET'])
@login_required
def continue_to_deal():
    """Continue to Buy button handler — redirects user to real scraped product URL and logs Deal Opened in Inbox."""
    selected_product = session.get('pending_product') or session.get('pending_purchase') or session.get('pending_selected_product')
    if not selected_product:
        db_prod = get_latest_user_selected_product(session['user_id'])
        if db_prod:
            selected_product = db_prod

    if selected_product and selected_product.get('product_url'):
        platform = selected_product.get('platform', 'the seller website')
        p_name = selected_product.get('product_name', 'Selected Product')
        p_price = selected_product.get('price', 'N/A')
        
        # Log Deal Opened entry in user's Inbox
        create_inbox_message(
            session['user_id'], 'deal_opened', '🔗 Deal Opened',
            f"You opened this product on {platform}.\n\nProduct:\n{p_name}\n\nPrice at selection:\n{p_price}"
        )
        target_url = normalize_external_url(selected_product.get('product_url'), platform)
        return redirect(target_url)

    flash("No active selected product found.", "info")
    return redirect(url_for('api.profile'))


@api_bp.route('/profile/update-name', methods=['POST'])
@login_required
def profile_update_name():
    """Update logged-in user's name."""
    new_name = request.form.get('name', '').strip()
    if not new_name:
        flash("Full name cannot be empty.", "danger")
        return redirect(url_for('api.profile'))

    if update_user_name(session['user_id'], new_name):
        session['user_name'] = new_name
        flash("Profile name updated successfully!", "success")
    else:
        flash("Failed to update profile name.", "danger")
    return redirect(url_for('api.profile'))


@api_bp.route('/profile/change-password', methods=['POST'])
@login_required
def profile_change_password():
    """Change logged-in user's password."""
    current_password = request.form.get('current_password', '')
    new_password = request.form.get('new_password', '')
    confirm_password = request.form.get('confirm_password', '')

    user = get_user_by_id(session['user_id'])
    user_email = user.get('email', '') if isinstance(user, dict) else ''
    full_user = get_user_by_email(user_email) if user_email else None

    if not full_user or not check_password_hash(full_user.get('password_hash', ''), current_password):
        flash("Current password is incorrect.", "danger")
        return redirect(url_for('api.profile'))

    if len(new_password) < 6:
        flash("New password must be at least 6 characters long.", "danger")
        return redirect(url_for('api.profile'))

    if new_password != confirm_password:
        flash("New password and confirm password do not match.", "danger")
        return redirect(url_for('api.profile'))

    new_hash = generate_password_hash(new_password)
    if update_user_password(session['user_id'], new_hash):
        flash("Password changed successfully!", "success")
    else:
        flash("Failed to change password.", "danger")
    return redirect(url_for('api.profile'))


@api_bp.route('/search', methods=['GET'])
@api_bp.route('/search/results', methods=['GET'])
def search():
    """Main search route for side-by-side multi-platform comparison."""
    raw_q = request.args.get('q', '')
    query = clean_text(raw_q)[:100]

    price_range = request.args.get('price_range', '').strip()
    min_rating = request.args.get('min_rating', '').strip()
    sort_by = request.args.get('sort', 'best_match').strip()

    from search.normalizer import build_search_query_chain
    from search_engine import fetch_all_products_with_fallbacks

    category_val = request.args.get('category', '').strip()
    specs_list = []
    for k in ('brand', 'ram', 'storage', 'processor', 'appliance_type', 'type'):
        if request.args.get(k):
            specs_list.append(f"{k.capitalize()}: {request.args.get(k)}")
    specs_str = ", ".join(specs_list)

    query_chain = build_search_query_chain(
        brand=request.args.get('brand', ''),
        category=category_val,
        ram=request.args.get('ram', ''),
        storage=request.args.get('storage', ''),
        processor=request.args.get('processor', ''),
        appliance_type=request.args.get('appliance_type', ''),
        type_val=request.args.get('type', ''),
        q=raw_q,
    )

    query = query_chain[0] if query_chain else (query or 'Products')

    if not query:
        return redirect('/')

    # Log search for global autocomplete history
    log_search_query(query)

    # Save search URL in session if unauthenticated for seamless post-login restoration
    if 'user_id' not in session:
        session['pending_search_url'] = request.full_path

    filter_params = parse_filter_params(request.args)
    cache_key = f"{normalize_query(query)}|{json.dumps(filter_params, sort_keys=True)}"

    # Check cache
    cached_data = get_cached_search(cache_key)
    if cached_data:
        processed = cached_data
    else:
        # Execute parallel search with fallback loop
        raw_results, platform_status = fetch_all_products_with_fallbacks(query_chain)
        processed = process_results(query, raw_results, filter_params, platform_status)
        set_cached_search(cache_key, processed)

    # Log user search and send automatic inbox notifications if logged in
    user_id = session.get('user_id')
    if user_id:
        total_count = len(processed.get('all_results', []))
        platform_list = [p.capitalize() for p, items in processed.get('platform_results', {}).items() if isinstance(items, list) and len(items) > 0]
        platforms_str = ", ".join(platform_list) or "Amazon, Flipkart, Meesho"
        
        specs_dict = {}
        for k in ('brand', 'ram', 'storage', 'processor', 'appliance_type', 'type'):
            if request.args.get(k):
                specs_dict[k] = request.args.get(k)
        if not specs_dict and specs_str:
            specs_dict = {"details": specs_str}

        search_id = log_user_search(
            user_id, query, category_val or "General",
            specifications=specs_dict, search_query=query,
            num_results=total_count, platforms_found=platforms_str
        )

        # Automatic inbox message: Search Completed
        create_inbox_message(
            user_id,
            'search',
            'Search Completed 🔔',
            f"Your search for '{query}' has been completed successfully. Found {total_count} products across {platforms_str}.",
            search_id
        )

        # Automatic inbox message: Best Deal Found
        best_deal = processed.get('best_overall_deal')
        if best_deal and best_deal.get('formatted_price'):
            create_inbox_message(
                user_id,
                'best_deal',
                'Best Deal Found 🏆',
                f"The lowest price for '{query}' is ₹{best_deal['formatted_price']} on {best_deal.get('platform', 'SmartBuy').capitalize()}.",
                search_id
            )

    render_data = {
        "query": query,
        "filter_params": filter_params,
        "price_range": price_range,
        "min_rating": min_rating,
        **processed
    }

    sort_views = processed.get('sort_views', {})
    results_for_view = sort_views.get(sort_by, sort_views.get('best_match', []))
    return render_template('results.html', sort_by=sort_by,
                           results_for_view=results_for_view, **render_data)


@api_bp.route('/api/search/stream', methods=['GET'])
def api_search_stream():
    """
    Server-Sent Events (SSE) streaming endpoint (Req 3).
    Streams results to frontend progressively as each scraper completes:
      Amazon results received -> Display Amazon
      Flipkart results received -> Display Flipkart
      Meesho results received -> Display Meesho
    """
    raw_q = request.args.get('q', '')
    query = clean_text(raw_q)[:100]

    category_val = request.args.get('category', '').strip()
    filter_params = parse_filter_params(request.args)
    cache_key = f"{normalize_query(query)}|cat:{category_val}|{json.dumps(filter_params, sort_keys=True)}"

    def generate_events():
        if not query:
            yield f"event: error\ndata: {json.dumps({'error': 'Query parameter q is required'})}\n\n"
            return

        # 1. Check Short-Term Cache (60s TTL)
        cached_data = get_cached_search(cache_key, ttl_seconds=60)
        if cached_data:
            logger.info(f"SSE: Yielding instant cached results for '{query}'")
            yield f"event: cached_result\ndata: {json.dumps(cached_data)}\n\n"
            return

        # Log query
        log_search_query(query)

        # 2. Yield Initial Status Event
        platform_status = {
            "Amazon": {"available": False, "searching": True, "count": 0},
            "Flipkart": {"available": False, "searching": True, "count": 0},
            "Meesho": {"available": False, "searching": True, "count": 0},
        }
        yield f"event: status\ndata: {json.dumps({'platform_status': platform_status, 'query': query})}\n\n"

        # 3. Stream platform scrapers concurrently
        raw_results = {"Amazon": [], "Flipkart": [], "Meesho": []}
        t_start = time.time()

        for platform, items, dt, status in stream_platform_results(query):
            raw_results[platform] = items
            platform_status[platform] = status

            # Process single platform items for immediate rendering
            single_raw = {platform: items}
            single_processed = process_results(query, single_raw, filter_params, {platform: status})
            plat_items = single_processed.get("platform_results", {}).get(platform, [])

            event_payload = {
                "platform": platform,
                "items": plat_items,
                "status": status,
                "duration": dt
            }
            yield f"event: platform_result\ndata: {json.dumps(event_payload)}\n\n"

        # 4. All scrapers completed — compute overall comparison & badges
        processed = process_results(query, raw_results, filter_params, platform_status)

        # Store in 60s cache
        set_cached_search(cache_key, processed)

        total_dt = round(time.time() - t_start, 2)
        processed["total_duration"] = total_dt
        logger.info(f"SSE Search Completed for '{query}' in {total_dt:.2f}s")

        yield f"event: complete\ndata: {json.dumps(processed)}\n\n"

    return Response(stream_with_context(generate_events()), mimetype='text/event-stream')


@api_bp.route('/api/search', methods=['GET'])
def api_search():
    """JSON API endpoint returning raw & processed multi-platform search data."""
    raw_q = request.args.get('q', '')
    query = clean_text(raw_q)[:100]

    if not query:
        return jsonify({"error": "Query parameter 'q' is required", "status": "error"}), 400

    raw_results, platform_status = fetch_all_products_parallel(query)
    processed = process_results(query, raw_results, platform_status=platform_status)

    return jsonify({
        "status": "success",
        "query": query,
        "platform_status": platform_status,
        "results": processed.get("platform_results", {}),
        "all_results": processed.get("all_results", []),
        "best_per_platform": processed.get("best_per_platform", {}),
        "overall_best": processed.get("overall_best"),
        "ai_summary": processed.get("ai_summary"),
        "top_prices_data": processed.get("top_prices_data"),
        "top_prices": processed.get("top_prices"),
        "best_overall_deal": processed.get("best_overall_deal"),
        "savings_info": processed.get("savings_info"),
        "exact_matching_data": processed.get("exact_matching_data"),
        "similar_products": processed.get("similar_products"),
    })


@api_bp.route('/api/search-suggestions', methods=['GET'])
@api_bp.route('/autocomplete', methods=['GET'])
@api_bp.route('/api/autocomplete', methods=['GET'])
def search_suggestions():
    """
    Intelligent Search Suggestions API:
    - Returns product suggestions from ALL categories (Electronics, Appliances, Kitchen,
      Groceries, Personal Care, Beauty, Fashion, Baby, Pet, Stationery, Sports, Furniture, Books, etc.)
    - Supports prefix matching, token matching, RapidFuzz fuzzy search, and typo correction.
    - Displays 10–15 relevant suggestions.
    """
    q = request.args.get('q', '').strip()
    if not q or len(q) < 2:
        return jsonify({"status": "success", "query": q, "suggestions": []})

    trie = get_current_trie()
    suggestions = get_autocomplete_suggestions(trie, q, limit=12)
    return jsonify({
        "status": "success",
        "query": q,
        "suggestions": suggestions
    })



@api_bp.route('/api/health', methods=['GET'])
def health_check():
    """System health check endpoint."""
    return jsonify({
        "status": "online",
        "system": "Smart-Buy: Multiplatform Price Review Comparison System",
        "timestamp": time.time(),
        "database_queries_logged": get_query_count(),
    })


# ════════════════════ ADMIN PORTAL & SMARTBUY ADMIN INBOX ════════════════════

@api_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """Admin Portal Sign In."""
    if 'user_id' in session:
        user = get_user_by_id(session['user_id'])
        if user and user.get('is_admin'):
            return redirect(url_for('api.admin_dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = get_user_by_email(email)
        if user and user.get('is_admin') and check_password_hash(user.get('password_hash', ''), password):
            u_id = str(user.get('id') or user.get('_id', ''))
            u_name = user.get('name', 'Admin')
            session['user_id'] = u_id
            session['user_name'] = u_name
            session['is_admin'] = 1
            update_user_last_login(u_id)
            flash("Welcome to the SmartBuy Admin Portal!", "success")
            return redirect(url_for('api.admin_dashboard'))
        else:
            error = "Invalid Administrator credentials."
            return render_template('admin_login.html', error=error, email=email)

    return render_template('admin_login.html')


@api_bp.route('/admin/dashboard', methods=['GET'])
@admin_required
def admin_dashboard():
    """Admin Dashboard overview."""
    users = get_all_users_for_admin()
    notifications = get_admin_inbox_notifications(limit=10)
    query_count = get_query_count()
    unread_admin = get_admin_unread_count()
    return render_template('admin_dashboard.html',
                           users=users,
                           notifications=notifications,
                           total_users=len(users),
                           total_queries=query_count,
                           unread_admin=unread_admin)


@api_bp.route('/admin/inbox', methods=['GET'])
@admin_required
def admin_inbox():
    """SmartBuy Admin Inbox displaying all system notifications."""
    notifications = get_admin_inbox_notifications(limit=100)
    return render_template('admin_inbox.html', notifications=notifications)


@api_bp.route('/admin/inbox/read/<notification_id>', methods=['POST'])
@admin_required
def admin_inbox_read(notification_id):
    """Mark an admin notification as read."""
    mark_admin_notification_read(notification_id)
    return redirect(url_for('api.admin_inbox'))


@api_bp.route('/admin/inbox/delete/<notification_id>', methods=['POST'])
@admin_required
def admin_inbox_delete(notification_id):
    """Delete an admin notification."""
    delete_admin_notification(notification_id)
    flash("Notification removed.", "info")
    return redirect(url_for('api.admin_inbox'))


@api_bp.route('/admin/users', methods=['GET'])
@admin_required
def admin_users():
    """Admin view listing all registered users."""
    users = get_all_users_for_admin()
    return render_template('admin_users.html', users=users)


@api_bp.route('/admin/user/<user_id>', methods=['GET'])
@admin_required
def admin_user_detail(user_id):
    """Admin Detailed User Profile view."""
    user_detail = get_user_full_details_for_admin(user_id)
    if not user_detail:
        flash("User not found.", "danger")
        return redirect(url_for('api.admin_dashboard'))
    return render_template('admin_user_detail.html', user_detail=user_detail)


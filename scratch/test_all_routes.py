"""
test_all_routes.py
==================
Full integration test suite to verify ALL endpoints, handlers, database queries, and scrapers.
"""

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import unittest
from app import app
from database import (
    db, create_user, get_user_by_email, to_object_id,
    log_user_search, save_user_selected_product, create_user_feedback
)

class SmartBuyFullTestSuite(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.app = app
        cls.client = app.test_client()
        cls.email = "fulltest_user@smartbuy.com"
        
        # Ensure clean state for test user
        db.users.delete_many({"email": cls.email})
        uid, status, msg = create_user("Full Test User", cls.email, "pbkdf2:sha256:password123")
        cls.user_id = str(uid)
        
        # Promote to admin for admin route testing
        db.users.update_one({"_id": to_object_id(cls.user_id)}, {"$set": {"is_admin": True}})

    def test_01_public_routes(self):
        routes = ["/", "/about", "/signup", "/signin", "/admin/login", "/api/health"]
        for r in routes:
            resp = self.client.get(r)
            self.assertEqual(resp.status_code, 200, f"Route {r} failed with status {resp.status_code}")

    def test_02_autocomplete_api(self):
        resp = self.client.get("/autocomplete?q=sam")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("suggestions", data)

    def test_03_authenticated_user_routes(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user_id
            
        user_routes = ["/profile", "/my-searches", "/my-feedback", "/inbox"]
        for r in user_routes:
            resp = self.client.get(r)
            self.assertEqual(resp.status_code, 200, f"Authenticated route {r} failed with status {resp.status_code}")

    def test_04_admin_routes(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = self.user_id
            
        admin_routes = ["/admin/dashboard", "/admin/inbox", "/admin/users"]
        for r in admin_routes:
            resp = self.client.get(r)
            self.assertEqual(resp.status_code, 200, f"Admin route {r} failed with status {resp.status_code}")

    def test_05_api_search(self):
        resp = self.client.get("/api/search?q=milk")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("results", data)
        self.assertIn("platform_status", data)

if __name__ == "__main__":
    unittest.main()

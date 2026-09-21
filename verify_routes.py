import requests
import json

base_url = "http://127.0.0.1:5000"

print("--- Testing Routes ---")
# 1. Home
r = requests.get(f"{base_url}/")
print(f"GET / -> Status {r.status_code}")
assert r.status_code == 200, "Home failed"

# 2. Health
r = requests.get(f"{base_url}/api/health")
print(f"GET /api/health -> Status {r.status_code}, data: {r.json()}")
assert r.status_code == 200, "Health failed"

# 3. Signup
r = requests.get(f"{base_url}/signup")
print(f"GET /signup -> Status {r.status_code}")
assert r.status_code == 200, "Signup failed"

# 4. Signin
r = requests.get(f"{base_url}/signin")
print(f"GET /signin -> Status {r.status_code}")
assert r.status_code == 200, "Signin failed"

# 5. Autocomplete
r = requests.get(f"{base_url}/autocomplete?q=chia")
print(f"GET /autocomplete?q=chia -> Status {r.status_code}, suggestions: {r.json().get('suggestions', [])[:3]}")

# 6. Search Page (GET /search?q=chia seeds)
print("\n--- Testing Search Route ---")
r = requests.get(f"{base_url}/search?q=chia+seeds")
print(f"GET /search?q=chia+seeds -> Status {r.status_code}")
assert r.status_code == 200, "Search page failed"
assert "Specification Comparison" in r.text or "All Results" in r.text or "SmartBuy" in r.text
print("Search page rendered successfully with original templates!")

print("\n--- ALL BASIC CHECKS PASSED ---")

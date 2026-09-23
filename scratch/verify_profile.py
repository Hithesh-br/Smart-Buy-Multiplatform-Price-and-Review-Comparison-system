import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app
import database

def main():
    database.init_db()
    u = database.db.users.find_one({"email": "karthi@2gmail.com"})
    print("Testing for user:", u["email"], "(ID:", u["_id"], ")")

    client = app.app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = str(u["_id"])
        sess["email"] = u["email"]

    res = client.get("/profile")
    print("Profile GET status:", res.status_code)
    html = res.get_data(as_text=True)

    print("Checking Table Header 'Platform':", "<th>Platform</th>" in html or "<th>PLATFORM</th>" in html)
    print("Checking Table Header 'Price':", "<th>Price</th>" in html or "<th>PRICE</th>" in html)
    print("Checking 'Best Deal Available' in top banner:", "Price: Best Deal Available" in html)
    
    # Check top banner content
    if "Authentication Complete" in html:
        print("Top banner is present.")
        start = html.find("Price: <strong")
        end = html.find("</strong>", start)
        print("PRICE CONTENT:", ascii(html[start:end+9]))

    # Check search activity table rows
    print("\n--- Search Activity Rows Sample ---")
    for line in html.splitlines():
        if "product-detail-link" in line:
            print("Row product:", line.strip()[:120].encode('ascii', 'ignore').decode())
        if "Selected" in line and "badge bg-success-subtle" in line:
            print("Selected badge found:", line.strip().encode('ascii', 'ignore').decode())

    # Check modal presence
    print("\nChecking Modal presence:", "id=\"searchDetailModal\"" in html)
    print("Checking Modal script presence:", "searchActivityData" in html)

if __name__ == "__main__":
    main()

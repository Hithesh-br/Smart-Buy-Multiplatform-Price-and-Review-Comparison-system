import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import app
import database

def main():
    database.init_db()
    u = database.db.users.find_one({"email": "karthi@2gmail.com"})
    client = app.app.test_client()

    with client.session_transaction() as sess:
        sess["user_id"] = str(u["_id"])
        sess["email"] = u["email"]

    # Select Flipkart deal for pupkin seeds
    res = client.post("/api/select-product", json={
        "search_id": "6ab3c22c4268a57e7dfe1933",
        "query": "pupkin seeds",
        "platform": "Flipkart",
        "price": "88",
        "product_name": "Harrows Raw Pumpkin Seeds",
        "product_url": "https://www.flipkart.com",
        "image_url": ""
    })
    print("Select API status:", res.status_code)
    print("Select API response:", ascii(res.get_json()))

    # Check updated profile
    res2 = client.get("/profile")
    html = res2.get_data(as_text=True)
    start = html.find("Price: <strong")
    end = html.find("</strong>", start)
    print("Updated Banner Price:", ascii(html[start:end+9]))
    print("Updated Banner Platform Flipkart?:", "Flipkart" in html[html.find("Selected Platform:"):start])

    # Now select Meesho deal back (₹182) as the user had in screenshot
    res3 = client.post("/api/select-product", json={
        "search_id": "6ab3c22c4268a57e7dfe1933",
        "query": "pupkin seeds",
        "platform": "Meesho",
        "price": "182",
        "product_name": "Nutritoz Premium Raw Pumpkin Seeds 200g High Protein Zinc Rich Healthy Snack Best Superfood",
        "product_url": "https://www.meesho.com/nutritoz-premium-raw-pumpkin-seeds-200g-high-protein-zinc-rich-healthy-snack-best-superfood/p/bc4rhd",
        "image_url": "https://images.meesho.com/images/products/685505569/4qb0r_512.webp?width=360"
    })
    print("Restored Meesho deal status:", res3.status_code)

    res4 = client.get("/profile")
    html4 = res4.get_data(as_text=True)
    start4 = html4.find("Price: <strong")
    end4 = html4.find("</strong>", start4)
    print("Final Banner Price:", ascii(html4[start4:end4+9]))
    print("Final Banner Platform Meesho?:", "Meesho" in html4[html4.find("Selected Platform:"):start4])

if __name__ == "__main__":
    main()

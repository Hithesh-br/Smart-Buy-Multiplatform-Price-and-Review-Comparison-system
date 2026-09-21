import pytest
from app import app
import database

def test_profile_template_display_and_badges():
    database.init_db()
    user_id = '6a952c933a3bf656265613f6' # Darshan

    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user_id'] = user_id
            sess['user_email'] = 'dbr26797@gmail.com'
            sess['user_name'] = 'Darshan'

        resp = client.get('/profile')
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)

        # 1. Verify Top Banner
        assert "Authentication Complete — Ready to Purchase" in html
        assert "Flipkart" in html
        assert "₹349" in html
        # Should not display "Best Deal Available" or "Price Unavailable" in banner for this product
        assert "Selected Platform: <strong class=\"text-warning\">flipkart</strong>" not in html

        # 2. Verify Search Activity table contains badges and formatted prices
        assert "boAt Smartwatch" in html
        assert "₹1,499" in html
        assert "pilgrim face wash" in html
        assert "₹259" in html
        assert "iphone 17pro max" in html
        assert "₹134,900" in html
        assert "hp laptop charger" in html
        assert "₹649" in html
        assert "vivo t4 5g" in html
        assert "₹21,999" in html

        # 3. Verify Selected Products section contains proper prices and platforms
        assert "DK Group Microfibre Sleeping Pillow" in html
        assert "vivo S2 (256 GB Storage, 8 GB RAM)" in html
        assert "Samsung Galaxy F70 Pro 5G" in html
        assert "ShopsYes Wall Charger Accessory" in html
        assert "Kuber Industries Microfiber Pillow" in html or "Type-C Charger" in html

        # 4. Verify No "None (3)" ratings are rendered
        assert "⭐ None" not in html
        assert "Rating: ⭐ None" not in html
        assert "⭐ 0.0" not in html

        print("\nAll Profile Display Verifications PASSED!")

if __name__ == '__main__':
    test_profile_template_display_and_badges()

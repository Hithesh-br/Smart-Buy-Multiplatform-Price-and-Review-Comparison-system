from playwright.sync_api import sync_playwright

def test_modal_toggle():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("http://127.0.0.1:5000/search?q=Vivo")
        page.wait_for_load_state("networkidle")

        # Click the price alert button on the first product card
        page.wait_for_selector("button[onclick*='openPriceAlertModal']")
        page.locator("button[onclick*='openPriceAlertModal']").first.click()
        page.wait_for_selector("#priceAlertModal", state="visible")

        # Initial mode is percent: check visibility
        assert page.is_visible("#paSectionPct"), "Percent section should be visible initially"
        assert not page.is_visible("#paSectionPrice"), "Price section should be hidden initially"
        print("Initial percent mode verified: paSectionPct is visible, paSectionPrice is hidden")

        # Switch to Exact Target Price mode
        page.click("#paTabBtnPrice")
        page.wait_for_timeout(300)

        # Check visibility after switch
        assert not page.is_visible("#paSectionPct"), "Percent section should be hidden in price mode"
        assert page.is_visible("#paSectionPrice"), "Price section should be visible in price mode"
        print("Target price mode verified: paSectionPct is hidden, paSectionPrice is visible")

        # Check prefilled target price value
        val = page.input_value("#paInputTarget")
        print("Prefilled target price:", val)
        assert int(val) > 0, "Target price should be prefilled"

        # Change target price to lower value and verify calculations
        cur = int(page.input_value("#paHiddenCurPrice"))
        target = int(cur * 0.8)
        page.fill("#paInputTarget", str(target))
        page.wait_for_timeout(200)
        savings_text = page.inner_text("#paSavingsBadge")
        print("Savings badge in price mode:", savings_text)
        expected_diff = cur - target
        assert str(expected_diff) in savings_text, f"Expected {expected_diff} in {savings_text}"

        # Capture screenshot of Target Price mode
        page.screenshot(path="price_alert_target_mode.png")
        print("Screenshot saved to price_alert_target_mode.png")

        # Switch back to percent mode
        page.click("#paTabBtnPct")
        page.wait_for_timeout(300)
        assert page.is_visible("#paSectionPct"), "Percent section should be visible"
        assert not page.is_visible("#paSectionPrice"), "Price section should be hidden"
        print("Switch back to percent mode verified successfully!")

        browser.close()

if __name__ == "__main__":
    test_modal_toggle()

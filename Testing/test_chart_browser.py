import sys
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    console_errors = []
    page.on('console', lambda msg: console_errors.append(msg.text) if msg.type == 'error' else None)
    page.on('pageerror', lambda err: console_errors.append(str(err)))

    print("Navigating to URL comparison results...")
    page.goto('http://127.0.0.1:5000/search?url=https://www.amazon.in/dp/B08L5WHFT9', timeout=60000)
    page.wait_for_load_state('networkidle')

    canvas = page.locator('#multiPlatformPriceChart')
    print('Canvas count:', canvas.count())
    print('Canvas visible:', canvas.is_visible())
    
    # Check if chart is initialized (Chart.js attaches $chartjs or creates internal state)
    chart_rendered = page.evaluate("""() => {
        const c = document.getElementById('multiPlatformPriceChart');
        if (!c) return false;
        // Check if Chart instance exists
        const chart = Chart.getChart(c);
        return chart !== undefined && chart !== null;
    }""")
    print('Chart instance exists on canvas:', chart_rendered)
    print('Console errors:', console_errors)

    # Take screenshot of prediction card
    pred_card = page.locator('#pricePredictionCard')
    if pred_card.count() > 0:
        pred_card.screenshot(path='price_prediction_chart_test.png')
        print('Screenshot saved as price_prediction_chart_test.png')

    browser.close()

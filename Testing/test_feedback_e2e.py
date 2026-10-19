import sys
sys.path.insert(0, '.')
from app import app
from flask.sessions import SecureCookieSessionInterface
from playwright.sync_api import sync_playwright

si = SecureCookieSessionInterface()
signer = si.get_signing_serializer(app)
session_data = {'user_id': '6a8dbf0a5a683db316d6c131', 'user_name': 'Hithesh B R'}
cookie_val = signer.dumps(session_data)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context()
    ctx.add_cookies([{'name': 'session', 'value': cookie_val, 'domain': '127.0.0.1', 'path': '/'}])
    page = ctx.new_page()

    # 1. TEST ON /profile
    print('--- Testing /profile edit feedback ---')
    page.goto('http://127.0.0.1:5000/profile')
    page.wait_for_selector('text=Edit Feedback')
    page.locator('button:has-text("Edit Feedback")').first.click()
    page.wait_for_timeout(500)

    # Edit fields
    title_input = page.locator('#editFeedbackModal6ad104adfd085a5b2e4e3637 input[name="title"]')
    title_input.fill('Ghar Soaps Kojic Acid Soap')

    msg_input = page.locator('#editFeedbackModal6ad104adfd085a5b2e4e3637 textarea[name="message"]')
    msg_input.fill('Excellent product, highly recommended!')

    rating_select = page.locator('#editFeedbackModal6ad104adfd085a5b2e4e3637 select[name="rating"]')
    rating_select.select_option('5')

    # Click Save Changes
    page.locator('#editFeedbackModal6ad104adfd085a5b2e4e3637 button[type="submit"]').click()
    page.wait_for_load_state('networkidle')

    # Verify updated content on profile page
    content = page.content()
    assert 'Rating and feedback updated successfully.' in content, 'Flash message not found!'
    assert 'Excellent product, highly recommended!' in content, 'Updated message not found!'
    print('SUCCESS: Profile edit feedback updated and verified!')

    # 2. TEST ON /my-feedback
    print('--- Testing /my-feedback edit feedback ---')
    page.goto('http://127.0.0.1:5000/my-feedback')
    page.wait_for_selector('text=Edit')
    page.locator('button:has-text("Edit")').first.click()
    page.wait_for_timeout(500)

    # Edit fields
    title_input_mf = page.locator('#editModal6ad104adfd085a5b2e4e3637 input[name="title"]')
    title_input_mf.fill('Ghar Soaps Kojic Acid Soap')

    msg_input_mf = page.locator('#editModal6ad104adfd085a5b2e4e3637 textarea[name="message"]')
    msg_input_mf.fill('exellent')

    rating_select_mf = page.locator('#editModal6ad104adfd085a5b2e4e3637 select[name="rating"]')
    rating_select_mf.select_option('3')

    # Click Save Changes
    page.locator('#editModal6ad104adfd085a5b2e4e3637 button[type="submit"]').click()
    page.wait_for_load_state('networkidle')

    content_mf = page.content()
    assert 'Rating and feedback updated successfully.' in content_mf, 'Flash message not found on my-feedback!'
    assert 'exellent' in content_mf, 'Reverted message not found!'
    print('SUCCESS: /my-feedback edit feedback verified!')

    browser.close()
    print('ALL TESTS PASSED SUCCESSFULLY!')

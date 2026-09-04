import os
import time
from datetime import datetime
from flask import Flask, request, jsonify
from DrissionPage import ChromiumPage, ChromiumOptions

app = Flask(__name__)

def create_options():
    co = ChromiumOptions()
    co.set_browser_path('/usr/bin/chromium')
    co.headless()
    co.set_argument('--no-sandbox')
    co.set_argument('--disable-dev-shm-usage')
    co.set_argument('--disable-gpu')
    co.set_argument('--disable-blink-features=AutomationControlled')
    co.set_user_agent(
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    )
    return co

def wait_for_turnstile(page, max_wait=30):
    """
    Chờ input ẩn cf-turnstile-response xuất hiện VÀ có token.
    Input này nằm ở light DOM (ngoài shadow root) nên luôn query được.
    """
    start = time.time()
    while time.time() - start < max_wait:
        try:
            token_input = page.ele('css:input[name="cf-turnstile-response"]', timeout=1)
            if token_input:
                token = token_input.attr('value') or ''
                if token:
                    return True, token
        except Exception:
            pass
        time.sleep(2)
    return False, ''

@app.route('/test-widget')
def test_widget():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'Thiếu param ?url='}), 400

    page = None
    try:
        page = ChromiumPage(create_options())
        page.get(url)

        # 🔑 Locator chuẩn: input ẩn cf-turnstile-response
        solved, token = wait_for_turnstile(page)

        title = page.title
        chrome_version = page.run_cdp('Browser.getVersion')['product']

        return jsonify({
            'url': url,
            'pageTitle': title,
            'chromeVersion': chrome_version,
            'widgetLoaded': solved,
            'turnstileSolved': solved,
            'tokenLength': len(token),
            'tokenPreview': (token[:60] + '...') if token else None,
            'checkedAt': datetime.now().isoformat(),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if page:
            page.quit()

@app.route('/')
def index():
    return 'DrissionPage on Render. GET /test-widget?url=https://example.com'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))

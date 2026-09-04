import os
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

@app.route('/test-widget')
def test_widget():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'Thiếu param ?url='}), 400

    page = None
    try:
        page = ChromiumPage(create_options())
        page.get(url)
        page.wait(8)

        title = page.title
        iframes = page.eles('tag:iframe')
        iframe_found = any(
            'challenges.cloudflare.com' in (i.attr('src') or '') for i in iframes
        )
        
        # 👇 THÊM DÒNG NÀY để lấy version Chrome
        chrome_version = page.run_cdp('Browser.getVersion')['product']

        return jsonify({
            'url': url,
            'pageTitle': title,
            'widgetLoaded': iframe_found,
            'chromeVersion': chrome_version,  # ✅ Giờ mới dùng được
            'checkedAt': __import__('datetime').datetime.now().isoformat(),
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

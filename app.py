import os
import subprocess
import time
from datetime import datetime
from flask import Flask, request, jsonify
from DrissionPage import ChromiumPage, ChromiumOptions

app = Flask(__name__)

# ====== "ĐƯỜNG DẪN CHROME" TRÊN RENDER ======
CHROME_PATH = '/usr/bin/chromium'
DEBUG_PORT = 9222
PROFILE_DIR = '/tmp/chrome_profile'   # profile sống suốt phiên instance

_chrome_proc = None

def bat_equivalent():
    """
    BẢN DỊCH CỦA FILE .BAT SANG LINUX:
    Khởi động Chrome như 1 process ĐỘC LẬP, có profile riêng,
    KHÔNG phải do DrissionPage spawn ra.
    """
    global _chrome_proc
    if _chrome_proc is not None and _chrome_proc.poll() is None:
        return  # Chrome đang chạy sẵn rồi

    _chrome_proc = subprocess.Popen([
        CHROME_PATH,
        f'--remote-debugging-port={DEBUG_PORT}',
        f'--user-data-dir={PROFILE_DIR}',
        '--headless=new',                      # Render không có màn hình
        '--no-first-run',
        '--no-default-browser-check',
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--disable-blink-features=AutomationControlled',
        '--window-size=1920,1080',
    ])
    time.sleep(3)  # chờ Chrome khởi động

def get_driver():
    """Giống hệt code local của bạn: attach qua port"""
    bat_equivalent()
    co = ChromiumOptions()
    co.set_local_port(DEBUG_PORT)
    return ChromiumPage(co)

@app.route('/test-widget')
def test_widget():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'Thiếu param ?url='}), 400

    try:
        page = get_driver()
        page.get(url)

        locator = "xpath://input[@name='cf-turnstile-response' and @value!='']"
        solved, token = False, ''
        start = time.time()
        while time.time() - start < 45:
            ele = page.ele(locator, timeout=2)
            if ele:
                token = ele.attr('value') or ''
                if token:
                    solved = True
                    break
            time.sleep(1)

        return jsonify({
            'url': url,
            'pageTitle': page.title,
            'widgetLoaded': solved,
            'turnstileSolved': solved,
            'tokenLength': len(token),
            'tokenPreview': (token[:60] + '...') if token else None,
            'checkedAt': datetime.now().isoformat(),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    # ⚠️ KHÔNG có page.quit()! Browser phải sống để giữ profile + trust

@app.route('/')
def index():
    return 'Chrome-as-BAT mode. GET /test-widget?url=...'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))

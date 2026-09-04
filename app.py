import os
import subprocess
import time
from datetime import datetime
from flask import Flask, request, jsonify
from DrissionPage import ChromiumPage, ChromiumOptions

app = Flask(__name__)

CHROME_PATH = '/usr/bin/chromium'
DEBUG_PORT = 9222
PROFILE_DIR = '/tmp/chrome_profile'
_chrome_proc = None

def start_chrome_headed_on_virtual_display():
    """
    Chạy Chrome HEADED (không --headless) trên màn hình ảo Xvfb.
    Chrome tưởng đang có màn hình thật -> giống hệt local.
    """
    global _chrome_proc
    if _chrome_proc is not None and _chrome_proc.poll() is None:
        return  # Đang chạy rồi

    _chrome_proc = subprocess.Popen([
        'xvfb-run', '-a',           # 👈 Chạy qua màn hình ảo
        '--server-args=-screen 0 1920x1080x24',
        CHROME_PATH,
        f'--remote-debugging-port={DEBUG_PORT}',
        f'--user-data-dir={PROFILE_DIR}',
        '--profile-directory=Default',
        '--no-first-run',
        '--no-default-browser-check',
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--disable-blink-features=AutomationControlled',
        '--window-size=1920,1080',
        # ⚠️ KHÔNG có --headless=new
    ])
    time.sleep(5)  # Chờ Chrome + Xvfb khởi động

def get_driver():
    start_chrome_headed_on_virtual_display()
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

        while time.time() - start < 60:
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
    # ⚠️ KHÔNG page.quit() — giữ browser sống để tích lũy trust

@app.route('/')
def index():
    return 'Chrome HEADED on Xvfb. GET /test-widget?url=...'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))

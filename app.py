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

_xvfb_proc = None
_chrome_proc = None

def setup_environment():
    global _xvfb_proc, _chrome_proc
    
    # 1. Khởi động màn hình ảo Xvfb (nếu chưa có)
    if _xvfb_proc is None:
        # Tạo màn hình ảo :99 với độ phân giải 1920x1080
        _xvfb_proc = subprocess.Popen(['Xvfb', ':99', '-screen', '0', '1920x1080x24'])
        os.environ['DISPLAY'] = ':99'
        time.sleep(2) # Chờ Xvfb khởi động

    # 2. Spawn Chrome ở chế độ HEADED (KHÔNG dùng --headless)
    if _chrome_proc is None or _chrome_proc.poll() is not None:
        _chrome_proc = subprocess.Popen([
            CHROME_PATH,
            f'--remote-debugging-port={DEBUG_PORT}',
            f'--user-data-dir={PROFILE_DIR}',
            # BỎ --headless đi! Chrome sẽ chạy trên màn hình ảo Xvfb
            '--no-first-run',
            '--no-default-browser-check',
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-blink-features=AutomationControlled',
            '--window-size=1920,1080',
        ])
        time.sleep(3) # Chờ Chrome bind port 9222

def get_driver():
    setup_environment()
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
        
        # Locator chuẩn để bắt token
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

@app.route('/')
def index():
    return 'Chrome Headed + Xvfb mode. GET /test-widget?url=...'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))

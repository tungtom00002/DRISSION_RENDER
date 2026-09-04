import os
import subprocess
import time
import socket
import shutil
from datetime import datetime
from flask import Flask, request, jsonify
from DrissionPage import ChromiumPage, ChromiumOptions

app = Flask(__name__)

# Tự động tìm đường dẫn Chromium
CHROME_PATH = shutil.which('chromium') or '/usr/bin/chromium'
DEBUG_PORT = 9222
PROFILE_DIR = '/tmp/chrome_profile'
_chrome_proc = None

def wait_for_port(port, host="127.0.0.1", timeout=45.0):
    """Thăm dò port bằng socket. Chờ tối đa 45s vì CPU Render rất yếu."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(1)
    return False

def start_chrome_background():
    global _chrome_proc
    if _chrome_proc is not None and _chrome_proc.poll() is None:
        return  # Chrome đang chạy ngon lành

    print(f"🚀 Đang spawn Chrome ({CHROME_PATH}) tại port {DEBUG_PORT}...")
    _chrome_proc = subprocess.Popen(
        [
            CHROME_PATH,
            f'--remote-debugging-port={DEBUG_PORT}',
            f'--user-data-dir={PROFILE_DIR}',
            '--headless=new',
            '--no-first-run',
            '--no-default-browser-check',
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--disable-blink-features=AutomationControlled',
            '--window-size=1920,1080',
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # Chờ port thực sự mở
    if not wait_for_port(DEBUG_PORT):
        # Nếu port không mở -> Chrome đã crash. In lỗi ra Log Render!
        if _chrome_proc.poll() is not None:
            _, err = _chrome_proc.communicate()
            print(f"❌ CHROME CRASHED ON STARTUP:\n{err.decode('utf-8', errors='ignore')}")
        raise Exception("Chrome failed to start and bind to port 9222")
    
    print("✅ Chrome đã khởi động và mở port thành công!")

# 🔥 KHỞI ĐỘNG CHROME NGAY KHI FILE APP.PY ĐƯỢC LOAD (Tránh timeout request đầu)
try:
    start_chrome_background()
except Exception as e:
    print(f"⚠️ Lỗi khởi động Chrome ban đầu: {e}")

@app.route('/test-widget')
def test_widget():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'Thiếu param ?url='}), 400
    
    # Kiểm tra xem Chrome có còn sống không, nếu chết thì hồi sinh
    if _chrome_proc is None or _chrome_proc.poll() is not None:
        try:
            start_chrome_background()
        except Exception as e:
            return jsonify({'error': f'Chrome process failed: {str(e)}'}), 500

    try:
        co = ChromiumOptions()
        co.set_local_port(DEBUG_PORT)
        page = ChromiumPage(co)
        
        page.get(url)
        locator = "xpath://input[@name='cf-turnstile-response' and @value!='']"
        solved, token = False, ''
        start = time.time()
        
        # Chờ widget solve
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
    return 'Chrome-as-BAT mode on Render. GET /test-widget?url=...'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))

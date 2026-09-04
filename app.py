import os
import subprocess
import time
import socket
from datetime import datetime
from flask import Flask, request, jsonify
from DrissionPage import ChromiumPage, ChromiumOptions

app = Flask(__name__)

# ====== CẤU HÌNH CHROME TRÊN RENDER (LINUX) ======
CHROME_PATH = '/usr/bin/chromium'
DEBUG_PORT = 9222
PROFILE_DIR = '/tmp/chrome_profile'  # Lưu profile vào /tmp để tích lũy trust

def is_port_open(port):
    """Kiểm tra xem Chrome đã mở port debug chưa"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0

def launch_chrome_bat_style():
    """BẢN DỊCH CỦA FILE .BAT SANG LINUX"""
    if is_port_open(DEBUG_PORT):
        print("✅ Chrome đã chạy sẵn trên port 9222. Attach luôn!")
        return
        
    print("🚀 Port 9222 trống. Đang khởi động Chrome qua subprocess...")
    subprocess.Popen([
        CHROME_PATH,
        f'--remote-debugging-port={DEBUG_PORT}',
        f'--user-data-dir={PROFILE_DIR}',
        '--headless=new',                      # Bắt buộc trên server
        '--no-first-run',
        '--no-default-browser-check',
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--disable-blink-features=AutomationControlled',
        '--window-size=1920,1080',
    ])
    print("⏳ Chờ Chrome khởi động và mở port debug (3s)...")
    time.sleep(3)

def get_driver():
    """Attach vào Chrome y hệt cách làm ở local"""
    launch_chrome_bat_style()
    print("🔗 Đang attach DrissionPage vào Chrome...")
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
        
        # Locator chuẩn mực
        locator = "xpath://input[@name='cf-turnstile-response' and @value!='']"
        solved, token = False, ''
        start = time.time()
        
        # Chờ tối đa 45s
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
    # LƯU Ý: KHÔNG GỌI page.quit() ĐỂ GIỮ CHROME SỐNG DAI!

@app.route('/')
def index():
    return 'Chrome-as-BAT mode on Render. GET /test-widget?url=...'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))

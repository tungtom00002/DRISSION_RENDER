import os
import subprocess
import time
import urllib.request
from datetime import datetime
from flask import Flask, request, jsonify
from DrissionPage import ChromiumPage, ChromiumOptions

app = Flask(__name__)

# ====== CẤU HÌNH ======
CHROME_PATH = '/usr/bin/chromium'  # Đường dẫn Chrome do apt-get cài
DEBUG_PORT = 9222
PROFILE_DIR = '/tmp/chrome_profile'
_chrome_proc = None

def bat_equivalent():
    """
    Khởi động Chrome độc lập và chờ port DevTools thực sự mở.
    """
    global _chrome_proc
    
    # 1. Kiểm tra xem process cũ còn sống và port còn thở không
    if _chrome_proc is not None and _chrome_proc.poll() is None:
        try:
            req = urllib.request.urlopen(f'http://127.0.0.1:{DEBUG_PORT}/json/version', timeout=2)
            if req.status == 200:
                return  # Chrome vẫn đang chạy ngon
        except Exception:
            pass  # Port chết, chuẩn bị spawn lại

    # 2. Kiểm tra file Chrome có tồn tại không
    if not os.path.exists(CHROME_PATH):
        raise Exception(f"❌ Không tìm thấy Chrome tại {CHROME_PATH}. Kiểm tra lại Dockerfile đã cài chromium chưa.")

    print("🚀 Đang spawn Chromium process...")
    _chrome_proc = subprocess.Popen(
        [
            CHROME_PATH,
            f'--remote-debugging-port={DEBUG_PORT}',
            '--remote-debugging-address=0.0.0.0',  # Bind mọi interface
            f'--user-data-dir={PROFILE_DIR}',
            '--headless=new',
            '--no-first-run',
            '--no-default-browser-check',
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            '--disable-software-rasterizer',  # Chống crash do không có GPU thật
            '--disable-blink-features=AutomationControlled',
            '--window-size=1920,1080',
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

    # 3. Vòng lặp Health Check: Chờ port 9222 mở (tối đa 30s cho Render 0.1 CPU)
    for i in range(30):
        # Nếu process chết giữa chừng
        if _chrome_proc.poll() is not None:
            out = _chrome_proc.stdout.read()
            print(f"💀 Chromium CRASHED ngay khi khởi động! Log:\n{out}")
            raise Exception(f"Chromium crashed: {out[:500]}")
        
        # Thăm dò port
        try:
            req = urllib.request.urlopen(f'http://127.0.0.1:{DEBUG_PORT}/json/version', timeout=1)
            if req.status == 200:
                print(f"✅ Chromium DevTools ready sau {i+1}s!")
                return
        except Exception:
            pass
        
        time.sleep(1)
        
    raise Exception("⏳ Timeout: Chromium không mở port 9222 sau 30s.")

def get_driver():
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
    # ⚠️ KHÔNG gọi page.quit() để giữ trust

@app.route('/')
def index():
    return 'Chrome-as-BAT mode (Hardened). GET /test-widget?url=...'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))

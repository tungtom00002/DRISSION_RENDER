import os
import subprocess
import time
from datetime import datetime
from flask import Flask, request, jsonify
from DrissionPage import ChromiumPage, ChromiumOptions

app = Flask(__name__)

# ====== CẤU HÌNH CHROME TRÊN RENDER (LINUX) ======
CHROME_PATH = '/usr/bin/chromium'
DEBUG_PORT = 9222
PROFILE_DIR = '/tmp/chrome_profile'
_chrome_proc = None

def bat_equivalent():
    """
    Spawn Chrome như một process độc lập (giống file .BAT ở local).
    Giữ Chrome sống xuyên suốt vòng đời của instance Render.
    """
    global _chrome_proc
    # Nếu Chrome đang chạy thì thôi, không spawn lại
    if _chrome_proc is not None and _chrome_proc.poll() is None:
        return 
    
    try:
        _chrome_proc = subprocess.Popen([
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
        ])
        time.sleep(3)  # Chờ 3s cho Chrome khởi động
        print(f"✅ Chrome đã khởi động với PID: {_chrome_proc.pid}")
    except Exception as e:
        print(f"❌ Lỗi spawn Chrome: {e}")

def get_driver():
    """Attach DrissionPage vào Chrome đang chạy qua port 9222"""
    bat_equivalent()
    co = ChromiumOptions()
    co.set_local_port(DEBUG_PORT)
    return ChromiumPage(co)

# ==========================================
# CÁC ENDPOINTS
# ==========================================

@app.route('/')
def index():
    return '🚀 Chrome-as-BAT mode is running. Use /test-widget?url=... or /status'

@app.route('/status')
def status():
    """Endpoint để kiểm tra xem Chrome process có đang sống không"""
    global _chrome_proc
    chrome_alive = _chrome_proc is not None and _chrome_proc.poll() is None
    return jsonify({
        'chrome_process_alive': chrome_alive,
        'chrome_pid': _chrome_proc.pid if _chrome_proc else None,
        'profile_dir': PROFILE_DIR,
        'debug_port': DEBUG_PORT,
        'message': 'Chrome đang chạy ngầm và tích lũy trust' if chrome_alive else 'Chrome đã chết hoặc chưa được spawn'
    })

@app.route('/test-widget')
def test_widget():
    url = request.args.get('url')
    if not url:
        return jsonify({'error': 'Thiếu param ?url='}), 400
        
    try:
        page = get_driver()
        page.get(url)
        
        # Locator chuẩn: input ẩn có chứa token
        locator = "xpath://input[@name='cf-turnstile-response' and @value!='']"
        solved, token = False, ''
        start = time.time()
        
        # Chờ tối đa 45s
        while time.time() - start < 45:
            try:
                ele = page.ele(locator, timeout=2)
                if ele:
                    token = ele.attr('value') or ''
                    if token:
                        solved = True
                        break
            except:
                pass
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
        
    # ⚠️ TUYỆT ĐỐI KHÔNG GỌI page.quit() Ở ĐÂY!
    # Browser phải sống để giữ profile + trust cho các request sau.

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
